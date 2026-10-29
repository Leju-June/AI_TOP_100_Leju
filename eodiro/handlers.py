"""명령 처리. 전송 방식(웹훅/CLI)과 무관하게 SkillResponse 를 만들어 돌려준다."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from . import commands as c
from . import food_service as food
from . import kakao_bot as kb
from . import route_service as route
from .agent import KIND_AGENT, Agent
from .config import KST
from .kakao_map import CATEGORY_RESTAURANT, KakaoMapClient, KakaoMapError, Place, Point
from .register_commands import COMMANDS
from .store import LocationRequest, Store
from .tools import CMD_CANCEL, CMD_CONFIRM_REMOVE

log = logging.getLogger(__name__)

KIND_ROUTE = "route"
KIND_NEARBY_FOOD = "nearby_food"

HELP_TEXT = """🧭 어디로 사용법
'@어디로'를 멘션하고 편하게 말해주세요.

🚶 남은 동선
"미금역 가는 중인데 얼마나 남았어?"
"7시까지 강남역인데 지금 출발하면 안 늦어?"
→ 위치 버튼으로 내 위치를 보내면 남은 거리, 남은 시간, 도착 예정 시각과 카카오맵 길찾기를 알려드려요.

🍽 메뉴 추천
"오늘 점메추, 어제 국밥 먹었음"
"강남 가는 길에 저녁 먹을 데 있어?"
"아까 그 집 우리 맛집에 넣어줘"

📍 위치 버튼은 요청한 사람만 쓸 수 있고 10분 뒤 만료돼요."""


@dataclass
class Message:
    content: str
    group_key: str
    user_key: str
    is_channel: bool = False


@dataclass
class LocationResult:
    response: dict
    summary: str  # 위치 전송 페이지에 보여줄 한 줄


class LocationError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# 버튼·추천 명령어와 같은 문장은 LLM 을 거치지 않고 기존 파서로 바로 처리한다.
FAST_COMMANDS = {name for name, _ in COMMANDS} | {food.CMD_LIST, food.CMD_ADD_LAST}
AGENT_TIMEOUT_SEC = 90  # 콜백 토큰(5분) 안에 답하도록


def error_reply(text: str) -> dict:
    return kb.skill_response(kb.simple_text(text))


class Bot:
    def __init__(self, store: Store, maps: KakaoMapClient, public_base_url: str, location_ttl_sec: int = 600,
                 clock: Callable[[], datetime] = lambda: datetime.now(KST), agent: Agent | None = None):
        self.store = store
        self.maps = maps
        self.base_url = public_base_url
        self.location_ttl_sec = location_ttl_sec
        self.clock = clock
        self.agent = agent  # None 이면 기존 명령어 파서만 쓴다

    def room_key(self, msg: Message) -> str:
        # 채널채팅은 방 키 대신 사용자 키로 목록을 구분한다.
        return msg.group_key or msg.user_key

    def locate_url(self, req_id: str) -> str:
        return f"{self.base_url}/locate?req={req_id}"

    async def handle_message(self, msg: Message) -> dict:
        room = self.room_key(msg)
        body = c.MENTION_RE.sub("", msg.content, count=1).strip()
        try:
            pending_reply = await self._handle_pending(room, body, msg)
            if pending_reply:
                return pending_reply
            if self.agent and body not in FAST_COMMANDS:
                try:
                    return await asyncio.wait_for(
                        self.agent.handle(msg.content, room, msg.group_key, msg.user_key, msg.is_channel),
                        AGENT_TIMEOUT_SEC)
                except Exception:
                    log.exception("에이전트 실패, 명령어 파서로 처리")
            return await self._dispatch(c.parse(msg.content, self.clock()), msg)
        except KakaoMapError:
            log.exception("카카오맵 API 오류")
            return error_reply("카카오맵 응답에 문제가 있어요. 잠시 후 다시 시도해주세요.")

    async def _handle_pending(self, room: str, body: str, msg: Message) -> dict | None:
        """후보 선택·되묻기·삭제 확인에 대한 답이면 처리하고, 아니면 None."""
        pending = self.store.get_pending(room)
        if pending is None or self.clock().timestamp() - pending.created_at > self.location_ttl_sec:
            return None
        if body == CMD_CANCEL and pending.kind in ("ask", "confirm_remove"):
            self.store.clear_pending(room)
            return kb.skill_response(kb.simple_text("취소했어요."))

        if pending.kind == "candidates":
            # 후보를 누르면 식당 이름만 채팅으로 오므로 이름으로 맞춘다.
            picked = next((Place.from_dict(d) for d in pending.data["places"] if d["name"] == body), None)
            if picked:
                self.store.clear_pending(room)
                is_new = self.store.add_restaurant(room, picked, msg.user_key)
                return food.added_reply(picked, is_new, len(self.store.list_restaurants(room)))
        elif pending.kind == "confirm_remove" and body == CMD_CONFIRM_REMOVE:
            if pending.user_key and msg.user_key != pending.user_key:
                return error_reply("삭제를 요청한 사람만 확정할 수 있어요.")
            self.store.clear_pending(room)
            place = Place.from_dict(pending.data["place"])
            self.store.remove_restaurant(room, place.id)
            return food.removed_reply(place)
        elif pending.kind == "ask" and self.agent and body in pending.data["options"]:
            self.store.clear_pending(room)
            try:
                return await asyncio.wait_for(self.agent.resume_answer(pending, body), AGENT_TIMEOUT_SEC)
            except Exception:
                log.exception("에이전트 재개 실패")
                return error_reply("이어서 처리하지 못했어요. 처음부터 다시 말해주세요.")
        return None

    async def _dispatch(self, cmd: c.Command, msg: Message) -> dict:
        match cmd:
            case c.Help():
                return kb.skill_response(kb.simple_text(HELP_TEXT))
            case c.Route(destination, mode):
                return await self._route_request(destination, mode, msg)
            case c.AddRestaurant(query):
                return await self._add_restaurant(query, msg)
            case c.RemoveRestaurant(target):
                return self._remove_restaurant(target, msg)
            case c.ListRestaurants():
                return food.list_reply(self.store.list_restaurants(self.room_key(msg)))
            case c.Recommend(meal, nearby):
                return self._recommend(meal, nearby, msg)

    async def _route_request(self, destination: str, mode: c.Mode, msg: Message) -> dict:
        places = await self.maps.search_keyword(destination, size=1)
        if not places:
            return error_reply(f"'{destination}'을(를) 카카오맵에서 찾지 못했어요. 다른 이름으로 다시 말해주세요.")
        dest = places[0]
        req_id = self.store.create_location_request(
            KIND_ROUTE, {"dest": dest.to_dict(), "mode": mode.name}, msg.group_key, msg.user_key, msg.is_channel,
            self.clock().timestamp())
        return route.location_request_reply(dest, mode, self.locate_url(req_id))

    async def _add_restaurant(self, query: str, msg: Message) -> dict:
        room = self.room_key(msg)
        if not query:
            # '맛집 추가' 버튼: 이 방에서 방금 추천한 곳
            recent = self.store.recent_picks(room, limit=1)
            place = self.store.get_cached_place(recent[0]) if recent else None
            if not place:
                return error_reply("추가할 식당 이름을 같이 말해주세요. 예: '@어디로 맛집 추가 식당이름'")
        else:
            results = await self.maps.search_keyword(query, size=5)
            results = [p for p in results if food.is_food_place(p)] or results
            if not results:
                return error_reply(f"'{query}'을(를) 카카오맵에서 찾지 못했어요.")
            place = food.choose_search_result(query, results)
            if place is None:
                self.store.set_pending(room, "candidates", msg.user_key,
                                       {"places": [p.to_dict() for p in results[:5]]}, self.clock().timestamp())
                return food.candidates_reply(query, results)
        is_new = self.store.add_restaurant(room, place, msg.user_key)
        return food.added_reply(place, is_new, len(self.store.list_restaurants(room)))

    def _remove_restaurant(self, target: str, msg: Message) -> dict:
        room = self.room_key(msg)
        places = self.store.list_restaurants(room)
        if target.isdigit() and 1 <= int(target) <= len(places):
            place = places[int(target) - 1]
        else:
            matches = [p for p in places if target.replace(" ", "") in p.name.replace(" ", "")]
            if len(matches) != 1:
                return error_reply("어떤 곳인지 모르겠어요. '@어디로 맛집 리스트'에서 번호를 확인하고 "
                                   "'@어디로 맛집 삭제 번호'로 말해주세요.")
            place = matches[0]
        self.store.remove_restaurant(room, place.id)
        return food.removed_reply(place)

    def _recommend(self, meal: str, nearby: bool, msg: Message) -> dict:
        if nearby:
            req_id = self.store.create_location_request(
                KIND_NEARBY_FOOD, {"meal": meal}, msg.group_key, msg.user_key, msg.is_channel,
                self.clock().timestamp())
            return food.nearby_request_reply(meal, self.locate_url(req_id))
        room = self.room_key(msg)
        places = self.store.list_restaurants(room)
        if not places:
            return food.list_reply([])
        place = food.pick_restaurant(places, self.store.recent_picks(room))
        self.store.record_pick(room, place.id)
        return food.recommend_reply(place, meal, nearby=False)

    # ------------------------- 위치 전송 페이지에서 호출 -------------------------

    def get_location_request(self, req_id: str) -> LocationRequest:
        req = self.store.get_location_request(req_id)
        if req is None:
            raise LocationError(404, "요청을 찾을 수 없어요.")
        if self.clock().timestamp() - req.created_at > self.location_ttl_sec:
            raise LocationError(410, "요청 시간이 지났어요. 채팅방에서 다시 불러주세요.")
        return req

    async def handle_location(self, req_id: str, origin: Point,
                              user_key: str = "") -> tuple[LocationRequest, LocationResult]:
        req = self.get_location_request(req_id)
        if req.used:
            raise LocationError(409, "이미 처리된 요청이에요.")
        if req.kind in (KIND_ROUTE, KIND_AGENT) and user_key and req.user_key and user_key != req.user_key:
            raise LocationError(403, "위치를 요청한 사람만 보낼 수 있어요.")

        if req.kind == KIND_AGENT:
            if self.agent is None:
                raise LocationError(503, "지금은 이 요청을 처리할 수 없어요.")
            self.store.mark_location_request_used(req_id)  # 처리 중 중복 전송 방지
            try:
                done = await asyncio.wait_for(self.agent.resume_location(req, origin), AGENT_TIMEOUT_SEC)
            except Exception:
                log.exception("에이전트 재개 실패")
                raise LocationError(502, "위치는 받았지만 이어서 처리하지 못했어요. 채팅방에서 다시 불러주세요.")
            return req, LocationResult(done.response, done.summary)
        if req.kind == KIND_ROUTE:
            result = await self._complete_route(req.payload, origin)
        else:
            result = await self._complete_nearby(req.payload, origin, req.group_key or req.user_key)
        self.store.mark_location_request_used(req_id)
        return req, result

    async def _complete_route(self, payload: dict, origin: Point) -> LocationResult:
        dest = Place.from_dict(payload["dest"])
        mode = c.Mode[payload["mode"]]
        try:
            result = await route.find_route(self.maps, origin, dest, mode)
        except route.RouteNotFound as e:
            log.warning("경로 없음: %s", e)
            raise LocationError(422, f"{dest.name}까지 {mode.value} 경로를 찾지 못했어요.")
        now = self.clock()
        summary = (f"{dest.name}까지 {route.format_distance(result.distance_m)}, "
                   f"약 {route.format_duration(result.duration_s)} 남았어요.")
        return LocationResult(route.route_reply(dest, mode, result, now), summary)

    async def _complete_nearby(self, payload: dict, origin: Point, room: str) -> LocationResult:
        meal = payload["meal"]
        places = await self.maps.search_category(CATEGORY_RESTAURANT, origin, radius=1000)
        if not places:
            raise LocationError(422, "근처 1km 안에 음식점을 찾지 못했어요.")
        place = food.pick_restaurant(places, self.store.recent_picks(room))
        self.store.record_pick(room, place.id)
        self.store.cache_places([place])  # '맛집 추가' 버튼용
        return LocationResult(food.recommend_reply(place, meal, nearby=True), f"{place.name}을(를) 추천했어요.")
