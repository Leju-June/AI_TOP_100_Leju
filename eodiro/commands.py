"""'@어디로 ...' 메시지를 명령으로 해석한다."""
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# 단톡방에서는 봇을 멘션한 메시지만 웹훅으로 오므로 들어온 메시지는 모두 봇 호출로 본다.
# 앞의 '@봇이름' 멘션은 있으면 떼어낸다.
MENTION_RE = re.compile(r"^\s*@\S+\s*")


class Mode(str, Enum):
    TRANSIT = "대중교통"
    BUS = "버스"
    SUBWAY = "지하철"
    WALK = "도보"
    CAR = "자동차"


# 긴 표현부터 매칭해야 '버스로'가 '버스'보다 먼저 지워진다.
MODE_WORDS: list[tuple[str, Mode]] = [
    ("대중교통으로", Mode.TRANSIT), ("대중교통", Mode.TRANSIT),
    ("버스로", Mode.BUS), ("버스", Mode.BUS),
    ("지하철로", Mode.SUBWAY), ("지하철", Mode.SUBWAY), ("전철로", Mode.SUBWAY), ("전철", Mode.SUBWAY),
    ("걸어서", Mode.WALK), ("도보로", Mode.WALK), ("도보", Mode.WALK), ("걸어가면", Mode.WALK),
    ("자동차로", Mode.CAR), ("자동차", Mode.CAR), ("차로", Mode.CAR), ("운전해서", Mode.CAR),
    ("택시로", Mode.CAR), ("택시", Mode.CAR),
]

# 목적지 뒤에 붙는 질문/군더더기 표현
FILLER_RE = re.compile(
    r"(얼마나\s*남았(어|나|니|지|어요|나요)?|얼마나\s*걸려(요)?|몇\s*분\s*(남았|걸려)\S*|"
    r"가는\s*(길|법|방법)|어떻게\s*가\S*|길\s*(알려|찾아)\S*|가자|갈게|가는\s*중|[?？!.~]+)"
)

NEARBY_WORDS = ("아무대나", "아무데나", "아무 데나", "아무 대나", "아무곳", "아무 곳", "근처", "주변")
LIST_WORDS = {"맛집 리스트", "맛집리스트", "맛집 목록", "맛집목록", "리스트", "목록", "맛집"}
HELP_WORDS = {"", "도움말", "도움", "help", "사용법", "명령어"}


@dataclass(frozen=True)
class Help:
    pass


@dataclass(frozen=True)
class Route:
    destination: str
    mode: Mode


@dataclass(frozen=True)
class AddRestaurant:
    query: str  # 비어 있으면 방금 추천한 곳을 추가


@dataclass(frozen=True)
class RemoveRestaurant:
    target: str  # 목록 번호 또는 이름


@dataclass(frozen=True)
class ListRestaurants:
    pass


@dataclass(frozen=True)
class Recommend:
    meal: str  # '점심' | '저녁'
    nearby: bool


Command = Help | Route | AddRestaurant | RemoveRestaurant | ListRestaurants | Recommend


def default_meal(now: datetime) -> str:
    return "점심" if 5 <= now.hour < 16 else "저녁"


def _parse_recommend(body: str, now: datetime) -> Recommend | None:
    compact = body.replace(" ", "")
    is_rec = ("메추" in compact or ("메뉴" in compact and "추천" in compact)
              or "뭐먹" in compact or "밥추천" in compact)
    if not is_rec:
        return None
    if "점메추" in compact or "점심" in compact:
        meal = "점심"
    elif "저메추" in compact or "저녁" in compact:
        meal = "저녁"
    else:
        meal = default_meal(now)
    nearby = any(w.replace(" ", "") in compact for w in NEARBY_WORDS)
    return Recommend(meal, nearby)


def _parse_route(body: str) -> Route | None:
    mode = Mode.TRANSIT
    text = body
    for word, m in MODE_WORDS:
        if word in text:
            mode = m
            text = text.replace(word, " ")
            break
    if "까지" in text:
        text = text.split("까지")[0]
    text = FILLER_RE.sub(" ", text)
    dest = " ".join(text.split()).strip()
    return Route(dest, mode) if dest else None


def parse(text: str, now: datetime) -> Command:
    body = MENTION_RE.sub("", text, count=1).strip()
    if body.lower() in HELP_WORDS:
        return Help()

    m = re.match(r"^맛집\s*(추가|등록)\s*(.*)$", body)
    if m:
        return AddRestaurant(m.group(2).strip())
    m = re.match(r"^맛집\s*(삭제|제거|빼기|빼줘)\s*(.*)$", body)
    if m:
        return RemoveRestaurant(m.group(2).strip()) if m.group(2).strip() else Help()
    if body in LIST_WORDS or re.sub(r"\s+", " ", body).rstrip("?") in {"맛집 리스트 보여줘", "리스트 보여줘"}:
        return ListRestaurants()

    rec = _parse_recommend(body, now)
    if rec:
        return rec
    return _parse_route(body) or Help()
