# Wire Desk Marfeel 수집·녹화 (1단계) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** wire-desk가 Marfeel Reporting API에서 5분마다 국내·해외 KT 기사별 실시간 조회를 받아 DB에 쌓는다. 같은 코드로 48시간 이상 실제 API를 녹화하는 실행기도 만든다.

**Architecture:**
- 순수 로직(쿼리 조립, 응답 해석, 기사 URL 판별, 주기 판정)은 `wire_desk/domain/marfeel.py`에 둔다.
- HTTP·인증·호출 간격은 `wire_desk/adapters/marfeel_client.py`가 맡는다. 저장은 `wire_desk/adapters/db/kt_reads.py`가 맡는다.
- 주기 실행은 `wire_desk/lanes/marfeel_poll.py`의 `MarfeelPoller`가 맡는다. poller는 jobs 레인 안의 하위 작업으로 돈다. worker 레인은 3개를 유지한다.
- 녹화 실행기 `python -m wire_desk.marfeel_record`는 `RealClock`으로 같은 poller를 돌리고, JSONL도 남긴다.

**Tech Stack:** Python 3.12, httpx, asyncpg, pydantic-settings, pytest(+asyncio), ruff, pyright. 새 의존성은 없다.

**Spec:** `docs/plans/2026-10-22-wire-desk-marfeel-demand-design.md` (이 저장소 `marfeel`). 근거 실측은 `docs/references/marfeel-data-scope.md` 8절이다.

**대상 저장소:** `/home/kwh8121/projects/wire-desk`. 아래 경로는 모두 이 저장소 기준이다.
- `main`에서 `task/M1-marfeel-collect`를 만든다. 시작 전에 `git status --short --branch`로 다른 작업 브랜치가 아닌지 확인한다.
- 검증 명령은 `docs/guides/development.md`를 따른다.

## 범위

- **이번 계획 (설계 11절의 1단계):** 4.2 수집, 4.6 장애·한도 처리(알림 포함), 6.1 녹화, 10절 T0 확인 1~3
- **다른 계획으로 넘김**
  - KT 제목 임베딩, 4.3 수요 계산, 5절 후속 복귀, 4.4 화면은 T5(analyze) 계획에 처음부터 넣는다(설계 11절 2). 임베딩 경로와 사안 중심점이 T5에서 생기기 때문이다.
  - 6.2 반합성 생성, 6.3 Mock Marfeel, 7절 G19는 녹화가 끝난 뒤 별도 계획으로 한다(설계 11절 3).
  - 4.2의 보존 삭제(7일·30일)는 `maintenance` 모듈을 만드는 작업에서 한다. 삭제는 그 모듈에서만 할 수 있기 때문이다(r8 고정 25, `tests/static/test_delete_only_in_maintenance.py`). 1단계 데이터량은 하루 약 576 스냅샷, 최대 11.5만 행이라 PoC 기간에는 문제가 없다.

## Global Constraints

- 호출 한도는 계정당 분당 1회다. Marfeel 호출(로그인 포함) 사이는 **65초 이상** 둔다. 로그인이 한도에 포함되는지 모르므로 로그인도 같은 간격 장치를 지난다.
- 429는 바로 재시도하지 않는다. 그 주기의 남은 요청은 건너뛴다.
- 국가 필터 값은 GeoNames ID 문자열이다. 한국은 `"1835841"`, 국내는 `op: "eq"`, 해외는 `op: "neq"`다.
- 요청 기간은 `{"last": {"number": 30, "dimension": "minute"}}`, `granularity: "realtime"`이다. `day` 단위는 쓰지 않는다.
- 응답 행 `limit`은 시작값 200, 최대 500이다.
- 기사 URL 판별은 정규식 `/\d{8}/`이다. 맞지 않는 URL(홈페이지·섹션)은 `excluded = true`다.
- 시각은 `Clock`으로만 얻는다. SQL에 `now()`·`CURRENT_TIMESTAMP`를 쓰지 않는다. `datetime.now`와 `time.time`은 금지다(ruff TID251). 단조 시계 `time.monotonic`은 허용된다.
- `wire_desk/domain/`에서는 `httpx`, `asyncpg`, `os.environ`, `wire_desk.adapters·lanes·api·clock·config`를 import하지 않는다.
- 비밀값(`MARFEEL_EMAIL`, `MARFEEL_SECRET`, 토큰)은 로그, 예외 메시지, JSONL, api_calls에 남기지 않는다.
- Herb 주소의 Mock 전용 규칙(C1)은 그대로 둔다. Marfeel 주소는 `api.newsroom.bi`와 `mock-marfeel` 두 호스트만 허용한다.
- 재생 모드(`CLOCK_MODE=replay`)에서 실제 Marfeel 호스트를 쓰는 설정은 기동할 때 거부한다.
- 녹화 JSONL(`fixtures/marfeel/recordings/`)은 커밋하지 않는다.

## Review Focus

1. **worker와 녹화 실행기를 같은 계정으로 동시에 띄움** → 둘째 프로세스는 호출하지 않고 경고만 남겨야 한다(Postgres advisory lock). Task 5의 `test_second_poller_does_not_call`
2. **마지막 호출 뒤 65초 안에 프로세스를 재시작함** → 재시작한 프로세스도 남은 시간을 기다려야 한다(간격을 DB `api_calls`와 메모리 중 늦은 값으로 판단). Task 4의 `test_gate_waits_for_db_recorded_call`
3. **국가 필터가 조용히 무시됨(국내·해외 합계가 같음)** → 두 구간 모두 `invalid`로 저장하고 반영하지 않는다. Task 3의 `test_judge_pair_equal_totals_invalid`
4. **새벽처럼 조회가 적거나 홈페이지만 읽힌 주기** → 기사 행이 0개여도 `ok`다. 실패로 세어 알림을 내면 안 된다. Task 3의 `test_parse_homepage_only_is_ok`, Task 5의 `test_quiet_cycle_is_ok`
5. **재생 모드 worker가 실제 Marfeel 주소로 설정됨** → 60배속 주기로 실제 API를 두드리지 않도록 기동이 실패해야 한다. Task 6의 `test_replay_with_real_marfeel_host_rejected`

---

### Task 1: Marfeel 설정

**Files:**
- Modify: `wire_desk/config.py` (파일 끝에 클래스와 로더 추가)
- Modify: `.env.wire.example` (Marfeel 블록 추가, 값은 비움)
- Test: `tests/unit/test_marfeel_config.py`

**Interfaces:**
- Produces:
  - `class MarfeelSettings(BaseSettings)`: `env_prefix="MARFEEL_"`, `extra="ignore"`, `frozen=True`
  - 필드: `enabled: bool = False`, `base_url: HttpUrl = "https://api.newsroom.bi"`, `email: str | None = None`, `secret: SecretStr | None = None`, `poll_seconds: int = 300`, `poll_offset_seconds: int = 60`, `min_call_interval_seconds: float = 65`, `window_minutes: int = 30`, `limit: int = 200`, `country_id: str = "1835841"`, `article_url_pattern: str = r"/\d{8}/"`, `with_title: bool = True`, `token_max_age_days: int = 13`, `timeout_seconds: float = 15`, `alert_after_failed_cycles: int = 3`, `recordings_dir: Path = Path("fixtures/marfeel/recordings")`
  - 상수: `MARFEEL_HOSTS = frozenset({"api.newsroom.bi", "mock-marfeel"})`
  - `def load_marfeel_settings(env_file: Path | None = None) -> MarfeelSettings`: 실패하면 `SettingsError`이고, 메시지에 입력값을 넣지 않는다. `load_settings`와 같은 방식이다.
  - 환경변수 이름은 `MARFEEL_EMAIL`, `MARFEEL_SECRET`이다. marfeel 저장소 스크립트와 같다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_defaults_disabled(): s = MarfeelSettings(); assert s.enabled is False and s.limit == 200 and s.country_id == "1835841"
def test_enabled_requires_credentials(): with pytest.raises(ValidationError): MarfeelSettings(enabled=True)
def test_host_must_be_allowed(): with pytest.raises(ValidationError): MarfeelSettings(base_url="https://evil.example")
def test_mock_host_allowed(): assert MarfeelSettings(base_url="http://mock-marfeel:9100").base_url.host == "mock-marfeel"
def test_limit_max_500(): with pytest.raises(ValidationError): MarfeelSettings(limit=501)
def test_interval_at_least_61(): with pytest.raises(ValidationError): MarfeelSettings(min_call_interval_seconds=60)
def test_bad_pattern_rejected(): with pytest.raises(ValidationError): MarfeelSettings(article_url_pattern="(")
def test_loader_hides_secret(tmp_path):  # MARFEEL_ENABLED=true, MARFEEL_SECRET=topsecret-value, email 없음
    with pytest.raises(SettingsError) as e: load_marfeel_settings(env)
    assert "topsecret-value" not in str(e.value)
```

- [ ] **Step 2: 실행해서 실패 확인** — `uv run pytest tests/unit/test_marfeel_config.py -v` → ImportError
- [ ] **Step 3: `MarfeelSettings`·`load_marfeel_settings` 구현.** 검증은 다음과 같이 건다.
  - `limit`: `Field(gt=0, le=500)`
  - `min_call_interval_seconds`: `Field(ge=61)`
  - 그 밖의 정수: `gt=0`
  - 정규식 컴파일은 `field_validator`로 확인한다.
  - 호스트 검사와 `enabled`일 때의 자격증명 필수는 `model_validator`로 확인한다.
- [ ] **Step 4: `.env.wire.example`에 `MARFEEL_ENABLED=false`, `MARFEEL_EMAIL=`, `MARFEEL_SECRET=`를 주석과 함께 추가한다.** 빈 값은 미설정으로 본다. `_blank_is_unset`과 같은 처리다.
- [ ] **Step 5: 통과 확인** — `uv run pytest tests/unit/test_marfeel_config.py tests/unit/test_config.py -v` → PASS
- [ ] **Step 6: 커밋** — `git commit -m "feat(config): Marfeel settings"`

### Task 2: 스키마 0003 (수집 테이블, api_calls 대상 추가)

**Files:**
- Create: `wire_desk/adapters/db/migrations/0003_marfeel_reads.sql`
- Modify: `tests/scenario/conftest.py` (`ALL_TABLES`에 새 테이블 3개 추가)
- Test: `tests/db/test_marfeel_schema.py`

**Interfaces:**
- Produces: 다음 테이블과 제약. 이후 Task가 이 이름을 그대로 쓴다.

```sql
ALTER TABLE api_calls DROP CONSTRAINT api_calls_target_check;
ALTER TABLE api_calls ADD CONSTRAINT api_calls_target_check
    CHECK (target IN ('herb', 'openai', 'openrouter', 'marfeel'));
CREATE INDEX api_calls_target_wall ON api_calls (target, wall_time DESC);

CREATE TABLE kt_read_snapshots (                -- 보존 7일 (삭제는 maintenance 작업에서)
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    segment        text        NOT NULL CHECK (segment IN ('domestic', 'overseas')),
    collected_at   timestamptz NOT NULL,        -- Clock
    window_minutes smallint    NOT NULL,
    status         text        NOT NULL CHECK (status IN ('ok', 'rate_limited', 'invalid', 'error')),
    error          text,                        -- 짧은 코드 (filter_ignored, no_data, http_503 ...)
    total_pv       int,
    total_uv       int
);
CREATE INDEX kt_read_snapshots_latest ON kt_read_snapshots (segment, collected_at DESC);

CREATE TABLE kt_read_rows (
    snapshot_id  bigint   NOT NULL REFERENCES kt_read_snapshots (id) ON DELETE CASCADE,
    url          text     NOT NULL,
    page_views   int      NOT NULL,
    unique_users int,
    rank         smallint NOT NULL,             -- 응답 순서 1부터 (홈페이지 포함)
    PRIMARY KEY (snapshot_id, url)
);

CREATE TABLE kt_read_articles (                 -- 보존: 마지막으로 본 날부터 30일
    url            text PRIMARY KEY,
    title          text,
    published_date date,                        -- URL의 /YYYYMMDD/
    excluded       boolean     NOT NULL,        -- 기사 URL 패턴 불일치 (홈페이지·섹션)
    first_seen_at  timestamptz NOT NULL,
    last_seen_at   timestamptz NOT NULL
);
```

- [ ] **Step 1: 실패하는 테스트 작성** (`pytestmark = pytest.mark.db`, 기존 `conn` fixture 사용)

```python
async def test_api_calls_accepts_marfeel(conn): await conn.execute("INSERT INTO api_calls (target, endpoint, purpose, clock_time) VALUES ('marfeel','/api/dashboard/query','rt_domestic',$1)", T0)
async def test_api_calls_rejects_unknown_target(conn): with pytest.raises(asyncpg.CheckViolationError): ... 'ga4' ...
async def test_snapshot_status_check(conn): with pytest.raises(asyncpg.CheckViolationError): ... status 'partial' ...
async def test_rows_cascade_with_snapshot(conn): 스냅샷 1 + 행 2 삽입 → 스냅샷 행을 지우면 kt_read_rows가 0행  # 테스트 안의 DELETE는 허용(tests/)
```

- [ ] **Step 2: 실패 확인** — `make db-up && uv run pytest -m db tests/db/test_marfeel_schema.py -v` → FAIL
- [ ] **Step 3: 위 SQL로 `0003_marfeel_reads.sql`을 쓴다.** 머리 주석은 0002와 같은 형식으로, 출처인 설계 4.2를 적는다. 시작 전에 실제 제약 이름이 `api_calls_target_check`인지 `\d api_calls`로 확인한다. 다르면 실제 이름을 쓴다.
- [ ] **Step 4: `tests/scenario/conftest.py`의 `ALL_TABLES` 앞쪽에 `kt_read_rows, kt_read_snapshots, kt_read_articles,`를 추가한다.**
- [ ] **Step 5: 통과 확인** — `uv run pytest -m db tests/db -v` → PASS (기존 `test_migrate`·`test_schema` 포함)
- [ ] **Step 6: 커밋** — `git commit -m "feat(db): marfeel read tables (0003)"`

### Task 3: 도메인 — 쿼리 조립·응답 해석·주기 판정

**Files:**
- Create: `wire_desk/domain/marfeel.py`
- Test: `tests/unit/test_marfeel_domain.py`

**Interfaces:**
- Produces:

```python
Segment = Literal["domestic", "overseas"]
SnapshotStatus = Literal["ok", "rate_limited", "invalid", "error"]

@dataclass(frozen=True)
class ReadRow:
    url: str
    title: str | None
    page_views: int
    unique_users: int | None
    rank: int                      # pageViewsTotal 응답 순서, 1부터

@dataclass(frozen=True)
class SegmentResult:
    segment: Segment
    status: SnapshotStatus
    total_pv: int | None = None
    total_uv: int | None = None
    rows: tuple[ReadRow, ...] = ()
    error: str | None = None

class MarfeelFormatError(ValueError): ...

def build_query(segment: Segment, *, country_id: str, window_minutes: int, limit: int, with_title: bool) -> dict[str, Any]
def parse_response(body: object) -> tuple[int | None, int | None, tuple[ReadRow, ...]]   # (total_pv, total_uv, rows)
def is_article_url(url: str, pattern: re.Pattern[str]) -> bool
def published_date(url: str) -> date | None
def judge_pair(domestic: SegmentResult, overseas: SegmentResult) -> tuple[SegmentResult, SegmentResult]
```

- [ ] **Step 1: 실패하는 테스트 작성.** 응답 픽스처는 실측 응답 형식(`marfeel-data-scope.md` 8절)을 따르는 합성 값으로 테스트 파일 안에 둔다.

```python
def test_build_query_domestic():
    q = build_query("domestic", country_id="1835841", window_minutes=30, limit=200, with_title=True)
    assert q["filters"] == [{"filter": "country", "op": "eq", "value": ["1835841"]}]
    assert q["dates"] == {"last": {"number": 30, "dimension": "minute"}}
    assert q["granularity"] == "realtime" and q["groupBy"] == ["url", "title"]
    assert q["metrics"] == ["pageViewsTotal", "uniqueUsers"]
    assert q["order"] == {"metric": "pageViewsTotal", "sort": "DESC"} and (q["limit"], q["from"]) == (200, 0)
def test_build_query_overseas_neq_without_title():
    q = build_query("overseas", country_id="1835841", window_minutes=30, limit=200, with_title=False)
    assert q["filters"][0]["op"] == "neq" and q["groupBy"] == ["url"]
def test_parse_joins_metrics_by_key():   # PV 객체와 UV 객체의 같은 key를 한 행으로, rank는 PV 순서
    total_pv, total_uv, rows = parse_response(BODY_TWO_METRICS)
    assert (total_pv, total_uv) == (3682, 2595)
    assert rows[0] == ReadRow(url=HOME, title="The Korea Times", page_views=719, unique_users=472, rank=1)
    assert rows[1].url.endswith("/20261022/sample-article") and rows[1].rank == 2
def test_parse_title_missing_is_none(): 제목 item 없는 응답 → rows[0].title is None
def test_parse_homepage_only_is_ok(): 홈페이지 1행만 → rows 1개, 예외 없음
def test_parse_empty_values(): values == [] → (0, 0, ())
def test_parse_bad_shape_raises(): with pytest.raises(MarfeelFormatError): parse_response({"msg": "x"})
def test_is_article_url():
    p = re.compile(r"/\d{8}/")
    assert is_article_url("https://www.koreatimes.co.kr/southkorea/20261022/x", p)
    assert not is_article_url("https://www.koreatimes.co.kr", p)
def test_published_date(): assert published_date("https://x/a/20261022/y") == date(2026, 10, 22); assert published_date("https://x") is None
def test_judge_pair_equal_totals_invalid():
    d, o = judge_pair(SegmentResult("domestic", "ok", 3000, 2000), SegmentResult("overseas", "ok", 3000, 2000))
    assert (d.status, o.status, d.error, o.error) == ("invalid", "invalid", "filter_ignored", "filter_ignored")
def test_judge_pair_normal_untouched(): (1275, 597) / (2670, 2167) → 둘 다 "ok"
def test_judge_pair_zero_both_ok(): 두 구간 모두 total 0 → 둘 다 "ok" (조용한 시간대)
def test_judge_pair_skips_non_ok(): 한쪽이 rate_limited면 다른 쪽을 바꾸지 않는다
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/unit/test_marfeel_domain.py -v` → ImportError
- [ ] **Step 3: 구현**
  - `parse_response`의 입력은 지표 객체 리스트다. `metric`, `total`, `actualData.values[].{key,total,items[].{type,value}}`를 읽는다.
  - 행 순서와 rank는 `pageViewsTotal` 객체의 `values` 순서를 따른다. `uniqueUsers`는 key로 붙인다.
  - `pageViewsTotal` 객체가 없거나 형식이 다르면 `MarfeelFormatError`를 낸다.
  - `judge_pair`의 무시 판정: 두 구간이 모두 `ok`이고, `total_pv`가 같고, 그 값이 0보다 클 때만 `invalid`로 바꾼다.
- [ ] **Step 4: 통과 확인** — `uv run pytest tests/unit/test_marfeel_domain.py -v && uv run ruff check wire_desk/domain` → PASS
- [ ] **Step 5: 커밋** — `git commit -m "feat(domain): marfeel query/parse/judge"`

### Task 4: 어댑터 — Marfeel 클라이언트와 호출 간격 장치

**Files:**
- Create: `wire_desk/adapters/marfeel_client.py`
- Create: `wire_desk/adapters/marfeel_gate.py`
- Test: `tests/unit/marfeel/test_client.py` (`httpx.MockTransport`, 소켓 없음)
- Test: `tests/db/test_marfeel_gate.py`

**Interfaces:**
- Consumes: `ApiCall`, `ApiCallRecorder` (`wire_desk.adapters.herb_client`), `PgApiCallRecorder(pool, target="marfeel")`, `Clock`
- Produces:

```python
SIGNIN_PATH = "/api/user/signin"      # 본문 {"email","password"} → {"token": str}
QUERY_PATH = "/api/dashboard/query"

class MarfeelError(Exception):
    code: str                          # 짧은 코드: rate_limited|no_data|http_<n>|connect|timeout|bad_response|signin_failed
class MarfeelRateLimited(MarfeelError): ...   # code="rate_limited"
class MarfeelNoData(MarfeelError): ...        # HTTP 204, code="no_data"

class CallGate(Protocol):
    async def wait_turn(self) -> None: ...    # 반환 후 바로 1회 호출해도 되는 시점
    def mark_called(self) -> None: ...        # 호출을 보낸 직후 (성공·실패 무관)

class PgCallGate:
    def __init__(self, pool: asyncpg.Pool, clock: Clock, *, min_interval_seconds: float,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None

class MarfeelClient:
    def __init__(self, *, http: httpx.AsyncClient, email: str, password: str, clock: Clock,
                 gate: CallGate, recorder: ApiCallRecorder, token_max_age: timedelta,
                 monotonic: Callable[[], float] = time.monotonic) -> None
    async def query(self, body: Mapping[str, Any], *, purpose: str) -> object   # 200 JSON 본문

@asynccontextmanager
async def build_marfeel_client(settings: MarfeelSettings, clock: Clock, pool: asyncpg.Pool) -> AsyncIterator[MarfeelClient]
```

- [ ] **Step 1: 실패하는 클라이언트 테스트 작성** (게이트는 호출 수를 세는 가짜로 대체)

```python
async def test_signs_in_once_then_reuses_token(): 질의 2회 → signin 1회, 두 query 요청 모두 Authorization: Bearer <token>
async def test_every_request_passes_gate(): signin+query 2회 → gate.wait_turn 3회, mark_called 3회
async def test_401_resigns_in_once(): 첫 query 401 → signin 재실행 → 재요청 200. 둘째도 401이면 MarfeelError(code="http_401")
async def test_429_raises_without_retry(): query 429 → MarfeelRateLimited, 전송된 query 요청 1회
async def test_204_raises_no_data(): → MarfeelNoData
async def test_5xx_and_connect_errors_coded(): 503 → code "http_503", ConnectError → "connect", 시간초과 → "timeout"
async def test_token_refreshed_after_max_age(): FakeClock 13일+1초 경과 → 다음 query 전에 signin
async def test_records_calls_without_secrets(): recorder 기록의 endpoint는 경로 상수, purpose는 "signin"/전달값, repr에 비밀번호·토큰 없음
async def test_signin_bad_body(): signin 200인데 token 없음 → MarfeelError(code="bad_response"), 로그에 본문 없음
```

- [ ] **Step 2: 실패하는 게이트 테스트 작성** (`pytest.mark.db`)

```python
async def test_gate_first_call_no_wait(pool): api_calls 비어 있음 → sleeper 호출 없음
async def test_gate_waits_for_db_recorded_call(pool):   # Review Focus 2: 재시작 시나리오
    api_calls에 target='marfeel', wall_time = clock.wall_now() - 20초 행 삽입 (새 PgCallGate 인스턴스)
    → sleeper가 45초(±1)로 1회 호출됨
async def test_gate_ignores_other_targets(pool): target='herb' 최근 행 → 기다리지 않음
async def test_gate_uses_memory_when_db_record_missing(pool): mark_called() 후 DB 기록 없이 wait_turn → monotonic 기준 65초 대기
```

- [ ] **Step 3: 실패 확인** — `uv run pytest tests/unit/marfeel -v` / `uv run pytest -m db tests/db/test_marfeel_gate.py -v` → FAIL
- [ ] **Step 4: `PgCallGate` 구현**
  - 대기 시간은 다음 두 값 중 큰 쪽이다.
    - (a) `clock.wall_now() - SELECT max(wall_time) FROM api_calls WHERE target='marfeel'`로 구한 남은 시간
    - (b) 마지막 `mark_called()`의 monotonic 시각으로 구한 남은 시간
  - 대기는 `asyncio.Lock` 안에서 한다.
  - DB 조회가 실패하면 (b)만 쓰고, 경고 로그를 남긴다.
  - SQL에 `now()`를 쓰지 않는다.
- [ ] **Step 5: `MarfeelClient`·`build_marfeel_client` 구현**
  - 모든 요청(signin 포함)은 `await gate.wait_turn()`으로 시작하고, 전송 직후 `gate.mark_called()`를 부른다.
  - api_calls 기록은 `HerbClient._record`와 같은 형식이다. 기록에 실패해도 호출은 실패하지 않는다.
  - 토큰 나이는 `clock.now()` 기준이다.
  - `build_marfeel_client`는 `httpx.AsyncClient(base_url=settings.base_url, timeout=settings.timeout_seconds)`, `PgCallGate(pool, clock, min_interval_seconds=settings.min_call_interval_seconds)`, `PgApiCallRecorder(pool, target="marfeel")`를 조립한다.
- [ ] **Step 6: 통과 확인** — `uv run pytest tests/unit/marfeel -v && uv run pytest -m db tests/db/test_marfeel_gate.py -v && make check` → PASS
- [ ] **Step 7: 커밋** — `git commit -m "feat(adapters): marfeel client and call gate"`

### Task 5: 저장소와 poller (한 주기, 실패 알림, 단일 실행)

**Files:**
- Create: `wire_desk/adapters/db/kt_reads.py`
- Create: `wire_desk/lanes/marfeel_poll.py`
- Test: `tests/db/test_kt_reads.py`
- Test: `tests/scenario/test_marfeel_poll.py` (`MockTransport` + 실제 Postgres + `FakeClock`)

**Interfaces:**
- Consumes: Task 3 `SegmentResult`·`build_query`·`parse_response`·`judge_pair`·`is_article_url`·`published_date`, Task 4 `MarfeelClient`·`MarfeelError`·`MarfeelRateLimited`·`MarfeelNoData`, `notify_admins(conn, *, kind="system", message, now)`
- Produces:

```python
# adapters/db/kt_reads.py
async def save_segment(conn: Conn, result: SegmentResult, *, collected_at: datetime,
                       window_minutes: int, article_pattern: re.Pattern[str]) -> int   # snapshot id
#   한 트랜잭션: kt_read_snapshots 1행, kt_read_rows 전부, kt_read_articles upsert
#   (title은 새 값이 None이 아닐 때만 갱신, last_seen_at 갱신, excluded = not is_article_url)

# lanes/marfeel_poll.py
MARFEEL_LOCK_KEY = 0x4D52464C          # pg advisory lock 키 ("MRFL")

class SnapshotSink(Protocol):
    def write(self, result: SegmentResult, *, collected_at: datetime) -> None: ...

@dataclass(frozen=True)
class MarfeelPollConfig:
    poll_seconds: float = 300
    poll_offset_seconds: float = 60
    window_minutes: int = 30
    limit: int = 200
    country_id: str = "1835841"
    article_url_pattern: str = r"/\d{8}/"
    with_title: bool = True
    alert_after_failed_cycles: int = 3
    @classmethod
    def from_settings(cls, s: MarfeelSettings) -> "MarfeelPollConfig"

class MarfeelPoller:
    def __init__(self, *, client: MarfeelClient, pool: asyncpg.Pool, clock: Clock,
                 config: MarfeelPollConfig, sink: SnapshotSink | None = None) -> None
    async def run_cycle(self) -> tuple[SegmentResult, SegmentResult]
    async def run(self, stop: asyncio.Event, *, until: datetime | None = None) -> None
```

- `run_cycle` 순서
  1. 국내를 질의한다. `MarfeelRateLimited`가 나면 해외는 보내지 않고 둘 다 `rate_limited`로 저장한다.
  2. 국내가 다른 이유로 실패해도 해외는 질의한다. 해외 질의는 게이트가 65초 뒤로 미룬다.
  3. `judge_pair`를 적용하고, 두 구간을 저장한 뒤 sink에 쓴다.
  - 오류는 다음과 같이 저장한다. `MarfeelNoData`는 `invalid`/`no_data`, `MarfeelFormatError`는 `invalid`/`bad_shape`, 그 밖의 `MarfeelError`는 `error`/`code`다.
  - 두 구간이 모두 `ok`가 아니면 연속 실패 수를 1 늘린다. 연속 실패가 `alert_after_failed_cycles`가 된 주기에 알림을 1회 보낸다. 정상 주기가 오면 0으로 되돌린다.
  - **설계와 다른 점:** 설계 4.6 표는 204와 검증 실패에 바로 알림을 보내라고 한다. 이 계획은 모든 실패 종류를 "3주기 연속" 기준 하나로 통일한다. 5분마다 같은 알림이 쌓이지 않게 하려는 것이다. 즉시 알림이 필요하면 `alert_after_failed_cycles=1`로 설정한다.
- `run` 동작
  - 전용 연결에서 `pg_try_advisory_lock(MARFEEL_LOCK_KEY)`를 시도한다. 실패하면 경고 로그를 남기고 `poll_seconds`마다 다시 시도하며, 그동안 호출하지 않는다.
  - 다음 주기 시작은 `Clock` 기준 `poll_seconds` 경계에 `poll_offset_seconds`를 더한 시각이다(예: 11:01:00, 11:06:00).
  - `stop`이 세워지거나 `until`이 지나면 끝난다. 예외는 로그를 남기고 다음 주기로 넘어간다.

- [ ] **Step 1: 실패하는 저장소 테스트 작성** (`pytest.mark.db`)

```python
async def test_save_segment_writes_snapshot_rows_articles(conn): ok 결과(홈페이지 + 기사 2) → 스냅샷 1, rows 3, articles 3(홈페이지 excluded=True, 기사 published_date 2026-10-22)
async def test_save_segment_keeps_title_when_new_is_none(conn): 같은 URL을 title=None으로 다시 저장 → 기존 title 유지, last_seen_at 갱신, first_seen_at 유지
async def test_save_failed_segment_no_rows(conn): status rate_limited → 스냅샷 1행(total NULL), rows 0
```

- [ ] **Step 2: 실패하는 시나리오 테스트 작성** (`pytest.mark.scenario`, MockTransport가 요청 본문의 `op`로 국내·해외 응답을 고른다. 게이트는 대기 없는 가짜)

```python
async def test_cycle_stores_both_segments(...): 스냅샷 2행(ok), 국내 rows가 국내 응답과 같음
async def test_rate_limited_skips_overseas(...): 국내 429 → 해외 query 요청 0회, 두 스냅샷 rate_limited
async def test_filter_ignored_marks_invalid(...): 같은 합계 응답 → 두 스냅샷 invalid/filter_ignored
async def test_quiet_cycle_is_ok(...): 홈페이지만 있는 응답 → ok, 연속 실패 0, notices 0
async def test_alert_after_three_failed_cycles(...): 503 3주기 → notices 1건(kind system), 4번째 실패에도 추가 알림 없음, 정상 1주기 후 카운터 0
async def test_second_poller_does_not_call(...):   # Review Focus 1
    poller A가 run 중(lock 보유) → poller B.run을 짧게 돌림 → B 쪽 transport 요청 0회
async def test_run_stops_at_until(...): FakeClock으로 until 도달 → run 반환
async def test_sink_receives_each_segment(...): 리스트 sink에 2건, collected_at = clock.now()
```

- [ ] **Step 3: 실패 확인** — `uv run pytest -m db tests/db/test_kt_reads.py -v`, `uv run pytest -m scenario tests/scenario/test_marfeel_poll.py -v` → FAIL
- [ ] **Step 4: `kt_reads.save_segment` 구현** (upsert는 `INSERT ... ON CONFLICT (url) DO UPDATE`, 시각은 파라미터)
- [ ] **Step 5: `MarfeelPoller` 구현** (위 순서와 동작)
- [ ] **Step 6: 통과 확인** — 두 명령 재실행 + `make check` → PASS
- [ ] **Step 7: 커밋** — `git commit -m "feat(lanes): marfeel poller with store, alerts, single-runner lock"`

### Task 6: worker 연결과 녹화 실행기

**Files:**
- Modify: `wire_desk/lanes/jobs.py` (`JobsLane.__init__`에 `marfeel: MarfeelPoller | None = None`, `run`에서 함께 실행)
- Modify: `wire_desk/worker.py` (Marfeel 설정 로드·검증·조립)
- Create: `wire_desk/marfeel_record.py`
- Modify: `.gitignore` (`fixtures/marfeel/recordings/`), `tests/static/test_gitignore.py` (해당 경로 검사 추가)
- Modify: `docs/guides/development.md` (녹화 실행 절)
- Test: `tests/unit/test_marfeel_record.py`, `tests/scenario/test_worker.py`(기존 파일에 추가)

**Interfaces:**
- Consumes: Task 1 `load_marfeel_settings`, `MARFEEL_HOSTS`. Task 4 `build_marfeel_client`. Task 5 `MarfeelPoller`, `MarfeelPollConfig`, `SnapshotSink`.
- Produces:

```python
# worker.py
def check_marfeel_mode(settings: Settings, marfeel: MarfeelSettings) -> None   # 위반 시 SettingsError
#   enabled이고 clock_mode == "replay"인데 base_url.host != "mock-marfeel" → 거부

# marfeel_record.py   실행: python -m wire_desk.marfeel_record --hours 48
class JsonlSink:                      # SnapshotSink 구현
    def __init__(self, directory: Path, *, started_at: datetime) -> None   # 파일: <directory>/<YYYYMMDD-HHMM>.jsonl
    def write(self, result: SegmentResult, *, collected_at: datetime) -> None
#   한 줄 = {"collected_at": ISO8601, "segment", "status", "error", "total_pv", "total_uv",
#            "rows": [{"url","title","page_views","unique_users","rank"}]}  (비밀값 없음)
async def run_recording(settings: Settings, marfeel: MarfeelSettings, *, hours: float, stop: asyncio.Event) -> None
#   RealClock 고정, 마이그레이션 적용(worker와 같은 방식), enabled 무시하고 자격증명 필수,
#   poller.run(stop, until=start + hours)
```

- JobsLane 동작: `marfeel`이 있으면 `run()`이 기존 루프와 `marfeel.run(stop)`을 `asyncio.TaskGroup`으로 함께 돌린다. poller 예외는 poller 안에서 처리되므로 jobs 큐 처리를 막지 않는다.
- worker 동작
  - `marfeel.enabled`이면 `check_marfeel_mode`를 적용한 뒤 `build_marfeel_client`로 poller를 만들어 JobsLane에 넘긴다.
  - 꺼져 있으면 기존 동작과 완전히 같다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_replay_with_real_marfeel_host_rejected():   # Review Focus 5
    with pytest.raises(SettingsError): check_marfeel_mode(replay_settings, MarfeelSettings(enabled=True, email="a@b.c", secret="s"*16))
def test_replay_with_mock_host_allowed(): base_url="http://mock-marfeel:9100" → 예외 없음
def test_real_mode_allowed(): clock_mode="real" + 실제 호스트 → 예외 없음
def test_disabled_never_rejected(): enabled=False면 어떤 조합도 통과
def test_jsonl_sink_line_shape(tmp_path): write 2회 → 2줄, 키 집합이 위 정의와 같음, collected_at에 +09:00
def test_jsonl_sink_has_no_secret(tmp_path): 파일 텍스트에 MARFEEL_SECRET 값 없음
# tests/scenario/test_worker.py
async def test_jobs_lane_runs_marfeel_poller(...): 가짜 poller를 넘긴 JobsLane.run → poller.run 호출됨, stop 후 둘 다 종료
async def test_jobs_lane_without_marfeel_unchanged(...): 기존 테스트와 같은 결과
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/unit/test_marfeel_record.py -v && uv run pytest -m scenario tests/scenario/test_worker.py -v` → FAIL
- [ ] **Step 3: `check_marfeel_mode`·JobsLane 변경·worker 조립 구현**
- [ ] **Step 4: `JsonlSink`·`run_recording`·`main()` 구현.** argparse 인자는 `--hours`(float, 기본 48), `--dir`(기본 `recordings_dir`)다. SIGTERM과 SIGINT를 받으면 stop을 세운다. 시작·종료·주기마다 `status` 요약을 로그로 남긴다.
- [ ] **Step 5: `.gitignore`와 `test_gitignore.py` 파라미터에 `fixtures/marfeel/recordings/x.jsonl`을 추가한다. `development.md`에는 녹화 실행 명령, 필요한 환경변수, "worker의 Marfeel과 동시에 켜지 않는다(켜도 lock으로 한쪽만 호출)"를 적는다.**
- [ ] **Step 6: 통과 확인** — `make test` → PASS (check + db + scenario)
- [ ] **Step 7: 커밋** — `git commit -m "feat(worker): marfeel poller in jobs lane, recording runner"`

### Task 7: T0 확인과 48시간 녹화 시작 (실제 API, 수동)

**Files:**
- Modify: `docs/jobs/YYYY-MM-DD.md` (wire-desk 작업일지, 실행 결과)
- Modify(조건부): `wire_desk/config.py` 기본값 (`with_title`, `limit`)

**Interfaces:**
- Consumes: Task 6 `python -m wire_desk.marfeel_record`

이 Task는 실제 계정 한도를 쓴다. 시작 전에 사용자에게 시작 시각을 알린다(설계 10절 #4: 계정 공유 확인).

- [ ] **Step 1: 짧은 녹화로 T0 확인** — `.env.wire`에 Marfeel 자격증명을 넣고 `uv run python -m wire_desk.marfeel_record --hours 0.25`를 실행한다. 3주기, 약 6회 호출이다. 확인할 것은 다음 셋이다.
  1. T0-1: JSONL `rows[].title`이 채워졌는가. 모두 `null`이면 `with_title` 기본값을 `False`로 바꾸고 일지에 기록한다.
  2. T0-2: 로그인 직후 첫 질의가 429가 아닌가. 게이트가 로그인도 65초로 띄우므로 정상이면 문제가 없다. 결과만 기록한다.
  3. T0-3: 국내·해외 `rows` 수가 200에 닿는가. 닿으면 PV 200위의 값을 기록한다. 200위의 PV가 1위의 1% 미만이면 200을 유지한다. 그렇지 않으면 `limit`을 500으로 올린다.
  - 기대: 6개 스냅샷이 모두 `ok`, `api_calls`의 `target='marfeel'` 간격이 모두 65초 이상(`SELECT wall_time ... ORDER BY 1` 차분으로 확인)
- [ ] **Step 2: 기본값 변경이 있으면 커밋** — `git commit -m "chore(config): marfeel defaults from T0"`
- [ ] **Step 3: 48시간 녹화 시작** — `nohup uv run python -m wire_desk.marfeel_record --hours 48 > /tmp/marfeel_record.log 2>&1 &`. 평일이 포함되게 시작한다.
- [ ] **Step 4: 종료 후 기록.** 작업일지에 시작·종료 시각, 주기 성공률(두 구간 모두 `ok`인 주기 비율, 목표 ≥ 95%), 429 횟수, 60초 안 연속 호출 수(목표 0), JSONL 파일 경로를 적는다. 이 값이 이후 G19-①·②의 입력이다.

---

## 실행 순서와 의존

Task 1 → 2 → 3 → 4 → 5 → 6 → 7. Task 3은 Task 1·2와 독립이라 먼저 해도 된다. Task 7은 사람이 시작을 확인한 뒤 진행한다.
