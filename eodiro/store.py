"""SQLite 저장소: 방별 맛집 목록, 위치 요청, 장소 캐시, 최근 추천 기록.

카카오 장소 API 응답의 저장·재사용에는 정책 제한이 있을 수 있어 표시에 필요한 최소 필드만 보관한다.
"""
import json
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .kakao_map import Place

SCHEMA = """
CREATE TABLE IF NOT EXISTS restaurants (
    group_key TEXT NOT NULL,
    place_id  TEXT NOT NULL,
    data      TEXT NOT NULL,
    added_by  TEXT,
    added_at  REAL NOT NULL,
    PRIMARY KEY (group_key, place_id)
);
CREATE TABLE IF NOT EXISTS location_requests (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    group_key  TEXT,
    user_key   TEXT,
    is_channel INTEGER NOT NULL,
    created_at REAL NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS place_cache (
    place_id  TEXT PRIMARY KEY,
    data      TEXT NOT NULL,
    cached_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS recent_picks (
    group_key TEXT NOT NULL,
    place_id  TEXT NOT NULL,
    picked_at REAL NOT NULL
);
"""


@dataclass
class LocationRequest:
    id: str
    kind: str
    payload: dict
    group_key: str
    user_key: str
    is_channel: bool
    created_at: float
    used: bool


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def _exec(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self.lock, self.conn:
            return self.conn.execute(sql, args).fetchall()

    # 맛집 목록
    def add_restaurant(self, group_key: str, place: Place, added_by: str) -> bool:
        """새로 추가되면 True, 이미 있으면 False."""
        if self._exec("SELECT 1 FROM restaurants WHERE group_key=? AND place_id=?", (group_key, place.id)):
            return False
        self._exec("INSERT INTO restaurants VALUES (?,?,?,?,?)",
                   (group_key, place.id, json.dumps(place.to_dict(), ensure_ascii=False), added_by, time.time()))
        return True

    def list_restaurants(self, group_key: str) -> list[Place]:
        rows = self._exec("SELECT data FROM restaurants WHERE group_key=? ORDER BY added_at", (group_key,))
        return [Place.from_dict(json.loads(r[0])) for r in rows]

    def remove_restaurant(self, group_key: str, place_id: str) -> None:
        self._exec("DELETE FROM restaurants WHERE group_key=? AND place_id=?", (group_key, place_id))

    # 위치 요청
    def create_location_request(self, kind: str, payload: dict, group_key: str, user_key: str,
                                is_channel: bool, created_at: float) -> str:
        req_id = secrets.token_urlsafe(12)
        self._exec("INSERT INTO location_requests (id, kind, payload, group_key, user_key, is_channel, created_at)"
                   " VALUES (?,?,?,?,?,?,?)",
                   (req_id, kind, json.dumps(payload, ensure_ascii=False), group_key, user_key,
                    int(is_channel), created_at))
        return req_id

    def get_location_request(self, req_id: str) -> LocationRequest | None:
        rows = self._exec("SELECT id, kind, payload, group_key, user_key, is_channel, created_at, used"
                          " FROM location_requests WHERE id=?", (req_id,))
        if not rows:
            return None
        r = rows[0]
        return LocationRequest(r[0], r[1], json.loads(r[2]), r[3] or "", r[4] or "", bool(r[5]), r[6], bool(r[7]))

    def mark_location_request_used(self, req_id: str) -> None:
        self._exec("UPDATE location_requests SET used=1 WHERE id=?", (req_id,))

    # 장소 캐시 (후보 선택 버튼 등에서 id 로 장소를 다시 찾기 위함, 하루 보관)
    def cache_places(self, places: list[Place]) -> None:
        now = time.time()
        for p in places:
            self._exec("INSERT OR REPLACE INTO place_cache VALUES (?,?,?)",
                       (p.id, json.dumps(p.to_dict(), ensure_ascii=False), now))

    def get_cached_place(self, place_id: str, max_age_sec: int = 86400) -> Place | None:
        rows = self._exec("SELECT data FROM place_cache WHERE place_id=? AND cached_at>?",
                          (place_id, time.time() - max_age_sec))
        return Place.from_dict(json.loads(rows[0][0])) if rows else None

    # 최근 추천 (같은 곳 연속 추천 방지)
    def record_pick(self, group_key: str, place_id: str) -> None:
        self._exec("INSERT INTO recent_picks VALUES (?,?,?)", (group_key, place_id, time.time()))

    def recent_picks(self, group_key: str, limit: int = 3) -> list[str]:
        rows = self._exec("SELECT place_id FROM recent_picks WHERE group_key=? ORDER BY picked_at DESC LIMIT ?",
                          (group_key, limit))
        return [r[0] for r in rows]
