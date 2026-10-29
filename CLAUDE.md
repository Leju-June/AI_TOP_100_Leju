# AI_TOP_100 — Kakao AI 에이전트 대회 프로젝트

## 프로젝트 개요
- Kakao **AI TOP 100** 대회 참가 프로젝트.
- 대회 방식: 참가자가 AI 에이전트를 만들어 주어진 상황의 문제를 해결. 심사는 **문제 정의 → 단서 조합 → 에이전트가 실제 상황에서 얼마나 적절하게 작동하는가**에 초점.
- Claude의 역할: 사용자가 세운 에이전트 아이디어/구조를 **구체화**하고 **구현**을 돕는 것. 아이디어의 주인은 사용자이므로, 방향을 바꾸는 결정은 제안 후 확인받는다.

## 폴더 구조
- `kakao_챗봇설명서/` — 카카오톡 봇 API 공식 문서(developers.kakao.com/docs/ko/bot) 로컬 사본. 문서 간 링크는 로컬 상대 링크(Obsidian 호환, `파일.md#헤딩` 형식)로 변환되어 있음.
  - `이해하기.md` — 봇 API 개념, 메시지 흐름, 토큰, 이벤트 수신 방식(웹훅 vs 게이트웨이), 말풍선/명령어/퀵리플라이
  - `설정하기.md` — 봇 생성·관리, 인증 토큰, 웹훅 등록, 쿼터, 사용량
  - `REST API.md` — 메시지 콜백/전송, 명령어·도움말 API, SkillResponse·말풍선 컴포넌트 스펙
  - `웹훅.md` — 카카오톡 서버 → 봇 서버 웹훅 요청 명세, 에코봇 예제
  - `게이트웨이.md` — 웹소켓 상시 연결 방식(연결·인증·keep-alive·재연결), 콜백 토큰, 에코봇 예제
  - `튜토리얼.md` — Python(uv) 기반 간단한 봇 만들기
  - `에러 코드.md` — 주요 에러 및 해결 방법
- `kakaomap_설명서/` — 카카오맵 API 문서 로컬 사본(링크 형식은 위와 동일).
  - `이해하기.md` — 카카오맵 API 개요, 제공 방식(REST / 지도 SDK), 쿼터(첫 활성화 앱만 무료), 제공 API 목록
  - `REST API.md` — 주소↔좌표 변환, 키워드/카테고리 장소 검색, 대중교통·도보·자전거 경로 조회, 정적 지도 이미지
  - `웹 지도 가이드.md` — Kakao 지도 JavaScript API 시작하기, 라이브러리, **지도/길찾기 URL 패턴**(`map.kakao.com/link/...`)
  - 자동차 길찾기는 카카오모빌리티(`apis-navi.kakaomobility.com`) 별도 API라 사본 없음.
- `.obsidian/` — 사용자의 Obsidian 볼트 설정. 수정하지 않는다.

## 에이전트: '어디로'
단톡방에서 `@어디로`(또는 봇 멘션)로 호출하는 카카오톡 봇.
1. **남은 동선 안내** — 현재 위치 → 목적지 경로를 구해 카카오맵 길찾기 URL, 남은 거리, 남은 시간, 도착 예정 시각을 한 번에 보여준다.
2. **점심/저녁 메뉴 추천** — 사용자의 맛집 목록 기반 추천(추천 알고리즘은 추후 결정).
- 확인된 제약: 봇 이벤트(`MESSAGE_CREATE`)에는 텍스트만 오고 **사용자 위치가 없다**. 카카오맵 **즐겨찾기 폴더는 외부 연동 API가 없고 공개 URL 스크래핑도 카카오가 불허**(DevTalk 답변).
- 결정 사항: 현재 위치는 **위치 버튼 방식**(webLink → 우리 서버 `/locate` 페이지에서 브라우저 GPS → `/api/location` → 메시지 전송 API로 방에 결과 발송). 맛집은 **봇에 직접 등록**(방별 SQLite).
- 실측(2026-10-28, 단톡방):
  - 멘션한 메시지만 웹훅으로 오고, `content`에는 멘션을 뗀 본문만 온다.
  - 메시지 버튼은 문서와 달리 `messageText`가 아니라 **버튼 이름(label)이 그대로** 올라온다. payload에 버튼 입력을 구분하는 필드도 없다. 그래서 버튼 이름 = 명령 문장으로 둔다.

### 코드 구조 (`eodiro/`)
- `app.py` — FastAPI: `POST /webhook`(1초 내 204, 처리는 백그라운드), `GET /locate`, `POST /api/location`
- `handlers.py` — `Bot`: 메시지 → SkillResponse. 대기 상태(후보 선택·되묻기·삭제 확인) → 버튼 문장은 파서로 바로 → 나머지는 에이전트(실패 시 파서). 위치 요청 생성/완료. 전송 방식과 분리돼 있어 CLI·테스트에서 재사용
- `agent.py` — 에이전트 루프: 첫 호출은 빠른 모델, 도구 결과 뒤는 기본 모델. 위치·선택이 필요하면 대화 상태를 저장하고 멈췄다가 답이 오면 tool_result 로 이어 붙여 재개
- `tools.py` — 에이전트 도구 8개(search_place, get_route, request_location, ask_user, list/add/remove_restaurant, recommend_restaurant). 결과는 LLM용 JSON, 카드는 답장에 붙임
- `llm.py` — `LLMClient` 인터페이스와 Claude API 구현(`AnthropicLLM`, 서버 측 fallback 사용). 테스트는 가짜 LLM
- `commands.py` — `@어디로 ...` 파서 (Route/AddRestaurant/RemoveRestaurant/ListRestaurants/Recommend/Help). 에이전트의 빠른 경로·대체 경로
- `route_service.py` — 경로 계산(대중교통 수단 필터·도보·자동차)과 답장 카드
- `food_service.py` — 맛집 목록/추천 카드, `pick_restaurant()`(추천 알고리즘 자리)
- `kakao_bot.py`, `kakao_map.py` — API 클라이언트와 말풍선 빌더 / `store.py` — SQLite
- `register_commands.py` — 멘션 시 뜨는 추천 명령어 등록(`COMMANDS` 목록, 전체 덮어쓰기) / `--show` 조회
- `cli.py` — 카카오톡 없이 시험: `.venv/Scripts/python.exe -m eodiro.cli "@어디로 미금역 얼마나 남았어?" --lat .. --lng ..` (`--no-agent`면 파서만)
- 테스트: `.venv/Scripts/python.exe -m pytest` (가짜 지도 클라이언트·가짜 LLM·MockTransport 사용, 네트워크 불필요). `tests/test_agent.py`가 계획서 시나리오 9개
- 에이전트 설정: `.env`의 `ANTHROPIC_API_KEY`, `AGENT_MODEL`(기본 claude-sonnet-5-5), `AGENT_FAST_MODEL`(기본 claude-haiku-5-5), `AGENT_EFFORT`(기본 low), `AGENT_ENABLED`

## 외부 참고 자료
- **500+ AI Agent Projects** — https://github.com/ashishpatel26/500-AI-Agents-Projects
  - 에이전트 설계 시 참고할 예시 모음(MIT). 프레임워크별(LangGraph, CrewAI, AutoGen, Agno 등)·산업별 사용 사례와 실행 가능한 구현(`agents/` 폴더, 각 폴더에 `requirements.txt`·`.env.example` 포함)이 있음.
  - 조회 방법: README 원문은 `https://raw.githubusercontent.com/ashishpatel26/500-AI-Agents-Projects/main/README.md`, 특정 예시는 `.../main/agents/<폴더명>/` 하위 파일을 raw URL로 가져온다.
  - 예시는 아이디어·구조 참고용이며, 최종 구현은 카카오톡 봇 API(`kakao_챗봇설명서/`) 기준에 맞춰 조정한다.

## 개발 환경
- 모든 Python 개발·실행은 프로젝트 가상환경 **`.venv/`** 에서 한다 (공식 CPython 3.14.8, Windows x64).
  - 실행: `.venv/Scripts/python.exe <파일>` / 패키지 설치: `.venv/Scripts/python.exe -m pip install <패키지>`
  - 활성화: PowerShell `.venv\Scripts\Activate.ps1`, Git Bash `source .venv/Scripts/activate`
  - MSYS2 Python은 쓰지 않는다 (pydantic-core 등 바이너리 휠이 없어 빌드 실패).
- 시스템 Python이나 `uv run`으로 실행하지 않는다 (튜토리얼의 `uv` 예제도 `.venv`에 의존성을 설치해 실행).
- 설치한 패키지는 `requirements.txt`에 기록한다.

## 작업 원칙
- 카카오 봇 API 관련 구현 시 **항상 `kakao_챗봇설명서/`의 문서를 먼저 참조**하고, 추측으로 엔드포인트·필드를 만들지 않는다.
- 문서 링크를 추가/수정할 때는 로컬 링크 형식(`[텍스트](REST%20API.md#헤딩)`, 공백은 `%20`)을 유지한다.
- 봇 인증 토큰 등 비밀값은 코드에 하드코딩하지 않고 환경 변수(`.env`)로 관리하며, `.env`는 커밋하지 않는다.
- 사용자와의 대화는 한국어로 한다.
