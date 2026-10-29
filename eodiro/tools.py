"""에이전트가 부르는 도구. 기존 기능(장소 검색, 경로, 맛집 목록, 추천) 위에 얹은 얇은 층이다.

도구 결과는 LLM 에게 돌려줄 JSON 문자열이고, 사람에게 보여줄 말풍선 카드는 RunContext.cards 에 쌓는다.
숫자(거리·시간·도착 시각)는 도구 결과와 카드에서만 나오게 해서 LLM 이 지어내지 않게 한다.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from . import food_service as food
from . import kakao_bot as kb
from . import route_service as route
from .commands import Mode
from .kakao_map import CATEGORY_RESTAURANT, KakaoMapClient, Place, Point
from .store import Store

PAUSE = object()  # 위치·선택을 기다리느라 지금은 결과가 없다는 표시
CMD_CONFIRM_REMOVE = "삭제 확정"
CMD_CANCEL = "취소"

MODES = [m.value for m in Mode]
MEALS = ["점심", "저녁"]

TOOLS: list[dict] = [
    {
        "name": "search_place",
        "description": "장소 이름이나 키워드로 카카오맵을 검색해 최대 5곳을 돌려준다. 목적지나 식당의 place_id 가 필요할 때 먼저 부른다. "
                       "결과가 여러 곳이고 사용자가 어느 곳을 말하는지 분명하지 않으면 ask_user 로 되묻는다.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "검색어. 예: '미금역', '강남역 국밥'"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_route",
        "description": "사용자의 현재 위치에서 장소까지 남은 거리, 남은 시간, 도착 예정 시각을 구하고 길찾기 카드를 답장에 붙인다. "
                       "현재 위치가 없으면 오류가 나므로 먼저 request_location 을 부른다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "place_id": {"type": "string", "description": "search_place 등에서 받은 place_id"},
                "mode": {"type": "string", "enum": MODES, "description": "이동 수단. 말이 없으면 대중교통"},
                "less_walking": {"type": "boolean", "description": "걷는 거리가 적은 대중교통 경로를 원하면 true"},
            },
            "required": ["place_id", "mode"],
        },
    },
    {
        "name": "request_location",
        "description": "요청한 사람에게 현재 위치를 보내는 버튼을 보내고 위치가 올 때까지 기다린다. "
                       "위치가 오면 이 도구의 결과로 알려주니, 그때 위치가 필요한 도구를 이어서 부른다.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string", "description": "위치가 필요한 이유를 사용자에게 보여줄 한 문장"}},
            "required": ["reason"],
        },
    },
    {
        "name": "ask_user",
        "description": "목적지나 식당 후보가 여럿이라 하나로 정할 수 없을 때 후보를 버튼으로 보여주고 고를 때까지 기다린다. "
                       "고른 결과는 이 도구의 결과로 알려준다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "짧은 질문. 예: '어느 홍대를 말하는 거예요?'"},
                "options": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5,
                            "description": "후보 이름. 장소라면 search_place 결과의 name 을 그대로 쓴다"},
            },
            "required": ["question", "options"],
        },
    },
    {
        "name": "list_restaurants",
        "description": "이 방에 등록된 맛집 목록을 돌려준다. show_to_user 가 true 면 목록 카드를 답장에 붙인다.",
        "input_schema": {
            "type": "object",
            "properties": {"show_to_user": {"type": "boolean"}},
            "required": ["show_to_user"],
        },
    },
    {
        "name": "add_restaurant",
        "description": "장소를 이 방 맛집 목록에 추가한다. place_id 는 search_place 결과나 최근 추천한 곳에서 가져온다.",
        "input_schema": {
            "type": "object",
            "properties": {"place_id": {"type": "string"}},
            "required": ["place_id"],
        },
    },
    {
        "name": "remove_restaurant",
        "description": "이 방 맛집 목록에서 장소를 빼달라는 요청에 삭제 확인 버튼을 보낸다. 바로 지우지 않고, 요청한 사람이 버튼을 눌러야 지워진다.",
        "input_schema": {
            "type": "object",
            "properties": {"place_id": {"type": "string", "description": "list_restaurants 결과의 place_id"}},
            "required": ["place_id"],
        },
    },
    {
        "name": "recommend_restaurant",
        "description": "식당 한 곳을 골라 추천 카드를 답장에 붙인다. source 가 room 이면 이 방 맛집 목록에서, "
                       "near_me 면 사용자 현재 위치 1km 안에서(위치 필요), near_place 면 place_id 장소 1km 안에서 고른다. "
                       "최근 추천한 곳은 자동으로 피한다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meal": {"type": "string", "enum": MEALS},
                "source": {"type": "string", "enum": ["room", "near_me", "near_place"]},
                "place_id": {"type": "string", "description": "source 가 near_place 일 때 기준 장소"},
                "exclude_keywords": {"type": "array", "items": {"type": "string"},
                                     "description": "이름이나 업종에 들어가면 빼는 단어. 예: ['국밥']"},
                "exclude_place_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["meal", "source"],
        },
    },
]


class ToolError(Exception):
    pass


@dataclass
class RunContext:
    room: str
    group_key: str
    user_key: str
    is_channel: bool
    origin: Point | None = None
    cards: list[dict] = field(default_factory=list)
    pause: dict | None = None  # {"kind": "location"|"ask", ...}


def outputs(response: dict) -> list[dict]:
    return response["template"]["outputs"]


def place_brief(p: Place) -> dict:
    d = {"place_id": p.id, "name": p.name, "category": p.short_category, "address": p.address}
    if p.distance_m is not None:
        d["distance_m"] = p.distance_m
    return d


class AgentTools:
    def __init__(self, store: Store, maps: KakaoMapClient, clock: Callable[[], datetime]):
        self.store = store
        self.maps = maps
        self.clock = clock

    async def run(self, ctx: RunContext, name: str, args: dict):
        """도구 결과 문자열, 또는 기다려야 하면 PAUSE."""
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            return self._error(f"없는 도구: {name}")
        try:
            result = await fn(ctx, **args)
        except ToolError as e:
            return self._error(str(e))
        except TypeError as e:  # 인자 이름이 틀린 경우
            return self._error(f"인자 오류: {e}")
        return result if result is PAUSE else json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _error(message: str) -> str:
        return json.dumps({"error": message}, ensure_ascii=False)

    def _place(self, place_id: str) -> Place:
        place = self.store.get_cached_place(place_id)
        if place is None:
            raise ToolError(f"place_id '{place_id}' 를 모릅니다. search_place 로 먼저 찾으세요.")
        return place

    async def t_search_place(self, ctx: RunContext, query: str) -> dict:
        places = await self.maps.search_keyword(query, near=ctx.origin, size=5)
        self.store.cache_places(places)
        return {"places": [place_brief(p) for p in places]}

    async def t_get_route(self, ctx: RunContext, place_id: str, mode: str = Mode.TRANSIT.value,
                          less_walking: bool = False) -> dict:
        if ctx.origin is None:
            raise ToolError("사용자 현재 위치가 없습니다. request_location 을 먼저 부르세요.")
        if mode not in MODES:
            raise ToolError(f"mode 는 {MODES} 중 하나여야 합니다.")
        dest, m = self._place(place_id), Mode(mode)
        try:
            result = await route.find_route(self.maps, ctx.origin, dest, m, less_walking)
        except route.RouteNotFound:
            raise ToolError(f"{dest.name}까지 {m.value} 경로를 찾지 못했습니다.")
        now = self.clock()
        ctx.cards.extend(outputs(route.route_reply(dest, m, result, now)))
        arrival = now.timestamp() + result.duration_s
        return {
            "destination": dest.name, "mode": result.mode.value,
            "distance_m": result.distance_m, "duration_min": max(1, round(result.duration_s / 60)),
            "arrival": datetime.fromtimestamp(arrival, now.tzinfo).strftime("%H:%M"),
            "walk_m": result.walk_m, "steps": result.steps, "note": result.note,
        }

    async def t_request_location(self, ctx: RunContext, reason: str):
        if ctx.pause:
            raise ToolError("이미 다른 응답을 기다리고 있습니다.")
        ctx.pause = {"kind": "location", "reason": reason}
        return PAUSE

    async def t_ask_user(self, ctx: RunContext, question: str, options: list[str]):
        if ctx.pause:
            raise ToolError("이미 다른 응답을 기다리고 있습니다.")
        options = [o.strip() for o in options if o.strip()][:5]
        if len(options) < 2:
            raise ToolError("후보는 2개 이상이어야 합니다.")
        ctx.pause = {"kind": "ask", "question": question, "options": options}
        return PAUSE

    async def t_list_restaurants(self, ctx: RunContext, show_to_user: bool = False) -> dict:
        places = self.store.list_restaurants(ctx.room)
        self.store.cache_places(places)
        if show_to_user:
            ctx.cards.extend(outputs(food.list_reply(places)))
        return {"count": len(places), "restaurants": [place_brief(p) for p in places]}

    async def t_add_restaurant(self, ctx: RunContext, place_id: str) -> dict:
        place = self._place(place_id)
        is_new = self.store.add_restaurant(ctx.room, place, ctx.user_key)
        total = len(self.store.list_restaurants(ctx.room))
        ctx.cards.extend(outputs(food.added_reply(place, is_new, total)))
        return {"added": is_new, "already_listed": not is_new, "total": total}

    async def t_remove_restaurant(self, ctx: RunContext, place_id: str) -> dict:
        place = next((p for p in self.store.list_restaurants(ctx.room) if p.id == place_id), None)
        if place is None:
            raise ToolError("이 방 맛집 목록에 없는 장소입니다. list_restaurants 로 확인하세요.")
        self.store.set_pending(ctx.room, "confirm_remove", ctx.user_key, {"place": place.to_dict()},
                               self.clock().timestamp())
        ctx.cards.append(kb.text_card(
            f"🗑 {place.name}을(를) 뺄까요?",
            f"목록에서 빼려면 '{CMD_CONFIRM_REMOVE}'를 눌러주세요. 요청한 사람만 확정할 수 있어요.",
            [kb.message_button(CMD_CONFIRM_REMOVE), kb.message_button(CMD_CANCEL)]))
        return {"status": "확인 버튼을 보냈습니다. 아직 지우지 않았습니다."}

    async def t_recommend_restaurant(self, ctx: RunContext, meal: str, source: str, place_id: str = "",
                                     exclude_keywords: list[str] | None = None,
                                     exclude_place_ids: list[str] | None = None) -> dict:
        if meal not in MEALS:
            raise ToolError(f"meal 은 {MEALS} 중 하나여야 합니다.")
        if source == "room":
            candidates = self.store.list_restaurants(ctx.room)
            if not candidates:
                raise ToolError("이 방에 등록된 맛집이 없습니다. near_me 나 near_place 로 추천하거나 등록을 권하세요.")
        elif source == "near_me":
            if ctx.origin is None:
                raise ToolError("사용자 현재 위치가 없습니다. request_location 을 먼저 부르세요.")
            candidates = await self.maps.search_category(CATEGORY_RESTAURANT, ctx.origin, radius=1000)
        elif source == "near_place":
            center = self._place(place_id)
            candidates = await self.maps.search_category(CATEGORY_RESTAURANT, center.point, radius=1000)
        else:
            raise ToolError("source 는 room, near_me, near_place 중 하나여야 합니다.")

        words = [w for w in (exclude_keywords or []) if w]
        ids = set(exclude_place_ids or [])
        filtered = [p for p in candidates
                    if p.id not in ids and not any(w in p.name or w in p.category for w in words)]
        if not filtered:
            raise ToolError("조건에 맞는 식당이 없습니다.")
        place = food.pick_restaurant(filtered, self.store.recent_picks(ctx.room))
        self.store.record_pick(ctx.room, place.id)
        self.store.cache_places([place])
        ctx.cards.extend(outputs(food.recommend_reply(place, meal, nearby=source != "room")))
        return {"recommended": place_brief(place)}
