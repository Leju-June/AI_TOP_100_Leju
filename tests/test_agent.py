"""계획서의 시나리오 9개를 가짜 LLM 으로 돌려 에이전트 흐름(도구 호출, 멈춤·재개, 카드 조립)을 확인한다.

가짜 LLM 은 정해진 응답을 순서대로 돌려준다. 그래서 여기서는 LLM 의 판단이 아니라
그 판단을 실행하는 코드(도구 결과, 대화 구조, 저장·재개, 답장 카드)를 검증한다.
"""
import asyncio
import json

import pytest
from test_bot import NOW, YEONGTONG, FakeMaps, place

from eodiro.agent import Agent
from eodiro.handlers import Bot, LocationError, Message
from eodiro.llm import LLMError, LLMResponse
from eodiro.tools import AgentTools

MODEL, FAST = "main-model", "fast-model"


def tool(name, **inp):
    return ("tool", name, inp)


def say(text):
    return ("text", text)


class FakeLLM:
    """script 의 각 항목은 한 번의 응답: say(...) 하나, 또는 tool(...) 여러 개(+ 앞에 say 가능)."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = []  # (model, messages 사본)
        self.n = 0

    async def create(self, *, model, system, tools, messages):
        self.calls.append((model, json.loads(json.dumps(messages))))
        check_tool_results(messages)
        if not self.script:
            raise AssertionError("스크립트에 없는 LLM 호출")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        blocks = step if isinstance(step, list) else [step]
        content = []
        for b in blocks:
            if b[0] == "text":
                content.append({"type": "text", "text": b[1]})
            else:
                self.n += 1
                content.append({"type": "tool_use", "id": f"tu{self.n}", "name": b[1], "input": b[2]})
        stop = "tool_use" if any(b["type"] == "tool_use" for b in content) else "end_turn"
        return LLMResponse(stop, content)

    def tool_results(self, call_index):
        """call_index 번째 호출에 들어간 마지막 user 메시지의 tool_result 내용."""
        last = self.calls[call_index][1][-1]
        return {r["tool_use_id"]: r["content"] for r in last["content"]}


def check_tool_results(messages):
    """assistant 의 tool_use 마다 바로 다음 user 메시지에 같은 id 의 tool_result 가 있어야 한다."""
    for i, m in enumerate(messages):
        if m["role"] == "assistant" and isinstance(m["content"], list):
            ids = {b["id"] for b in m["content"] if b["type"] == "tool_use"}
            if ids:
                nxt = messages[i + 1]["content"]
                assert {r["tool_use_id"] for r in nxt} == ids


def make_bot(llm):
    from eodiro.store import Store
    store, maps, clock = Store(":memory:"), FakeMaps(), lambda: NOW
    agent = Agent(AgentTools(store, maps, clock), llm, model=MODEL, fast_model=FAST,
                  base_url="https://eodiro.test", clock=clock)
    return Bot(store, maps, "https://eodiro.test", clock=clock, agent=agent)


def run(coro):
    return asyncio.run(coro)


def send(bot, text, room="room1", user="u1"):
    return run(bot.handle_message(Message(text, room, user)))


def outs(response):
    return response["template"]["outputs"]


def texts(response):
    return [o["simpleText"]["text"] for o in outs(response) if "simpleText" in o]


def cards(response):
    return [next(iter(o.values())) for o in outs(response) if "simpleText" not in o]


def locate_req(response):
    for c in cards(response):
        for b in c.get("buttons", []):
            if "/locate?req=" in b.get("webLinkUrl", ""):
                return b["webLinkUrl"].split("req=")[1]
    raise AssertionError("위치 버튼 없음")


# ------------------------------ 시나리오 ------------------------------

def test_s1_remaining_route_after_location():
    llm = FakeLLM(
        tool("search_place", query="미금역"),
        tool("request_location", reason="미금역까지 남은 거리를 계산하려면 현재 위치가 필요해요."),
        tool("get_route", place_id="p-migeum", mode="대중교통"),
        say("미금역까지 약 25분 남았어요."),
    )
    bot = make_bot(llm)
    first = send(bot, "@어디로 미금역 가는 중인데 얼마나 남았어?")
    assert "현재 위치가 필요해요" in cards(first)[-1]["title"]
    assert [m for m, _ in llm.calls] == [FAST, MODEL]

    _, result = run(bot.handle_location(locate_req(first), YEONGTONG, "u1"))
    assert texts(result.response) == ["미금역까지 약 25분 남았어요."]
    route_card = cards(result.response)[-1]
    assert route_card["title"].startswith("🚉 미금역 수인분당선까지")
    assert "오후 12:25" in route_card["description"]
    assert result.summary == "미금역까지 약 25분 남았어요."
    assert llm.calls[2][0] == MODEL  # 재개 후에는 기본 모델


def test_s2_appointment_time_uses_route_arrival():
    llm = FakeLLM(
        tool("search_place", query="강남역"),
        tool("request_location", reason="도착 시각을 계산하려면 현재 위치가 필요해요."),
        tool("get_route", place_id="p-gangnam", mode="대중교통"),
        say("12시 25분 도착 예정이라 7시 약속까지 여유가 충분해요."),
    )
    bot = make_bot(llm)
    first = send(bot, "@어디로 7시까지 강남역인데 지금 출발하면 안 늦어?")
    assert "12:00" in llm.calls[0][1][-1]["content"]  # 현재 시각을 상황에 넣었는지

    run(bot.handle_location(locate_req(first), YEONGTONG, "u1"))
    resume_note = next(iter(llm.tool_results(2).values()))
    assert "위치를 받았습니다" in resume_note and "12:00" in resume_note
    route = json.loads(next(iter(llm.tool_results(3).values())))
    assert route["arrival"] == "12:25" and route["duration_min"] == 25


def test_s3_less_walking_route():
    llm = FakeLLM(
        tool("search_place", query="판교역"),
        tool("request_location", reason="경로를 찾으려면 현재 위치가 필요해요."),
        tool("get_route", place_id="p-pangyo", mode="대중교통", less_walking=True),
        say("걷는 거리가 짧은 버스 경로로 안내할게요."),
    )
    bot = make_bot(llm)
    first = send(bot, "@어디로 비 오니까 걷는 거 적게 판교 가는 법")
    _, result = run(bot.handle_location(locate_req(first), YEONGTONG, "u1"))
    route = json.loads(next(iter(llm.tool_results(3).values())))
    assert route["walk_m"] == 200 and route["duration_min"] == 40
    assert "걷는 거리가 가장 짧은" in cards(result.response)[-1]["description"]


def test_s4_recommend_excludes_keyword():
    llm = FakeLLM(
        tool("recommend_restaurant", meal="점심", source="room", exclude_keywords=["국밥"]),
        say("어제 국밥을 드셨으니 오늘은 김밥 어때요?"),
    )
    bot = make_bot(llm)
    bot.store.add_restaurant("room1", place("r1", "국밥집"), "u1")
    bot.store.add_restaurant("room1", place("r2", "김밥천국 영통점", "음식점 > 분식"), "u1")
    r = send(bot, "@어디로 오늘 점메추, 어제 국밥 먹었음")
    assert "김밥천국 영통점" in cards(r)[-1]["description"]
    assert bot.store.recent_picks("room1") == ["r2"]


def test_s5_food_near_destination_without_location():
    llm = FakeLLM(
        tool("search_place", query="강남역"),
        tool("recommend_restaurant", meal="저녁", source="near_place", place_id="p-gangnam"),
        say("강남역 근처에서 골라봤어요."),
    )
    r = send(make_bot(llm), "@어디로 강남 가는 길에 저녁 먹을 데 있어?")
    assert "근처식당" in cards(r)[-1]["description"]
    assert all("/locate" not in json.dumps(c) for c in cards(r))


def test_s6_another_place_uses_history():
    llm = FakeLLM(
        tool("recommend_restaurant", meal="저녁", source="room"),
        say("여기 어때요?"),
        tool("recommend_restaurant", meal="저녁", source="room", exclude_place_ids=["r1"]),
        say("그럼 여기는 어때요?"),
    )
    bot = make_bot(llm)
    bot.store.add_restaurant("room1", place("r1", "국밥집"), "u1")
    bot.store.add_restaurant("room1", place("r2", "김밥천국 영통점", "음식점 > 분식"), "u1")
    bot.store.record_pick("room1", "r2")  # 첫 추천이 r1 이 되도록
    first = send(bot, "@어디로 저녁 뭐 먹지")
    assert "국밥집" in cards(first)[-1]["description"]

    second = send(bot, "@어디로 거기 말고 다른 데")
    assert "김밥천국" in cards(second)[-1]["description"]
    history = llm.calls[2][1]
    assert history[0] == {"role": "user", "content": "저녁 뭐 먹지"}
    assert history[1] == {"role": "assistant", "content": "여기 어때요?"}


def test_s7_add_recent_pick():
    llm = FakeLLM(
        tool("add_restaurant", place_id="n1"),
        say("우리 방 맛집에 넣었어요."),
    )
    bot = make_bot(llm)
    bot.store.cache_places([place("n1", "근처식당")])
    bot.store.record_pick("room1", "n1")
    r = send(bot, "@어디로 아까 그 집 우리 맛집에 넣어줘")
    assert "근처식당(place_id: n1)" in llm.calls[0][1][-1]["content"]  # 최근 추천을 상황에 넣었는지
    assert "추가 완료" in cards(r)[-1]["title"]
    assert [p.id for p in bot.store.list_restaurants("room1")] == ["n1"]


def test_s8_out_of_scope_answers_without_tools():
    llm = FakeLLM(say("날씨는 알려드리지 못해요. 목적지까지 남은 시간이나 메뉴 추천은 도와드릴 수 있어요."))
    r = send(make_bot(llm), "@어디로 내일 날씨 어때?")
    assert texts(r)[0].startswith("날씨는 알려드리지 못해요")
    assert cards(r) == [] and len(llm.calls) == 1


def test_s9_ambiguous_destination_asks_then_continues():
    llm = FakeLLM(
        tool("search_place", query="홍대"),
        tool("ask_user", question="어느 홍대를 말하는 거예요?",
             options=["홍익대학교 서울캠퍼스", "홍대입구역 2호선"]),
        tool("request_location", reason="홍대입구역까지 경로를 찾으려면 현재 위치가 필요해요."),
        tool("get_route", place_id="p-hongdae", mode="대중교통"),
        say("홍대입구역까지 약 25분 걸려요."),
    )
    bot = make_bot(llm)
    first = send(bot, "@어디로 홍대 가는 길 알려줘")
    items = cards(first)[-1]["items"]
    assert [i["messageText"] for i in items] == ["홍익대학교 서울캠퍼스", "홍대입구역 2호선"]

    second = send(bot, "홍대입구역 2호선", user="u2")  # 같은 방의 다른 사람이 골라도 이어진다
    assert "사용자가 '홍대입구역 2호선'를 골랐습니다." in llm.tool_results(2).values()
    assert bot.store.get_pending("room1") is None

    _, result = run(bot.handle_location(locate_req(second), YEONGTONG, "u1"))  # 위치는 처음 요청한 사람
    assert cards(result.response)[-1]["title"].startswith("🚉 홍대입구역 2호선까지")


# ------------------------------ 안전장치 ------------------------------

def test_remove_needs_confirmation_by_requester():
    llm = FakeLLM(tool("remove_restaurant", place_id="r1"), say("확인 버튼을 눌러주세요."))
    bot = make_bot(llm)
    bot.store.add_restaurant("room1", place("r1", "국밥집"), "u1")
    r = send(bot, "@어디로 국밥집 목록에서 빼줘")
    assert [b["label"] for b in cards(r)[-1]["buttons"]] == ["삭제 확정", "취소"]
    assert len(bot.store.list_restaurants("room1")) == 1  # 아직 안 지움

    assert "요청한 사람만" in texts(send(bot, "삭제 확정", user="u2"))[0]
    assert "삭제 완료" in cards(send(bot, "삭제 확정", user="u1"))[-1]["title"]
    assert bot.store.list_restaurants("room1") == []


def test_cancel_clears_pending():
    llm = FakeLLM(tool("remove_restaurant", place_id="r1"), say("확인 버튼을 눌러주세요."))
    bot = make_bot(llm)
    bot.store.add_restaurant("room1", place("r1", "국밥집"), "u1")
    send(bot, "@어디로 국밥집 빼줘")
    assert texts(send(bot, "취소")) == ["취소했어요."]
    assert len(bot.store.list_restaurants("room1")) == 1


def test_button_text_skips_llm():
    llm = FakeLLM()
    r = send(make_bot(llm), "@어디로 맛집 리스트")
    assert "아직 등록된 맛집이 없어요" in cards(r)[-1]["title"]
    assert llm.calls == []


def test_llm_failure_falls_back_to_parser():
    llm = FakeLLM(LLMError("network"))
    r = send(make_bot(llm), "@어디로 미금역")
    assert "내 위치 보내기" in cards(r)[-1]["buttons"][0]["label"]  # 기존 파서의 길찾기 요청


def test_route_tool_without_location_returns_error():
    llm = FakeLLM(tool("get_route", place_id="p-migeum", mode="대중교통"), say("위치가 필요해요."))
    send(make_bot(llm), "@어디로 미금역")
    assert "request_location" in next(iter(llm.tool_results(1).values()))


def test_pause_hides_model_narration():
    # 실측(2026-10-28): 도구 호출 앞에 붙은 영어 혼잣말이 채팅에 그대로 나왔다.
    llm = FakeLLM([say("Same station, so I use the first result."), tool("request_location", reason="위치가 필요해요.")])
    r = send(make_bot(llm), "@어디로 미금역 얼마나 남았어")
    assert texts(r) == [] and "현재 위치가 필요해요" in cards(r)[-1]["title"]


def test_only_requester_can_send_agent_location():
    llm = FakeLLM(tool("request_location", reason="위치가 필요해요."))
    bot = make_bot(llm)
    first = send(bot, "@어디로 미금역 얼마나 남았어", user="u1")
    with pytest.raises(LocationError) as e:
        run(bot.handle_location(locate_req(first), YEONGTONG, "u2"))
    assert e.value.status == 403
