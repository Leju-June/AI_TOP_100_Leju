"""기능 2: 방별 맛집 목록 관리와 점심/저녁 메뉴 추천."""
import random

from . import kakao_bot as kb
from .kakao_map import Place

CMD_LIST = "맛집 리스트"
CMD_ADD_LAST = "맛집 추가"  # 방금 추천한 곳을 추가


def cmd_recommend(meal: str, nearby: bool = False) -> str:
    short = "점메추" if meal == "점심" else "저메추"
    return f"아무대나 {short}" if nearby else short


def pick_restaurant(candidates: list[Place], recent_ids: list[str], rng: random.Random | None = None) -> Place:
    """추천 알고리즘 자리. 지금은 최근 추천한 곳을 빼고 무작위로 고른다."""
    rng = rng or random.Random()
    fresh = [p for p in candidates if p.id not in recent_ids]
    return rng.choice(fresh or candidates)


def choose_search_result(query: str, results: list[Place]) -> Place | None:
    """검색 결과가 하나이거나 이름이 정확히 같으면 바로 확정, 아니면 None(후보 선택 필요)."""
    if len(results) == 1:
        return results[0]
    exact = [p for p in results if p.name.replace(" ", "") == query.replace(" ", "")]
    return exact[0] if len(exact) == 1 else None


def is_food_place(p: Place) -> bool:
    return p.category.startswith(("음식점", "카페"))


def added_reply(place: Place, is_new: bool, total: int) -> dict:
    title = f"✅ {place.name} 추가 완료" if is_new else f"👌 {place.name}은(는) 이미 있어요"
    desc = f"{place.short_category} · {place.address}\n\n지금 우리 방 맛집은 {total}곳이에요."
    return kb.skill_response(kb.text_card(title, desc, [
        kb.message_button(CMD_LIST),
        kb.link_button("카카오맵에서 보기", place.url),
    ]))


def candidates_reply(query: str, places: list[Place]) -> dict:
    # 누르면 식당 이름이 채팅으로 올라오고, Bot 이 대기 중인 후보와 이름을 맞춰 추가한다.
    items = [kb.list_item(p.name, f"{p.short_category} · {p.address}", send_title=True)
             for p in places[:5]]
    return kb.skill_response(kb.list_card(f"'{query}' 중 어디를 추가할까요?", items, [
        kb.link_button("카카오맵에서 찾기", f"https://map.kakao.com/?q={query}"),
    ]))


def list_reply(places: list[Place]) -> dict:
    if not places:
        return kb.skill_response(kb.text_card(
            "📋 아직 등록된 맛집이 없어요",
            "'@어디로 맛집 추가 식당이름'으로 우리 방 맛집을 등록해보세요.\n등록 전에는 '@어디로 아무대나 점메추'로 근처 식당을 추천받을 수 있어요.",
            [kb.message_button(cmd_recommend("점심", nearby=True))],
        ))
    lines = [f"{i}. {p.name} · {p.short_category}" for i, p in enumerate(places, 1)]
    lines.append("\n삭제: '@어디로 맛집 삭제 번호'")
    title = f"📋 우리 방 맛집 {len(places)}곳"
    buttons = [kb.message_button(cmd_recommend("점심")),
               kb.message_button(cmd_recommend("저녁"))]
    body = "\n".join(lines)
    if len(title) + len(body) <= 400:
        return kb.skill_response(kb.text_card(title, body, buttons))
    return kb.skill_response(kb.simple_text(f"{title}\n\n{body}"), kb.text_card(title, "메뉴를 골라볼까요?", buttons))


def removed_reply(place: Place) -> dict:
    return kb.skill_response(kb.text_card(f"🗑 {place.name} 삭제 완료", "목록에서 뺐어요.", [
        kb.message_button(CMD_LIST),
    ]))


def recommend_reply(place: Place, meal: str, nearby: bool) -> dict:
    icon = "🍚" if meal == "점심" else "🌙"
    where = f"📍 {place.distance_m}m · " if place.distance_m is not None else "📍 "
    desc = f"{place.name}\n{place.short_category}\n{where}{place.address}"
    third = (kb.message_button(CMD_ADD_LAST) if nearby
             else kb.message_button(CMD_LIST))
    return kb.skill_response(kb.text_card(f"{icon} 오늘 {meal}은 여기 어때요?", desc, [
        kb.link_button("카카오맵에서 보기", place.url),
        kb.message_button(cmd_recommend(meal, nearby)),
        third,
    ]))


def nearby_request_reply(meal: str, locate_url: str) -> dict:
    return kb.skill_response(kb.text_card(
        f"🎲 아무대나 {meal} 추천",
        "아래 버튼으로 현재 위치를 보내주면 근처 1km 안에서 골라드릴게요.",
        [kb.link_button("내 위치 보내기", locate_url)],
    ))
