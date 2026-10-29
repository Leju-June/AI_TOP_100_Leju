"""기능 1: 현재 위치 -> 목적지 남은 동선 계산과 답장 구성."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import kakao_bot as kb
from .commands import Mode
from .kakao_map import KakaoMapClient, Place, Point, map_link

ORIGIN_NAME = "내 위치"

# 요청 수단별 선호 경로 타입 (앞에서부터 우선, 없으면 다음 후보)
TRANSIT_PREFERENCE = {
    Mode.BUS: ["BUS", "BUS_AND_SUBWAY"],
    Mode.SUBWAY: ["SUBWAY", "BUS_AND_SUBWAY"],
    Mode.TRANSIT: [],
}
STEP_ICON = {"BUS": "🚌", "SUBWAY": "🚇"}
MODE_ICON = {Mode.TRANSIT: "🚉", Mode.BUS: "🚌", Mode.SUBWAY: "🚇", Mode.WALK: "🚶", Mode.CAR: "🚗"}


@dataclass
class RouteResult:
    mode: Mode
    distance_m: int
    duration_s: int
    link: str
    steps: list[str] = field(default_factory=list)
    note: str = ""
    walk_m: int | None = None  # 대중교통 경로 중 도보 구간 합계


class RouteNotFound(Exception):
    pass


def pick_transit_route(routes: list[dict], mode: Mode) -> tuple[dict, str]:
    """API 가 추천 순으로 준 경로 중 요청 수단에 맞는 첫 경로를 고른다. (route, 안내 문구)"""
    for wanted in TRANSIT_PREFERENCE[mode]:
        for r in routes:
            if r["properties"]["type"] == wanted:
                note = "" if wanted == TRANSIT_PREFERENCE[mode][0] else f"{mode.value}만 타는 경로가 없어 환승 경로로 안내해요."
                return r, note
    note = f"{mode.value} 경로가 없어 대중교통 추천 경로로 안내해요." if TRANSIT_PREFERENCE[mode] else ""
    return routes[0], note


def walk_distance(route: dict) -> int:
    return sum(s["properties"].get("distance", 0) for s in route.get("steps", [])
               if s["properties"]["type"] == "WALKING")


def summarize_steps(route: dict) -> list[str]:
    lines = []
    for step in route.get("steps", []):
        p = step["properties"]
        if p["type"] in STEP_ICON:
            lines.append(f"{STEP_ICON[p['type']]} {p.get('guidance', '')}")
    return lines


async def find_route(client: KakaoMapClient, origin: Point, dest: Place, mode: Mode,
                     less_walking: bool = False) -> RouteResult:
    if mode in (Mode.TRANSIT, Mode.BUS, Mode.SUBWAY):
        data = await client.transit_route(origin, dest.point)
        if data.get("status") == "OK" and data.get("routes"):
            route, note = pick_transit_route(data["routes"], mode)
            if less_walking:
                fewest = min(data["routes"], key=walk_distance)
                if walk_distance(fewest) < walk_distance(route):
                    route, note = fewest, "걷는 거리가 가장 짧은 경로로 안내해요."
            p = route["properties"]
            return RouteResult(mode, p["totalDistance"], p["totalTime"],
                               map_link("traffic", ORIGIN_NAME, origin, dest.name, dest.point),
                               summarize_steps(route), note, walk_distance(route))
        # 너무 가깝거나 대중교통 경로가 없으면 도보로 대체
        result = await find_route(client, origin, dest, Mode.WALK)
        result.note = "대중교통 경로가 없어 도보 경로로 안내해요."
        return result

    if mode == Mode.WALK:
        data = await client.walk_route(origin, dest.point)
        if data.get("status") != "OK":
            raise RouteNotFound(data.get("status", "UNKNOWN"))
        p = data["route"]["properties"]
        return RouteResult(mode, p["totalDistance"], p["totalTime"],
                           map_link("walk", ORIGIN_NAME, origin, dest.name, dest.point))

    data = await client.car_route(origin, dest.point)
    routes = data.get("routes") or []
    if not routes or routes[0].get("result_code") != 0:
        raise RouteNotFound(routes[0].get("result_msg", "UNKNOWN") if routes else "UNKNOWN")
    s = routes[0]["summary"]
    return RouteResult(mode, s["distance"], s["duration"],
                       map_link("car", ORIGIN_NAME, origin, dest.name, dest.point))


def format_distance(m: int) -> str:
    return f"{m}m" if m < 1000 else f"{m / 1000:.1f}km"


def format_duration(sec: int) -> str:
    minutes = max(1, round(sec / 60))
    h, m = divmod(minutes, 60)
    return f"{h}시간 {m}분" if h else f"{m}분"


def format_clock(t: datetime) -> str:
    ampm = "오전" if t.hour < 12 else "오후"
    hour = t.hour % 12 or 12
    return f"{ampm} {hour}:{t.minute:02d}"


def route_reply(dest: Place, requested: Mode, result: RouteResult, now: datetime) -> dict:
    arrival = now + timedelta(seconds=result.duration_s)
    lines = [
        f"📏 남은 거리: {format_distance(result.distance_m)}",
        f"⏱ 남은 시간: 약 {format_duration(result.duration_s)}",
        f"🕒 도착 예정: {format_clock(arrival)}",
    ]
    if result.steps:
        lines.append("")
        lines.extend(result.steps[:4])
    if result.note:
        lines.append(f"\nℹ️ {result.note}")
    title = f"{MODE_ICON[result.mode]} {dest.name}까지 ({requested.value})"
    return kb.skill_response(kb.text_card(title, "\n".join(lines), [
        kb.link_button("카카오맵 길찾기", result.link),
    ]))


def location_request_reply(dest: Place, mode: Mode, locate_url: str) -> dict:
    desc = (f"📍 {dest.address}\n\n"
            "아래 버튼을 눌러 현재 위치를 보내주면 남은 거리·시간·도착 예정 시각을 이 방에 알려드려요.")
    return kb.skill_response(kb.text_card(f"{MODE_ICON[mode]} {dest.name}까지 ({mode.value})", desc, [
        kb.link_button("내 위치 보내기", locate_url),
    ]))
