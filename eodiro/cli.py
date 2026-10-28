"""카카오톡 없이 명령을 시험하는 CLI. KAKAO_REST_API_KEY 만 있으면 된다.

예: .venv/Scripts/python.exe -m eodiro.cli "@어디로 미금역까지 버스로" --lat 37.2513 --lng 127.0711
    (--lat/--lng 를 주면 위치 전송 단계까지 이어서 실행)
"""
import argparse
import asyncio
import json
from urllib.parse import parse_qs, urlparse

import httpx

from .config import load_config
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
    args = ap.parse_args()

    cfg = load_config()
    async with httpx.AsyncClient(timeout=10) as http:
        bot = Bot(Store(cfg.db_path), KakaoMapClient(cfg.kakao_rest_api_key, http), cfg.public_base_url)
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
