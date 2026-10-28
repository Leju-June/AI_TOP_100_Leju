"""웹훅 서버 + 위치 전송 페이지.

실행: .venv/Scripts/python.exe -m eodiro.app
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .config import Config, load_config
from .handlers import Bot, LocationError, Message
from .kakao_bot import KakaoBotClient
from .kakao_map import KakaoMapClient, Point
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("eodiro")

OP_DISPATCH = 0
LOCATE_HTML = (Path(__file__).parent / "static" / "locate.html").read_text(encoding="utf-8")


class LocationBody(BaseModel):
    req: str
    lat: float
    lng: float
    botUserKey: str = ""


def create_app(cfg: Config | None = None, http: httpx.AsyncClient | None = None,
               store: Store | None = None) -> FastAPI:
    cfg = cfg or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = http or httpx.AsyncClient(timeout=10)
        app.state.bot = Bot(store or Store(cfg.db_path), KakaoMapClient(cfg.kakao_rest_api_key, client),
                            cfg.public_base_url, cfg.location_request_ttl_sec)
        app.state.kakao = KakaoBotClient(cfg.bot_token, client)
        yield
        if http is None:
            await client.aclose()

    app = FastAPI(lifespan=lifespan)

    async def process_message(msg: Message, callback_token: str) -> None:
        log.info("메시지 수신: %r", msg.content)
        response = await app.state.bot.handle_message(msg)
        if await app.state.kakao.callback(callback_token, response):
            log.info("답장 완료")

    @app.post("/webhook")
    async def webhook(request: Request, background: BackgroundTasks) -> Response:
        # 1초 안에 2xx 로 응답하고, 실제 처리는 백그라운드에서 한다.
        if cfg.webhook_header_name and cfg.webhook_header_value and request.headers.get(cfg.webhook_header_name) != cfg.webhook_header_value:
            return Response(status_code=401)
        payload = await request.json()
        d = payload.get("d") or {}
        if payload.get("op") == OP_DISPATCH and payload.get("t") == "MESSAGE_CREATE" and d.get("callbackToken"):
            msg = Message(d.get("content", ""), d.get("botGroupKey", ""), d.get("botUserKey", ""),
                          bool(d.get("isChannelChatroom")))
            background.add_task(process_message, msg, d["callbackToken"])
        return Response(status_code=204)

    @app.get("/locate", response_class=HTMLResponse)
    async def locate_page() -> str:
        return LOCATE_HTML

    @app.post("/api/location")
    async def receive_location(body: LocationBody) -> JSONResponse:
        bot: Bot = app.state.bot
        try:
            req, result = await bot.handle_location(body.req, Point(body.lng, body.lat), body.botUserKey)
        except LocationError as e:
            return JSONResponse({"ok": False, "message": e.message}, status_code=e.status)
        sent = await app.state.kakao.send_message(
            result.response,
            group_key="" if req.is_channel else req.group_key,
            user_key=req.user_key if req.is_channel else "",
        )
        if not sent:
            return JSONResponse({"ok": False, "message": "채팅방으로 전송하지 못했어요."}, status_code=502)
        return JSONResponse({"ok": True, "message": result.summary})

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    return app


if __name__ == "__main__":
    config = load_config()
    missing = [k for k, v in {"BOT_TOKEN": config.bot_token, "KAKAO_REST_API_KEY": config.kakao_rest_api_key}.items()
               if not v]
    if missing:
        raise SystemExit(f".env 에 {', '.join(missing)} 를 설정하세요")
    uvicorn.run(create_app(config), host="0.0.0.0", port=config.port)
