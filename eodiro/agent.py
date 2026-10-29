"""'어디로' 에이전트: LLM 이 상황을 해석하고 도구를 골라 쓰는 루프.

- 새 메시지의 첫 호출은 빠른 모델(도구 선택), 도구 결과를 받은 뒤의 호출은 기본 모델(설명 문장)이 맡는다.
- 위치나 선택이 필요하면 대화 상태를 저장하고 버튼을 보낸 뒤 멈춘다. 답이 오면 같은 대화에
  도구 결과로 이어 붙여 재개한다(대화는 덧붙이기만 하고 고치지 않는다).
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from . import commands as c
from . import kakao_bot as kb
from .llm import AnthropicLLM, LLMClient
from .store import LocationRequest, Pending, Store
from .tools import CMD_CANCEL, PAUSE, TOOLS, AgentTools, RunContext

log = logging.getLogger(__name__)

KIND_AGENT = "agent"
WEEKDAYS = "월화수목금토일"

SYSTEM_PROMPT = """너는 카카오톡 단톡방 봇 '어디로'다. 방 사람들이 이동과 식사를 정하도록 돕는다.
할 수 있는 일은 두 가지다.
1. 남은 동선 안내: 현재 위치에서 목적지까지 남은 거리, 남은 시간, 도착 예정 시각, 카카오맵 길찾기
2. 점심·저녁 식당 추천: 이 방에 등록한 맛집 목록, 내 위치 근처, 특정 장소 근처에서 고르기. 맛집 등록·삭제도 한다.

규칙
- 장소, 거리, 시간, 도착 시각 같은 사실은 도구 결과에서만 가져온다. 숫자를 지어내지 않는다.
- 사용자 현재 위치는 메시지에 오지 않는다. 위치가 필요하면 request_location 을 부르고, 위치를 받은 뒤 이어서 처리한다.
- 목적지가 "강남 가는 길에"처럼 경유지·근처를 뜻하면 그 장소를 search_place 로 찾아 near_place 로 추천할 수 있다. 이때는 위치가 필요 없다.
- 검색 결과가 여러 곳이고 어느 곳인지 분명하지 않으면 ask_user 로 되묻는다. 하나가 분명하면 묻지 않는다.
- 같은 역의 다른 노선이나 출구처럼 사실상 같은 곳인 후보는 되묻지 말고 첫 번째 결과를 쓴다.
- 되물어야 하면 위치를 요청하기 전에 먼저 묻는다. 목적지를 정한 뒤에 위치를 요청한다.
- 약속 시각이 있으면 get_route 의 도착 예정 시각과 비교해 몇 분 여유 또는 지각인지 말한다.
- 할 수 없는 요청(날씨, 예약, 결제 등)은 도구를 부르지 말고 할 수 있는 일을 한 문장으로 안내한다.
- 답장 문장은 한국어 존댓말로 1~2문장만 쓴다. 카드에 이미 나오는 거리·주소를 다시 늘어놓지 않는다.
- 마크다운 문법(굵게, 목록 기호)을 쓰지 않는다. 카카오톡에서는 그대로 보인다."""


class AgentError(Exception):
    pass


@dataclass
class AgentResult:
    response: dict
    summary: str  # 위치 전송 페이지에 보여줄 한 줄


def tool_result(tool_use_id: str, content: str) -> dict:
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}


class Agent:
    def __init__(self, tools: AgentTools, llm: LLMClient, *, model: str, fast_model: str, base_url: str,
                 clock: Callable[[], datetime], max_steps: int = 6, history_turns: int = 3):
        self.tools = tools
        self.store: Store = tools.store
        self.llm = llm
        self.model = model
        self.fast_model = fast_model
        self.base_url = base_url
        self.clock = clock
        self.max_steps = max_steps
        self.history_turns = history_turns

    # ------------------------------ 진입점 ------------------------------

    async def handle(self, text: str, room: str, group_key: str, user_key: str, is_channel: bool) -> dict:
        body = c.MENTION_RE.sub("", text, count=1).strip()
        ctx = RunContext(room, group_key, user_key, is_channel)
        messages = self._history(room) + [{"role": "user", "content": self._user_content(room, body)}]
        result = await self._loop(ctx, messages, body, fresh=True)
        return result.response

    async def resume_location(self, req: LocationRequest, origin) -> AgentResult:
        state = req.payload
        ctx = RunContext(req.group_key or req.user_key, req.group_key, req.user_key, req.is_channel, origin)
        note = f"사용자 현재 위치를 받았습니다. 지금은 {self._now_text()}입니다. 위치가 필요한 도구를 이어서 부르세요."
        return await self._resume(ctx, state, note)

    async def resume_answer(self, pending: Pending, answer: str) -> dict:
        state = pending.data
        ctx = RunContext(pending.group_key, state["group_key"], pending.user_key, state["is_channel"])
        result = await self._resume(ctx, state, f"사용자가 '{answer}'를 골랐습니다.")
        return result.response

    # ------------------------------ 루프 ------------------------------

    async def _resume(self, ctx: RunContext, state: dict, note: str) -> AgentResult:
        messages = state["messages"] + [{"role": "user", "content": [
            *state["results"], tool_result(state["tool_use_id"], note)]}]
        return await self._loop(ctx, messages, state["user_text"], fresh=False)

    async def _loop(self, ctx: RunContext, messages: list[dict], user_text: str, fresh: bool) -> AgentResult:
        for step in range(self.max_steps):
            model = self.fast_model if fresh and step == 0 else self.model
            resp = await self.llm.create(model=model, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages)
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use" or not resp.tool_uses:
                return self._finish(ctx, resp.text, user_text if fresh else None)

            results, pause_id = [], None
            for tu in resp.tool_uses:
                log.info("도구 호출 %s %s", tu["name"], tu["input"])
                out = await self.tools.run(ctx, tu["name"], tu.get("input") or {})
                if out is PAUSE:
                    pause_id = tu["id"]
                else:
                    results.append(tool_result(tu["id"], out))
            if pause_id:
                return self._pause(ctx, messages, results, pause_id, user_text)
            messages.append({"role": "user", "content": results})
        raise AgentError("도구 호출 횟수 초과")

    def _finish(self, ctx: RunContext, text: str, user_text: str | None) -> AgentResult:
        """user_text 가 None 이면 재개된 대화라 사용자 말은 멈출 때 이미 기록했다."""
        out = ([kb.simple_text(text)] if text else []) + ctx.cards[-2:]
        if not out:
            out = [kb.simple_text("무엇을 도와드릴까요? 목적지나 메뉴 고민을 말해주세요.")]
        self._remember(ctx.room, user_text, text or "(카드로 답함)")
        return AgentResult(kb.skill_response(*out[-3:]), (text or "결과를 채팅방에 보냈어요.").split("\n")[0])

    def _pause(self, ctx: RunContext, messages: list[dict], results: list[dict], pause_id: str,
               user_text: str) -> AgentResult:
        # 도구를 부르며 쓴 문장은 모델의 혼잣말일 때가 많아 보여주지 않는다. 카드에 이유가 들어간다.
        state = {"messages": messages, "results": results, "tool_use_id": pause_id, "user_text": user_text,
                 "group_key": ctx.group_key, "is_channel": ctx.is_channel}
        now = self.clock().timestamp()
        if ctx.pause["kind"] == "location":
            req_id = self.store.create_location_request(KIND_AGENT, state, ctx.group_key, ctx.user_key,
                                                        ctx.is_channel, now)
            card = kb.text_card("📍 현재 위치가 필요해요",
                                f"{ctx.pause['reason']}\n\n아래 버튼으로 위치를 보내주면 이어서 알려드릴게요. "
                                "요청한 사람만 보낼 수 있고 10분 뒤 만료돼요.",
                                [kb.link_button("내 위치 보내기", f"{self.base_url}/locate?req={req_id}")])
            remembered = "(위치 요청 버튼을 보냄)"
        else:
            options = ctx.pause["options"]
            self.store.set_pending(ctx.room, "ask", ctx.user_key, {**state, "options": options}, now)
            card = kb.list_card(ctx.pause["question"], [kb.list_item(o, send_title=True) for o in options],
                                [kb.message_button(CMD_CANCEL)])  # ListCard 는 buttons 가 필수
            remembered = f"(되물음: {ctx.pause['question']} {', '.join(options)})"
        self._remember(ctx.room, user_text, remembered)
        return AgentResult(kb.skill_response(*ctx.cards[-1:], card), remembered)

    # ------------------------------ 프롬프트 ------------------------------

    def _now_text(self) -> str:
        now = self.clock()
        return f"{now:%Y-%m-%d}({WEEKDAYS[now.weekday()]}) {now:%H:%M} KST"

    def _user_content(self, room: str, body: str) -> str:
        recent = [p for p in (self.store.get_cached_place(pid) for pid in self.store.recent_picks(room)) if p]
        lines = [
            "[상황]",
            f"현재 시각: {self._now_text()}",
            f"이 방 맛집: {len(self.store.list_restaurants(room))}곳",
            "최근 추천한 곳: " + (", ".join(f"{p.name}(place_id: {p.id})" for p in recent) or "없음"),
            "",
            "[메시지]",
            body or "(내용 없이 부름)",
        ]
        return "\n".join(lines)

    def _history(self, room: str) -> list[dict]:
        msgs = [{"role": role, "content": text}
                for role, text in self.store.recent_history(room, self.history_turns * 2)]
        while msgs and msgs[0]["role"] != "user":  # 대화는 user 로 시작해야 한다
            msgs.pop(0)
        return msgs

    @classmethod
    def from_config(cls, cfg, store: Store, maps, clock: Callable[[], datetime],
                    llm: LLMClient | None = None) -> "Agent | None":
        if not cfg.agent_enabled:
            return None
        return cls(AgentTools(store, maps, clock), llm or AnthropicLLM(effort=cfg.agent_effort),
                   model=cfg.agent_model, fast_model=cfg.agent_fast_model,
                   base_url=cfg.public_base_url, clock=clock)

    def _remember(self, room: str, user_text: str | None, bot_text: str) -> None:
        if user_text is not None:
            self.store.add_history(room, "user", user_text or "(부름)")
        self.store.add_history(room, "assistant", bot_text)
