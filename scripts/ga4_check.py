#!/usr/bin/env python3
"""GA4 연결 확인 스크립트(읽기 전용). 표준 라이브러리만 사용한다.

searchconsole_check.py auth로 받은 토큰을 쓴다(analytics.readonly 범위가 들어 있어야 한다).
  1) Admin API accountSummaries로 접근 가능한 계정·속성을 나열한다.
  2) --property 를 주면 그 속성의 하루치 runReport(국가 × 언어)를 1회 호출해 요약을 출력한다.
응답 원본은 저장하지 않는다.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

from searchconsole_check import DEFAULT_CLIENT, DEFAULT_TOKEN, access_token

ADMIN = "https://analyticsadmin.googleapis.com/v1beta"
DATA = "https://analyticsdata.googleapis.com/v1beta"
TIMEOUT = 60


def call(token, method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        hint = ""
        if e.code in (401, 403):
            hint = "\n토큰에 analytics.readonly 범위가 없거나 속성 권한이 없을 수 있다. 토큰 파일을 지우고 searchconsole_check.py auth를 다시 실행한다."
        sys.exit(f"HTTP {e.code} {url}\n{e.read().decode()[:400]}{hint}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client-json", default=str(DEFAULT_CLIENT))
    ap.add_argument("--token-file", default=str(DEFAULT_TOKEN))
    ap.add_argument("--property", help="속성 ID(숫자). 목록에서 확인한 값")
    ap.add_argument("--date", help="YYYY-MM-DD. 기본: 4일 전")
    args = ap.parse_args()

    tok = access_token(args)
    res = call(tok, "GET", f"{ADMIN}/accountSummaries")
    print("[accountSummaries]")
    for a in res.get("accountSummaries", []):
        print(f"  계정 {a.get('displayName')} ({a.get('account')})")
        for p in a.get("propertySummaries", []):
            print(f"    {p['property']}  {p.get('displayName')}")
    if not args.property:
        print("속성 ID를 --property 로 지정하면 하루치 조회를 호출한다.")
        return
    day = args.date or (date.today() - timedelta(days=4)).isoformat()
    meta = call(tok, "GET", f"{DATA}/properties/{args.property}/metadata")
    print(f"[metadata] 차원 {len(meta.get('dimensions', []))}개, 지표 {len(meta.get('metrics', []))}개")
    body = {"dateRanges": [{"startDate": day, "endDate": day}],
            "dimensions": [{"name": "country"}, {"name": "languageCode"}],
            "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}],
            "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}], "limit": 8}
    rep = call(tok, "POST", f"{DATA}/properties/{args.property}:runReport", body)
    print(f"[runReport] {day} 행 {rep.get('rowCount')}건, 시간대 {rep.get('metadata', {}).get('timeZone')}")
    for r in rep.get("rows", []):
        d = [x["value"] for x in r["dimensionValues"]]
        m = [x["value"] for x in r["metricValues"]]
        print(f"  {d[0]} | {d[1]} | PV={m[0]} 사용자={m[1]}")


if __name__ == "__main__":
    main()
