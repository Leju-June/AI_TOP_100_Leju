"""환경 변수 설정. 프로젝트 루트의 .env 를 읽는다."""
import os
from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Windows 에는 tz 데이터베이스가 없어 zoneinfo 대신 고정 오프셋을 쓴다.
KST = timezone(timedelta(hours=9), "KST")


@dataclass(frozen=True)
class Config:
    bot_token: str
    kakao_rest_api_key: str
    public_base_url: str
    webhook_header_name: str
    webhook_header_value: str
    port: int
    db_path: Path
    location_request_ttl_sec: int = 600


def load_config() -> Config:
    return Config(
        bot_token=os.getenv("BOT_TOKEN", ""),
        kakao_rest_api_key=os.getenv("KAKAO_REST_API_KEY", ""),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        webhook_header_name=os.getenv("WEBHOOK_HEADER_NAME", ""),
        webhook_header_value=os.getenv("WEBHOOK_HEADER_VALUE", ""),
        port=int(os.getenv("WEBHOOK_PORT", "8000")),
        db_path=Path(os.getenv("DB_PATH", str(ROOT / "data" / "eodiro.db"))),
    )
