"""카카오톡 없이 봇을 시험하는 CLI. KAKAO_REST_API_KEY 가 필요하고, 에이전트는 ANTHROPIC_API_KEY 도 필요하다.

예: .venv/Scripts/python.exe -m eodiro.cli "@어디로 미금역 가는 중인데 얼마나 남았어?" --lat 37.2513 --lng 127.0711
    (--lat/--lng 를 주면 위치 전송 단계까지 이어서 실행, --no-agent 면 기존 명령어 파서만 사용)
    도구 호출 과정은 로그로 찍힌다.
"""
import argparse
import asyncio
import dataclasses
import json
import logging
import sys
from urllib.parse import parse_qs, urlparse

import httpx

from .agent import Agent
from .config import load_config, now_kst
from .handlers import Bot, LocationError, Message
from .kakao_map import KakaoMapClient, Point
from .store import Store


def find_locate_req(response: dict) -> str | None:
    for out in response["template"]["outputs"]:
        for btn in next(iter(out.values())).get("buttons", []):
            if "/locate?" in btn.get("webLinkUrl", ""):
                return parse_qs(urlparse(btn["webLinkUrl"]).query)["req"][0]
    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--room", default="cli-room")
    ap.add_argument("--user", default="cli-user")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lng", type=float)
    ap.add_argument("--no-agent", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔(cp949)은 이모지를 못 찍는다
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    cfg = load_config()
    if args.no_agent:
        cfg = dataclasses.replace(cfg, agent_enabled=False)
    async with httpx.AsyncClient(timeout=10) as http:
        store, maps = Store(cfg.db_path), KakaoMapClient(cfg.kakao_rest_api_key, http)
        bot = Bot(store, maps, cfg.public_base_url, cfg.location_request_ttl_sec, now_kst,
                  agent=Agent.from_config(cfg, store, maps, now_kst))
        response = await bot.handle_message(Message(args.text, args.room, args.user))
        print(json.dumps(response, ensure_ascii=False, indent=2) if response else "(봇 호출 아님)")
        req_id = response and find_locate_req(response)
        if req_id and args.lat is not None and args.lng is not None:
            try:
                _, result = await bot.handle_location(req_id, Point(args.lng, args.lat), args.user)
            except LocationError as e:
                print("위치 처리 실패:", e.message)
                return
            print("\n--- 위치 전송 후 채팅방으로 보낼 메시지 ---")
            print(json.dumps(result.response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
