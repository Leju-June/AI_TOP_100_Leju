"""멘션 시 입력창 위에 뜨는 추천 명령어를 등록한다.

명세: kakao_챗봇설명서/REST API.md#명령어 (최대 30개, 보낸 목록이 기존 목록 전체를 덮어쓴다)
누르면 buttonName 이 채팅으로 올라오므로 buttonName 은 commands.py 가 해석하는 명령 문장이어야 한다.

조회: .venv/Scripts/python.exe -m eodiro.register_commands --show
등록: .venv/Scripts/python.exe -m eodiro.register_commands
"""
import argparse
import json

import httpx

from .config import load_config
from .kakao_bot import KAKAO_API_URL

COMMANDS: list[tuple[str, str]] = [
    ("도움말", "사용법 보기"),
    ("점메추", "우리 방 맛집에서 점심 추천"),
    ("저메추", "우리 방 맛집에서 저녁 추천"),
    ("아무대나 점메추", "내 위치 근처에서 점심 추천"),
    ("아무대나 저메추", "내 위치 근처에서 저녁 추천"),
    ("맛집 리스트", "우리 방 맛집 목록"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="'어디로' 추천 명령어 등록/조회")
    parser.add_argument("--show", action="store_true", help="등록하지 않고 현재 목록만 조회")
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.bot_token:
        raise SystemExit(".env 에 BOT_TOKEN 을 설정하세요")
    headers = {"Authorization": f"KakaoAK {cfg.bot_token}"}

    with httpx.Client(timeout=10) as http:
        if args.show:
            resp = http.get(f"{KAKAO_API_URL}/v1/bot/commands", headers=headers)
        else:
            body = {"utterances": [{"buttonName": name, "description": desc} for name, desc in COMMANDS]}
            resp = http.post(f"{KAKAO_API_URL}/v1/bot/commands/update", json=body, headers=headers)
    print(resp.status_code)
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except ValueError:
        print(resp.text)


if __name__ == "__main__":
    main()
