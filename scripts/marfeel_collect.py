#!/usr/bin/env python3
"""Marfeel Reporting API 수집 스크립트.

docs/references/marfeel-queries/*.json 요청 본문을 순서대로 호출하고
원본 응답(JSON)과 그룹별 합계 표(CSV)를 저장한다. 표준 라이브러리만 사용한다.

자격 증명: .env 또는 환경변수의 MARFEEL_EMAIL, MARFEEL_SECRET.
토큰 캐시: ~/.cache/marfeel/state.json (권한 600). 저장소 안에 두지 않는다.
"""
import argparse
import csv
import fcntl
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIGNIN_URL = "https://api.newsroom.bi/api/user/signin"
QUERY_URL = "https://api.newsroom.bi/api/dashboard/query"
QUERY_DIR = ROOT / "docs" / "references" / "marfeel-queries"
DEFAULT_OUT = ROOT / "data" / "marfeel"

MIN_INTERVAL = 65  # 계정당 분당 1회 한도에 여유를 둔 호출 간격(초)
TOKEN_MAX_AGE = 13 * 24 * 3600  # 문서상 최대 14일. 정확히 14일을 보장하지 않으므로 13일에 갱신
TIMEOUT = 60
MAX_RETRIES = 3  # 429 재시도 횟수
MAX_ROWS = 500  # 응답당 최대 행 수
REQUIRED_FIELDS = ("dates", "filters", "groupBy", "metrics", "order")


class ApiError(Exception):
    pass


class NoData(ApiError):
    """HTTP 204. 잘못된 지표 이름만 보냈거나 데이터가 없을 때 돌아온다."""


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def load_env():
    """.env를 읽는다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        os.environ.setdefault(key.strip(), value)


def post_json(url, body, token=None):
    """(status, text)를 돌려준다. HTTP 오류 코드는 예외 대신 값으로 반환한다."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise ApiError(f"네트워크 오류: {e.reason}") from e


class State:
    """토큰과 마지막 호출 시각을 저장한다. 실행 간에도 호출 간격을 지키기 위해 파일에 둔다."""

    def __init__(self):
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
        self.dir = Path(base) / "marfeel"
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)
        self.path = self.dir / "state.json"
        self.data = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except ValueError:
                self.data = {}

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.path)


def signin(email, password):
    status, text = post_json(SIGNIN_URL, {"email": email, "password": password})
    if status != 200:  # 응답 본문에 사용자 정보가 있을 수 있어 출력하지 않는다
        raise ApiError(f"로그인 실패: HTTP {status}")
    try:
        token = json.loads(text).get("token")
    except (ValueError, AttributeError) as e:
        raise ApiError("로그인 응답 JSON 파싱 실패") from e
    if not isinstance(token, str) or not token.strip():
        raise ApiError("로그인 응답에 token이 없음")
    return token


def get_token(state, force=False):
    issued = state.data.get("issued_at", 0)
    token = state.data.get("token")
    if not force and token and time.time() - issued < TOKEN_MAX_AGE:
        return token
    email, password = os.environ.get("MARFEEL_EMAIL"), os.environ.get("MARFEEL_SECRET")
    if not email or not password:
        raise ApiError("MARFEEL_EMAIL / MARFEEL_SECRET이 설정되지 않음")
    log("토큰 발급 중...")
    state.data["token"] = signin(email, password)
    state.data["issued_at"] = time.time()
    state.save()
    return state.data["token"]


def throttle(state):
    wait = state.data.get("last_call_at", 0) + MIN_INTERVAL - time.time()
    if wait > 0:
        log(f"호출 한도 대기 {wait:.0f}초")
        time.sleep(wait)


def query(state, body):
    """401은 재인증 후 1회, 429는 MAX_RETRIES회까지 재시도한다."""
    reauthed = False
    retries = 0
    while True:
        throttle(state)
        token = get_token(state)
        status, text = post_json(QUERY_URL, body, token)
        state.data["last_call_at"] = time.time()
        state.save()
        if status == 200:
            try:
                return json.loads(text)
            except ValueError as e:
                raise ApiError("응답 JSON 파싱 실패") from e
        if status == 204:
            raise NoData("HTTP 204: 유효한 지표가 없거나 데이터 없음")
        if status == 401 and not reauthed:
            log("인증 오류(401): 토큰을 재발급하고 1회 재시도")
            get_token(state, force=True)
            reauthed = True
            continue
        if status == 429 and retries < MAX_RETRIES:
            retries += 1
            log(f"HTTP 429: 재시도 {retries}/{MAX_RETRIES}")
            continue
        # 403(rawData·amplify 권한 등)은 재시도해도 풀리지 않으므로 바로 보고한다
        raise ApiError(f"HTTP {status}: {text[:200]}")


def validate(body, name):
    missing = [f for f in REQUIRED_FIELDS if f not in body]
    if missing:
        raise ApiError(f"{name}: 필수 필드 누락 {missing}")
    if not body["metrics"]:
        raise ApiError(f"{name}: metrics가 비어 있음")
    if int(body.get("limit", 0)) > MAX_ROWS:
        raise ApiError(f"{name}: limit은 최대 {MAX_ROWS}")


def collect(state, body, max_pages):
    """페이지를 이어 받는다. 첫 지표의 행 수가 limit보다 적으면 마지막 페이지다."""
    limit = int(body.get("limit", MAX_ROWS))
    pages = []
    for i in range(max_pages):
        page_body = dict(body, **{"from": int(body.get("from", 0)) + i * limit})
        resp = query(state, page_body)
        pages.append(resp)
        rows = len(resp[0]["actualData"]["values"]) if resp else 0
        if rows < limit:
            break
    return pages


def flatten(pages):
    """그룹(key)별로 차원 값과 지표 합계(total)를 한 행으로 합친다."""
    rows, dims, metrics = {}, [], []
    for resp in pages:
        for m in resp:
            name = m["metric"]
            if name not in metrics:
                metrics.append(name)
            for v in m["actualData"]["values"]:
                row = rows.setdefault(v["key"], {})
                for item in v.get("items", []):
                    if item["type"] not in dims:
                        dims.append(item["type"])
                    value = item.get("value")
                    row[item["type"]] = "" if value is None else value
                row[name] = v.get("total")
    return dims + metrics, list(rows.values())


def write_outputs(out_dir, name, body, pages):
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    raw = {"query": name, "collected_at": stamp, "request": body, "pages": pages}
    (out_dir / f"{name}.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    columns, rows = flatten(pages)
    with open(out_dir / f"{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description="Marfeel Reporting API 수집")
    ap.add_argument("queries", nargs="*", type=Path, help="요청 본문 JSON (기본: marfeel-queries/*.json)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="출력 폴더 (기본: data/marfeel)")
    ap.add_argument("--max-pages", type=int, default=1, help="쿼리당 최대 페이지 수 (페이지마다 1분 소요)")
    ap.add_argument("--auth-only", action="store_true", help="토큰만 발급·확인하고 종료")
    args = ap.parse_args()

    load_env()
    state = State()
    lock = open(state.dir / "lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)  # 동시 실행 시 토큰 재발급·호출 한도 중복 방지

    try:
        get_token(state)
    except ApiError as e:
        log(f"오류: {e}")
        return 1
    age_h = (time.time() - state.data["issued_at"]) / 3600
    log(f"토큰 사용 가능 (발급 후 {age_h:.1f}시간 경과)")
    if args.auth_only:
        return 0

    paths = args.queries or sorted(QUERY_DIR.glob("*.json"))
    if not paths:
        log("실행할 쿼리가 없음")
        return 1
    out_dir = args.out / datetime.now().astimezone().strftime("%Y-%m-%d")

    failed = []
    for path in paths:
        name = path.stem
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            validate(body, name)
            log(f"[{name}] 수집 중")
            pages = collect(state, body, args.max_pages)
            n = write_outputs(out_dir, name, body, pages)
            log(f"[{name}] {n}행 저장 -> {out_dir}")
        except (ApiError, ValueError, OSError) as e:
            log(f"[{name}] 실패: {e}")
            failed.append(name)
    if failed:
        log(f"실패 {len(failed)}건: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
