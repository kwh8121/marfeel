#!/usr/bin/env python3
"""Search Console 일별 원본 수집 스크립트(읽기 전용). 표준 라이브러리만 사용한다.

가장 오래된 날부터 하루 × 검색 유형별로 받아 원본 그대로 gzip JSON으로 저장한다.
  data/searchconsole/raw/{searchType}/{YYYY-MM-DD}.json.gz
이미 받은 파일은 건너뛰므로 중단 후 다시 실행하면 이어 받는다. 파일은 덮어쓰지 않는다.
Search Console 보존이 16개월이라 오래된 날부터 사라진다. 먼저 받아 쌓는 것이 목적이다.

인증은 searchconsole_check.py의 auth로 받은 토큰을 쓴다(저장소 밖).
차원: web·news = date, query, page, country / discover·googleNews = date, page, country
(discover·googleNews는 검색어 차원이 없다. 공식 문서 기준이며 이 속성에서 실측하지 않았다.)
"""
import argparse
import fcntl
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from searchconsole_check import API, DEFAULT_CLIENT, DEFAULT_SITE, DEFAULT_TOKEN, access_token

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "searchconsole"
PAGE = 25000          # 요청당 최대 행 수
TIMEOUT = 120
MAX_RETRIES = 4
TOKEN_MAX_AGE = 45 * 60  # 액세스 토큰은 1시간. 45분마다 갱신
LAG_DAYS = 3          # 최근 며칠은 데이터가 확정되지 않는다(추정). 기본 종료일에서 뺀다
RETRY_EMPTY_DAYS = 7   # 최근 며칠의 빈 응답은 저장하지 않는다
START_OFFSET_DAYS = 485 # 보존 약 16개월. 가장 오래된 날에서 오류가 나면 --start로 조정
DIMS = {
    "web": ["date", "query", "page", "country"],
    "news": ["date", "query", "page", "country"],
    "discover": ["date", "page", "country"],
    "googleNews": ["date", "page", "country"],
}


def post(token, url, body):
    data = json.dumps(body).encode()
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 2))
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 2))
                continue
            raise RuntimeError(f"네트워크 오류: {e}")


def fetch_day(token, site, day, stype):
    url = f"{API}/sites/{urllib.parse.quote(site, safe='')}/searchAnalytics/query"
    rows, start, agg = [], 0, None
    while True:
        body = {"startDate": day, "endDate": day, "dimensions": DIMS[stype], "searchType": stype,
                "rowLimit": PAGE, "startRow": start, "dataState": "final"}
        res = post(token, url, body)
        agg = res.get("responseAggregationType", agg)
        got = res.get("rows", [])
        rows.extend(got)
        if len(got) < PAGE:
            return rows, agg
        start += PAGE


def save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client-json", default=str(DEFAULT_CLIENT))
    ap.add_argument("--token-file", default=str(DEFAULT_TOKEN))
    ap.add_argument("--site", default=DEFAULT_SITE)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--start", help="YYYY-MM-DD. 기본: 오늘 - 485일")
    ap.add_argument("--end", help="YYYY-MM-DD. 기본: 오늘 - 3일")
    ap.add_argument("--search-types", default="web,news,discover,googleNews")
    ap.add_argument("--sleep", type=float, default=0.5, help="호출 사이 대기(초)")
    ap.add_argument("--max-days", type=int, help="이번 실행에서 받을 최대 일수(시험용)")
    args = ap.parse_args()

    today = date.today()
    end = date.fromisoformat(args.end) if args.end else today - timedelta(days=LAG_DAYS)
    types = [t.strip() for t in args.search_types.split(",") if t.strip()]
    for t in types:
        if t not in DIMS:
            sys.exit(f"알 수 없는 검색 유형: {t}")
    out = Path(args.out)
    if args.start:
        start = date.fromisoformat(args.start)
    else:
        # 증분: 이미 받은 가장 오래된 날부터 훑는다. 받은 파일은 건너뛰므로 중간에 빠진 날도 채운다.
        # 파일이 없는 유형이 있으면 처음부터 받는다.
        firsts = []
        for t in types:
            files = sorted((out / "raw" / t).glob("*.json.gz"))
            firsts.append(date.fromisoformat(files[0].name[:10]) if files
                          else today - timedelta(days=START_OFFSET_DAYS))
        start = min(firsts)
    out.mkdir(parents=True, exist_ok=True)
    lock = open(out / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("다른 수집이 실행 중이다.")

    token, token_at = access_token(args), time.time()
    done = skipped = empty = 0
    day = start
    while day <= end:
        for stype in types:
            path = out / "raw" / stype / f"{day.isoformat()}.json.gz"
            if path.exists():
                skipped += 1
                continue
            if args.max_days is not None and done >= args.max_days:
                print(f"--max-days {args.max_days} 도달. 받음 {done}, 건너뜀 {skipped}, 빈 날 {empty}")
                return
            if time.time() - token_at > TOKEN_MAX_AGE:
                token, token_at = access_token(args), time.time()
            try:
                rows, agg = fetch_day(token, args.site, day.isoformat(), stype)
            except RuntimeError as e:
                print(f"중단: {day} {stype}: {e}\n받음 {done}, 건너뜀 {skipped}", file=sys.stderr)
                sys.exit(1)
            if not rows and (today - day).days <= RETRY_EMPTY_DAYS:
                print(f"{day} {stype:10s} 빈 응답: 아직 확정 전일 수 있어 저장하지 않고 다음 실행에서 다시 받는다")
                continue
            save(path, {"site": args.site, "date": day.isoformat(), "searchType": stype,
                        "dimensions": DIMS[stype], "responseAggregationType": agg,
                        "fetchedAt": datetime.now(timezone.utc).isoformat(),
                        "rowCount": len(rows), "rows": rows})
            done += 1
            empty += not rows
            print(f"{day} {stype:10s} {len(rows):6d}행")
            time.sleep(args.sleep)
        day += timedelta(days=1)
    print(f"완료. 받음 {done}, 건너뜀 {skipped}, 빈 날 {empty}")


if __name__ == "__main__":
    main()
