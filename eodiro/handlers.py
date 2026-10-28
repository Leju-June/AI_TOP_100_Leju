"""명령 처리. 전송 방식(웹훅/CLI)과 무관하게 SkillResponse 를 만들어 돌려준다."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from . import commands as c
from . import food_service as food
from . import kakao_bot as kb
from . import route_service as route
from .config import KST
from .kakao_map import CATEGORY_RESTAURANT, KakaoMapClient, KakaoMapError, Place, Point
from .store import LocationRequest, Store

log = logging.getLogger(__name__)

KIND_ROUTE = "route"
KIND_NEARBY_FOOD = "nearby_food"

HELP_TEXT = """🧭 어디로 사용법
'@어디로'를 멘션하고 뒤에 말해주세요.

🚶 남은 동선 알려주기
@어디로 미금역
@어디로 미금역까지 버스로
→ 버튼으로 내 위치를 보내면 남은 거리, 남은 시간, 도착 예정 시각과 카카오맵 길찾기를 방에 올려줘요.
→ 이동 수단: 대중교통(기본)·버스·지하철·도보

🍽 우리 방 맛집
@어디로 맛집 추가 식당이름
@어디로 맛집 리스트
@어디로 맛집 삭제 번호

🎲 메뉴 추천
@어디로 점메추 / 저메추
→ 우리 방 맛집 중에서 골라줘요.
@어디로 아무대나 점메추
→ 내 위치 근처 1km 안에서 골라줘요.

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


def error_reply(text: str) -> dict:
    return kb.skill_response(kb.simple_text(text))


class Bot:
    def __init__(self, store: Store, maps: KakaoMapClient, public_base_url: str, location_ttl_sec: int = 600,
                 clock: Callable[[], datetime] = lambda: datetime.now(KST)):
        self.store = store
        self.maps = maps
        self.base_url = public_base_url
        self.location_ttl_sec = location_ttl_sec
        self.clock = clock
        # 방별 '맛집 추가' 후보 목록. 후보를 누르면 식당 이름만 채팅으로 오므로 이름으로 맞춘다.
        self.pending_candidates: dict[str, tuple[list[Place], float]] = {}

    def room_key(self, msg: Message) -> str:
        # 채널채팅은 방 키 대신 사용자 키로 목록을 구분한다.
        return msg.group_key or msg.user_key

    def locate_url(self, req_id: str) -> str:
        return f"{self.base_url}/locate?req={req_id}"

    def _pending_candidate(self, room: str, text: str) -> Place | None:
        places, created_at = self.pending_candidates.get(room, ([], 0.0))
        if self.clock().timestamp() - created_at > self.location_ttl_sec:
            return None
        name = c.MENTION_RE.sub("", text, count=1).strip()
        return next((p for p in places if p.name == name), None)

    async def handle_message(self, msg: Message) -> dict:
        room = self.room_key(msg)
        picked = self._pending_candidate(room, msg.content)
        if picked:
            del self.pending_candidates[room]
            is_new = self.store.add_restaurant(room, picked, msg.user_key)
            return food.added_reply(picked, is_new, len(self.store.list_restaurants(room)))

        cmd = c.parse(msg.content, self.clock())
        try:
            return await self._dispatch(cmd, msg)
        except KakaoMapError:
            log.exception("카카오맵 API 오류")
            return error_reply("카카오맵 응답에 문제가 있어요. 잠시 후 다시 시도해주세요.")

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
                self.pending_candidates[room] = (results[:5], self.clock().timestamp())
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
        if req.kind == KIND_ROUTE and user_key and req.user_key and user_key != req.user_key:
            raise LocationError(403, "길찾기를 요청한 사람만 위치를 보낼 수 있어요.")

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
