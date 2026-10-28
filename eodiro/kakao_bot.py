"""카카오톡 봇 API 클라이언트와 말풍선(SkillResponse) 빌더.

명세: kakao_챗봇설명서/REST API.md
"""
import logging

import httpx

log = logging.getLogger(__name__)

KAKAO_API_URL = "https://kapi.kakao.com"


# ----------------------------- 말풍선 빌더 -----------------------------

def skill_response(*outputs: dict) -> dict:
    """outputs 는 최소 1개, 최대 3개."""
    return {"version": "2.0", "template": {"outputs": list(outputs[:3])}}


def simple_text(text: str) -> dict:
    return {"simpleText": {"text": text[:1000]}}


def text_card(title: str, description: str, buttons: list[dict]) -> dict:
    # 단일형 TextCard: title 50자, title+description 400자, 버튼 최대 3개
    title = title[:50]
    description = description[: max(0, 400 - len(title))]
    return {"textCard": {"title": title, "description": description, "buttons": buttons[:3]}}


def list_card(header: str, items: list[dict], buttons: list[dict]) -> dict:
    return {"listCard": {"header": {"title": header}, "items": items[:5], "buttons": buttons[:3]}}


def list_item(title: str, description: str = "", send_title: bool = False, link: str | None = None) -> dict:
    item = {"title": title}
    if description:
        item["description"] = description
    if send_title:
        # 버튼과 마찬가지로 누르면 제목이 그대로 채팅으로 올라간다고 보고 같은 문장을 보낸다.
        item["action"] = "message"
        item["messageText"] = title
    elif link:
        item["link"] = {"web": link}
    return item


def link_button(label: str, url: str) -> dict:
    return {"action": "webLink", "label": label[:14], "webLinkUrl": url}


def message_button(text: str) -> dict:
    # 문서와 달리 단톡방에서는 messageText 가 무시되고 버튼 이름(label)이 그대로 채팅으로 올라온다.
    # 웹훅 payload 에도 버튼 입력을 구분하는 필드가 없어서(2026-10-28 실측) 둘을 같게 둔다.
    return {"action": "message", "label": text[:14], "messageText": text[:14]}


# ----------------------------- API 클라이언트 -----------------------------

class KakaoBotClient:
    def __init__(self, bot_token: str, http: httpx.AsyncClient):
        self.bot_token = bot_token
        self.http = http

    def _headers(self) -> dict:
        return {"Authorization": f"KakaoAK {self.bot_token}"}

    async def callback(self, callback_token: str, response: dict) -> bool:
        """MESSAGE_CREATE 에 대한 답장. 콜백 토큰은 5분 뒤 만료."""
        resp = await self.http.post(
            f"{KAKAO_API_URL}/v1/bot/callback",
            json={"skillResponse": response},
            headers={**self._headers(), "X-Bot-Callback-Token": callback_token},
        )
        if resp.status_code != 200:
            log.error("callback 실패 %d %s", resp.status_code, resp.text)
        return resp.status_code == 200

    async def send_message(self, response: dict, *, group_key: str = "", user_key: str = "") -> bool:
        """봇이 먼저 보내는 메시지. 일반/오픈/팀채팅은 group_key, 채널채팅은 user_key."""
        body = {"skillResponse": response}
        if group_key:
            body["botGroupKey"] = group_key
        else:
            body["botUserKey"] = user_key
        resp = await self.http.post(f"{KAKAO_API_URL}/v1/bot/send_message", json=body, headers=self._headers())
        if resp.status_code != 200:
            log.error("send_message 실패 %d %s", resp.status_code, resp.text)
        return resp.status_code == 200
