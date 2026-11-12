#!/usr/bin/env python3
"""GA4 일별 페이지 경로별 PV 원본 수집(읽기 전용). 표준 라이브러리만 사용한다.

하루 × pagePath별 screenPageViews·activeUsers를 원본 그대로 gzip JSON으로 저장한다.
  data/ga4/raw/pagepath/{YYYY-MM-DD}.json.gz
저장 항목에 (other) 행 손실 여부(dataLossFromOtherRow)와 (other) PV 비중을 함께 남긴다.
받은 날은 건너뛴다. 단 최근 REFRESH_DAYS일은 GA4 후처리로 값이 바뀔 수 있어 매번 다시 받아 덮어쓴다.
인증은 searchconsole_check.py의 토큰(analytics.readonly)을 쓴다.

기본 범위: 2025-02-21(원장 시작) ~ 오늘 - 1일. --start·--end로 조정한다.
속성: 340662437 (0. GA4_코리아타임스_통합, Asia/Seoul)
"""
import argparse
import fcntl
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from searchconsole_check import DEFAULT_CLIENT, DEFAULT_TOKEN, access_token

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "ga4"
PROPERTY = "340662437"
DATA = "https://analyticsdata.googleapis.com/v1beta"
DEFAULT_START = "2025-02-21"
PAGE = 100000
TIMEOUT = 120
MAX_RETRIES = 4
TOKEN_MAX_AGE = 45 * 60
REFRESH_DAYS = 4      # 오늘 기준 이 일수 이내의 날은 다시 받는다
QUOTA_FLOOR = 2000    # 시간당 토큰이 이 아래로 남으면 멈춘다(프로젝트 시간당 14,000)


def post(token, body):
    data = json.dumps(body).encode()
    url = f"{DATA}/properties/{PROPERTY}:runReport"
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 3))
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 3))
                continue
            raise RuntimeError(f"네트워크 오류: {e}")


# 보고서 종류별 차원·지표. segment는 N3·G1용 국가 × 언어 세그먼트(기사 경로 포함)다.
REPORTS = {
    "pagepath": (["pagePath"], ["screenPageViews", "activeUsers"]),
    "segment": (["pagePath", "country", "languageCode"],
                ["screenPageViews", "activeUsers", "userEngagementDuration"]),
}


def fetch_day(token, day, report="pagepath"):
    dims, mets = REPORTS[report]
    rows, off, meta, quota = [], 0, {}, {}
    while True:
        res = post(token, {"dateRanges": [{"startDate": day, "endDate": day}],
                           "dimensions": [{"name": d} for d in dims],
                           "metrics": [{"name": m} for m in mets],
                           "limit": PAGE, "offset": off, "returnPropertyQuota": True})
        for x in res.get("rows", []):
            rows.append([d["value"] for d in x["dimensionValues"]]
                        + [int(m["value"]) for m in x["metricValues"]])
        meta = res.get("metadata", {})
        quota = res.get("propertyQuota", {})
        off += PAGE
        if off >= res.get("rowCount", 0):
            return rows, meta, quota


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
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", help="YYYY-MM-DD. 기본: 오늘 - 1일")
    ap.add_argument("--report", choices=sorted(REPORTS), default="pagepath",
                    help="pagepath(기본): 경로별 PV. segment: 경로 × 국가 × 언어 PV·사용자·참여 시간")
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--max-days", type=int, help="이번 실행에서 받을 최대 일수(시험용)")
    args = ap.parse_args()

    today = date.today()
    end = date.fromisoformat(args.end) if args.end else today - timedelta(days=1)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lock = open(out / (".lock" if args.report == "pagepath" else f".lock-{args.report}"), "w")  # 보고서별 락
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("다른 수집이 실행 중이다.")

    token, token_at = access_token(args), time.time()
    done = skipped = 0
    day = date.fromisoformat(args.start)
    while day <= end:
        path = out / "raw" / args.report / f"{day.isoformat()}.json.gz"
        if path.exists() and (today - day).days > REFRESH_DAYS:
            skipped += 1
            day += timedelta(days=1)
            continue
        if args.max_days is not None and done >= args.max_days:
            break
        if time.time() - token_at > TOKEN_MAX_AGE:
            token, token_at = access_token(args), time.time()
        try:
            rows, meta, quota = fetch_day(token, day.isoformat(), args.report)
        except RuntimeError as e:
            print(f"중단: {day}: {e}\n받음 {done}, 건너뜀 {skipped}", file=sys.stderr)
            sys.exit(1)
        nd = len(REPORTS[args.report][0])  # 차원 열 수. 첫 지표(PV)는 nd번째 열
        other_pv = sum(r[nd] for r in rows if "(other)" in r[:nd])
        total_pv = sum(r[nd] for r in rows)
        save(path, {"property": PROPERTY, "date": day.isoformat(), "report": args.report,
                    "dimensions": REPORTS[args.report][0], "metrics": REPORTS[args.report][1],
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                    "rowCount": len(rows), "totalPV": total_pv, "otherPV": other_pv,
                    "dataLossFromOtherRow": bool(meta.get("dataLossFromOtherRow")),
                    "samplingMetadatas": meta.get("samplingMetadatas"), "rows": rows})
        done += 1
        flag = " (other 손실)" if meta.get("dataLossFromOtherRow") else ""
        print(f"{day} {len(rows):6d}행 PV {total_pv:8d} other {other_pv / max(total_pv, 1):.1%}{flag}", flush=True)
        left = quota.get("tokensPerHour", {}).get("remaining")
        if left is not None and left < QUOTA_FLOOR:
            print(f"시간당 토큰 {left} 남음: 멈춘다. 다음 실행에서 이어 받는다.", file=sys.stderr)
            sys.exit(2)
        time.sleep(args.sleep)
        day += timedelta(days=1)
    print(f"완료. 받음 {done}, 건너뜀 {skipped}")


if __name__ == "__main__":
    main()
