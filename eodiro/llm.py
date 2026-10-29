"""LLM 호출을 감싸는 얇은 층. 에이전트는 이 인터페이스만 알고, 테스트에서는 가짜 LLM 으로 바꾼다.

응답의 content 는 SDK 객체가 아니라 dict 목록으로 돌려준다. 위치·선택을 기다리는 동안
대화 상태를 SQLite 에 JSON 으로 저장했다가 그대로 다시 보내야 하기 때문이다.
"""
from dataclasses import dataclass
from typing import Protocol

import anthropic

# 서버 측 fallback(거절 시 다른 모델로 재시도)을 켜는 모델. Haiku 5.5 는 지원하지 않아 보내면 안 된다.
FALLBACK_MODELS = {"claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    pass


@dataclass
class LLMResponse:
    stop_reason: str
    content: list[dict]

    @property
    def text(self) -> str:
        return "\n".join(b["text"] for b in self.content if b.get("type") == "text").strip()

    @property
    def tool_uses(self) -> list[dict]:
        return [b for b in self.content if b.get("type") == "tool_use"]


class LLMClient(Protocol):
    async def create(self, *, model: str, system: str, tools: list[dict], messages: list[dict]) -> LLMResponse: ...


class AnthropicLLM:
    def __init__(self, effort: str = "low", max_tokens: int = 4000, client: anthropic.AsyncAnthropic | None = None):
        # 자격 증명은 ANTHROPIC_API_KEY 또는 `ant auth login` 프로필에서 SDK 가 찾는다.
        self.client = client or anthropic.AsyncAnthropic(timeout=60, max_retries=1)
        self.effort = effort
        self.max_tokens = max_tokens

    async def create(self, *, model: str, system: str, tools: list[dict], messages: list[dict]) -> LLMResponse:
        params = dict(model=model, max_tokens=self.max_tokens, system=system, tools=tools, messages=messages,
                      output_config={"effort": self.effort})
        try:
            if model in FALLBACK_MODELS:
                resp = await self.client.beta.messages.create(**params, betas=[FALLBACK_BETA], fallbacks="default")
            else:
                resp = await self.client.messages.create(**params)
        except anthropic.APIError as e:
            raise LLMError(str(e)) from e
        if resp.stop_reason == "refusal":
            raise LLMError("refusal")
        return LLMResponse(resp.stop_reason, [b.to_dict() for b in resp.content])
