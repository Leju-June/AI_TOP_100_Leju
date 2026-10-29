"""웹훅/위치 API 를 카카오 서버 없이 확인한다 (httpx MockTransport)."""
import json

import httpx
from fastapi.testclient import TestClient

from eodiro.app import create_app
from eodiro.config import Config
from eodiro.store import Store

CFG = Config(bot_token="bot", kakao_rest_api_key="rest", public_base_url="https://eodiro.test",
             webhook_header_name="X-Eodiro", webhook_header_value="secret", port=0, db_path=None,
             agent_enabled=False)


def make_client():
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "kapi.kakao.com":
            sent.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json={"totalCount": 1})
        if request.url.path.startswith("/v2/local/search/keyword"):
            return httpx.Response(200, json={"documents": [{
                "id": "1", "place_name": "미금역", "category_name": "교통", "address_name": "성남시",
                "x": "127.11", "y": "37.35", "place_url": "http://place.map.kakao.com/1"}]})
        if request.url.path == "/v2/routing/publictraffic":
            return httpx.Response(200, json={"status": "OK", "routes": [{
                "properties": {"type": "SUBWAY", "totalDistance": 15000, "totalTime": 1500}, "steps": []}]})
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app(CFG, http=http, store=Store(":memory:"))
    return TestClient(app), sent


def dispatch(text):
    return {"op": 0, "t": "MESSAGE_CREATE", "d": {
        "id": 1, "content": text, "isChannelChatroom": False, "botGroupKey": "g1", "botUserKey": "u1",
        "timestamp": "2026-10-28T03:00:00Z", "callbackToken": "cb"}}


def test_webhook_rejects_missing_header():
    client, _ = make_client()
    with client:
        assert client.post("/webhook", json=dispatch("@어디로 미금역")).status_code == 401


def test_full_route_flow():
    client, sent = make_client()
    with client:
        r = client.post("/webhook", json=dispatch("@어디로 미금역"), headers={"X-Eodiro": "secret"})
        assert r.status_code == 204
        path, body = sent[-1]
        assert path == "/v1/bot/callback"
        url = body["skillResponse"]["template"]["outputs"][0]["textCard"]["buttons"][0]["webLinkUrl"]
        req_id = url.split("req=")[1]

        assert "내 위치 보내기" in client.get(f"/locate?req={req_id}").text

        r = client.post("/api/location", json={"req": req_id, "lat": 37.25, "lng": 127.07, "botUserKey": "u1"})
        assert r.json()["ok"] is True
        path, body = sent[-1]
        assert path == "/v1/bot/send_message" and body["botGroupKey"] == "g1"
        assert "25분" in body["skillResponse"]["template"]["outputs"][0]["textCard"]["description"]


def test_mention_gets_reply():
    client, sent = make_client()
    with client:
        client.post("/webhook", json=dispatch("@어디로 도움말"), headers={"X-Eodiro": "secret"})
    path, body = sent[-1]
    assert path == "/v1/bot/callback"
    assert "사용법" in body["skillResponse"]["template"]["outputs"][0]["simpleText"]["text"]
