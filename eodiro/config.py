"""환경 변수 설정. 프로젝트 루트의 .env 를 읽는다."""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Windows 에는 tz 데이터베이스가 없어 zoneinfo 대신 고정 오프셋을 쓴다.
KST = timezone(timedelta(hours=9), "KST")


def now_kst() -> datetime:
    return datetime.now(KST)


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
    # 에이전트 (Claude API). 자격 증명은 ANTHROPIC_API_KEY 를 SDK 가 직접 읽는다.
    agent_enabled: bool = True
    agent_model: str = "claude-sonnet-5-5"     # 도구 결과를 보고 답을 쓰는 모델
    agent_fast_model: str = "claude-haiku-5-5"  # 새 메시지의 첫 도구 선택
    agent_effort: str = "low"


def load_config() -> Config:
    return Config(
        bot_token=os.getenv("BOT_TOKEN", ""),
        kakao_rest_api_key=os.getenv("KAKAO_REST_API_KEY", ""),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        webhook_header_name=os.getenv("WEBHOOK_HEADER_NAME", ""),
        webhook_header_value=os.getenv("WEBHOOK_HEADER_VALUE", ""),
        port=int(os.getenv("WEBHOOK_PORT", "8000")),
        db_path=Path(os.getenv("DB_PATH", str(ROOT / "data" / "eodiro.db"))),
        agent_enabled=os.getenv("AGENT_ENABLED", "1") != "0",
        agent_model=os.getenv("AGENT_MODEL", "claude-sonnet-5-5"),
        agent_fast_model=os.getenv("AGENT_FAST_MODEL", "claude-haiku-5-5"),
        agent_effort=os.getenv("AGENT_EFFORT", "low"),
    )
