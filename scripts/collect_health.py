#!/usr/bin/env python3
"""수집 상태 점검(읽기 전용). Search Console 빠진 날과 goatway 원장 최신성을 보고한다.
개인 PC가 꺼져 있던 동안 빠진 구간이 있는지 본다. 이상이 있으면 종료 코드 1.
  python3 scripts/collect_health.py
"""
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SC = ROOT / "data" / "searchconsole" / "raw"
DB = ROOT / "data" / "ledger" / "ledger.sqlite"
GA4 = ROOT / "data" / "ga4" / "raw"  # 하위: pagepath, segment
GA4_START = "2025-02-21"
GA4_CHANNEL_START = "2025-07-01"  # channel 보고서는 분석 구간(2025-07-01)부터만 받는다
GA4_LAG = 1         # ga4_collect.py의 종료일 = 오늘 - 1
TYPES = ["web", "news", "discover", "googleNews"]
SC_LAG = 3          # searchconsole_collect.py의 종료일 = 오늘 - 3
LEDGER_STALE_H = 36  # 마지막 성공 증분 수집이 이보다 오래되면 이상


def main():
    bad = 0
    today = date.today()
    for t in TYPES:
        have = {f.name[:10] for f in (SC / t).glob("*.json.gz")}
        if not have:
            print(f"SC {t}: 파일 없음"); bad += 1; continue
        d0, d1 = date.fromisoformat(min(have)), today - timedelta(days=SC_LAG)
        miss = [(d0 + timedelta(i)).isoformat() for i in range((d1 - d0).days + 1)
                if (d0 + timedelta(i)).isoformat() not in have]
        last = max(have)
        print(f"SC {t:10s}: 최신 {last}, 기대 최신 {d1}, 빠진 날 {len(miss)}"
              + (f" {miss[:5]}" if miss else ""))
        bad += bool(miss)
    for rep in ("pagepath", "segment", "channel"):
        have = {f.name[:10] for f in (GA4 / rep).glob("*.json.gz")}
        if have:
            d0, d1 = date.fromisoformat(GA4_CHANNEL_START if rep == "channel" else GA4_START), today - timedelta(days=GA4_LAG)
            miss = [(d0 + timedelta(i)).isoformat() for i in range((d1 - d0).days + 1)
                    if (d0 + timedelta(i)).isoformat() not in have]
            print(f"GA4 {rep:8s} : 최신 {max(have)}, 기대 최신 {d1}, 빠진 날 {len(miss)}" + (f" {miss[:5]}" if miss else ""))
            bad += bool(miss)
        else:
            print(f"GA4 {rep:8s} : 파일 없음"); bad += 1
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=30)
    ended, = con.execute("SELECT MAX(ended_at) FROM runs WHERE mode IN ('incremental','full') AND failed_pages=0").fetchone()
    pub, = con.execute("SELECT MAX(pub_dt) FROM articles").fetchone()
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(ended)).total_seconds() / 3600 if ended else None
    print(f"원장: 마지막 성공 수집 {ended} ({age:.1f}시간 전), 최신 기사 {pub}")
    if age is None or age > LEDGER_STALE_H:
        print("원장 수집이 오래됐다."); bad += 1
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
