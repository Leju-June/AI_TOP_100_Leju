"""카카오맵 API 를 흉내 낸 가짜 클라이언트로 봇 흐름을 확인한다."""
import asyncio
from datetime import datetime

import pytest

from eodiro.config import KST
from eodiro.handlers import Bot, LocationError, Message
from eodiro.kakao_map import Place, Point
from eodiro.store import Store

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=KST)
YEONGTONG = Point(127.0711, 37.2513)


def place(pid, name, cat="음식점 > 한식 > 국밥", x=127.07, y=37.25, dist=None):
    return Place(pid, name, cat, "경기 수원시 영통구", Point(x, y), f"http://place.map.kakao.com/{pid}", dist)


MIGEUM = place("p-migeum", "미금역 수인분당선", "교통,수송 > 지하철역", 127.1100, 37.3500)


class FakeMaps:
    def __init__(self):
        self.keyword = {
            "미금역": [MIGEUM],
            "국밥집": [place("r1", "국밥집")],
            "김밥": [place("r2", "김밥천국 영통점", "음식점 > 분식"), place("r3", "고봉민김밥 영통점", "음식점 > 분식")],
        }

    async def search_keyword(self, query, *, category=None, near=None, size=5):
        return self.keyword.get(query, [])[:size]

    async def search_category(self, category, near, *, radius=1000, size=15):
        return [place("n1", "근처식당", dist=120), place("n2", "근처식당2", dist=300)]

    async def transit_route(self, start, end):
        def route(rtype, time, guidance):
            return {"properties": {"type": rtype, "totalDistance": 15000, "totalTime": time, "transfers": 0},
                    "steps": [{"properties": {"type": rtype, "guidance": guidance}}]}
        return {"status": "OK", "routes": [
            route("SUBWAY", 1500, "수인분당선 (영통 > 미금)"),
            route("BUS", 2400, "직행 5000 (영통역 > 미금역)"),
        ]}

    async def walk_route(self, start, end):
        return {"status": "OK", "route": {"properties": {"totalDistance": 800, "totalTime": 660}}}

    async def car_route(self, start, end):
        return {"routes": [{"result_code": 0, "summary": {"distance": 16000, "duration": 1200}}]}


@pytest.fixture
def bot():
    return Bot(Store(":memory:"), FakeMaps(), "https://eodiro.test", clock=lambda: NOW)


def run(coro):
    return asyncio.run(coro)


def msg(text, room="room1", user="u1"):
    return Message(text, room, user)


def card(response):
    out = response["template"]["outputs"][-1]
    return next(iter(out.values()))


def req_id_of(response):
    url = card(response)["buttons"][0]["webLinkUrl"]
    return url.split("req=")[1]


def test_route_flow_bus(bot):
    first = run(bot.handle_message(msg("@어디로 미금역까지 버스로")))
    assert "내 위치 보내기" in card(first)["buttons"][0]["label"]
    req, result = run(bot.handle_location(req_id_of(first), YEONGTONG, "u1"))
    c = card(result.response)
    assert c["title"].startswith("🚌 미금역 수인분당선까지 (버스)")
    assert "40분" in c["description"]          # 버스 경로(2400초)를 골랐는지
    assert "오후 12:40" in c["description"]     # 도착 예정 시각
    assert c["buttons"][0]["webLinkUrl"].startswith("https://map.kakao.com/link/by/traffic/")
    with pytest.raises(LocationError) as e:     # 같은 요청 재사용 불가
        run(bot.handle_location(req.id, YEONGTONG, "u1"))
    assert e.value.status == 409


def test_route_only_requester_can_send_location(bot):
    first = run(bot.handle_message(msg("@어디로 미금역", user="u1")))
    with pytest.raises(LocationError) as e:
        run(bot.handle_location(req_id_of(first), YEONGTONG, "someone-else"))
    assert e.value.status == 403


@pytest.mark.parametrize("text, expect", [("@어디로 미금역 걸어서", "11분"), ("@어디로 미금역 차로", "20분")])
def test_route_walk_and_car(bot, text, expect):
    first = run(bot.handle_message(msg(text)))
    _, result = run(bot.handle_location(req_id_of(first), YEONGTONG, "u1"))
    assert expect in card(result.response)["description"]


def test_unknown_destination(bot):
    r = run(bot.handle_message(msg("@어디로 없는곳")))
    assert "찾지 못했어요" in r["template"]["outputs"][0]["simpleText"]["text"]


def test_restaurant_add_list_recommend_remove(bot):
    added = card(run(bot.handle_message(msg("@어디로 맛집 추가 국밥집"))))
    assert "추가 완료" in added["title"]
    # 단톡방에서는 버튼 이름이 그대로 채팅으로 올라오므로 이름과 보낼 문장이 같아야 한다.
    assert added["buttons"][0]["label"] == added["buttons"][0]["messageText"] == "맛집 리스트"

    again = card(run(bot.handle_message(msg("@어디로 맛집 추가 국밥집"))))
    assert "이미 있어요" in again["title"]

    # 후보가 여러 개면 리스트 카드로 고르게 하고, 누르면 올라오는 식당 이름으로 추가된다.
    cands = card(run(bot.handle_message(msg("@어디로 맛집 추가 김밥"))))
    pick = cands["items"][1]["title"]
    assert pick == cands["items"][1]["messageText"] == "고봉민김밥 영통점"
    assert "추가 완료" in card(run(bot.handle_message(msg(pick))))["title"]

    listed = card(run(bot.handle_message(msg("@어디로 리스트"))))
    assert "2곳" in listed["title"] and "고봉민김밥" in listed["description"]

    rec = card(run(bot.handle_message(msg("@어디로 점메추"))))
    assert rec["title"] == "🍚 오늘 점심은 여기 어때요?"

    removed = card(run(bot.handle_message(msg("@어디로 맛집 삭제 1"))))
    assert "국밥집" in removed["title"]
    assert len(bot.store.list_restaurants("room1")) == 1


def test_lists_are_per_room(bot):
    run(bot.handle_message(msg("@어디로 맛집 추가 국밥집", room="A")))
    assert bot.store.list_restaurants("B") == []


def test_recommend_without_list_suggests_nearby(bot):
    r = card(run(bot.handle_message(msg("@어디로 저메추"))))
    assert "아직 등록된 맛집이 없어요" in r["title"]


def test_nearby_recommend_and_add(bot):
    first = run(bot.handle_message(msg("@어디로 아무대나 점메추")))
    _, result = run(bot.handle_location(req_id_of(first), YEONGTONG, "anyone"))
    c = card(result.response)
    assert "근처식당" in c["description"]
    assert c["buttons"][1]["label"] == "아무대나 점메추"   # 다른 곳 추천
    add_text = c["buttons"][2]["label"]
    assert add_text == "맛집 추가"
    assert "추가 완료" in card(run(bot.handle_message(msg(add_text))))["title"]
    assert "근처식당" in bot.store.list_restaurants("room1")[0].name


def test_expired_location_request(bot):
    first = run(bot.handle_message(msg("@어디로 미금역")))
    bot.clock = lambda: datetime(2026, 10, 28, 13, 0, tzinfo=KST)
    with pytest.raises(LocationError) as e:
        run(bot.handle_location(req_id_of(first), YEONGTONG, "u1"))
    assert e.value.status == 410
