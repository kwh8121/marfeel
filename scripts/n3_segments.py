#!/usr/bin/env python3
"""N3 1단계(일부): GA4 세그먼트 원본에서 국가 × 언어 집계를 만든다(읽기 전용, 표준 라이브러리).

입력: data/ga4/raw/segment/*.json.gz (행: pagePath, country, languageCode, PV, 활성 사용자, 참여 시간)
출력(data/analysis/):
  n3_month_seg.csv   월 × 세그먼트(A/B/C/기타) PV·사용자·참여 시간
  n3_country_lang.csv 분석 구간 국가 × 언어 PV·사용자·사용자당 참여 시간(봇 의심 행 점검용)
  n3_article_seg.csv 기사 × 세그먼트 PV(발행일부터 3일, 분석 구간에 발행된 기사)
세그먼트: A=한국 × 비한국어, C=한국 × 한국어(ko 계열), B=한국 외 국가, X=국가 불명. 봇 제외는 하지 않는다.
n3_bot_tiers_pathsum.csv  해외 국가 × 언어 티어, 경로별 활성 사용자 합 기준(M1 이전 정의, 비교용). 현행 티어는 n3_users.py가 만든다
기사 키는 AMP 접두를 떼고 앞 96자, 72시간 창이 확정되지 않은 기사(마지막 수집일 - REFRESH_DAYS일 이후)는 제외한다.
유입 유형은 이 데이터에 없다(별도 수집 필요).
"""
import csv, glob, gzip, json, re, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from n3_common import ANALYSIS as OUT, TIER_MIN_PV, akey, tier_of, window_closed

ROOT = Path(__file__).resolve().parent.parent
START = date(2025, 7, 1)                  # 분석 구간 시작(r5)
ART = re.compile(r"^/(?:amp/)?[^?]*?/(20\d{6})/[^/]+$")


def seg(country, lang):
    if country in ("(not set)", ""):
        return "X"
    if country != "South Korea":
        return "B"
    return "C" if lang.lower().split("-")[0] == "ko" else "A"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    month = defaultdict(lambda: [0, 0, 0])
    cl = defaultdict(lambda: [0, 0, 0])
    art = defaultdict(lambda: defaultdict(int))
    files = sorted(glob.glob(str(ROOT / "data/ga4/raw/segment/*.json.gz")))
    if not files:
        sys.exit("입력 없음: data/ga4/raw/segment")
    last = date.fromisoformat(json.load(gzip.open(files[-1], "rt", encoding="utf-8"))["date"])
    for f in files:
        d = json.load(gzip.open(f, "rt", encoding="utf-8"))
        day = date.fromisoformat(d["date"])
        if day < START:
            continue
        m = day.strftime("%Y-%m")
        for path, ctry, lang, pv, au, eng in d["rows"]:
            s = seg(ctry, lang)
            a = month[(m, s)]; a[0] += pv; a[1] += au; a[2] += eng
            c = cl[(ctry, lang)]; c[0] += pv; c[1] += au; c[2] += eng
            mt = ART.match(path)
            if mt:
                try:
                    pub = date(int(mt[1][:4]), int(mt[1][4:6]), int(mt[1][6:]))
                except ValueError:
                    continue
                if START <= pub <= day <= pub + timedelta(days=2) and window_closed(pub, last):
                    art[(akey(path), mt[1])][s] += pv
    with open(OUT / "n3_month_seg.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["month", "seg", "pv", "active_users_sum", "engagement_sec"])
        for (m, s), v in sorted(month.items()): w.writerow([m, s, *v])
    with open(OUT / "n3_country_lang.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["country", "language", "pv", "active_users_sum", "engagement_sec", "eng_per_user"])
        for (c, l), v in sorted(cl.items(), key=lambda x: -x[1][0]):
            w.writerow([c, l, *v, round(v[2] / v[1], 1) if v[1] else ""])
    with open(OUT / "n3_article_seg.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["path", "pub", "pv_A", "pv_B", "pv_C", "pv_X"])
        for (p, pub), v in art.items(): w.writerow([p, pub, v["A"], v["B"], v["C"], v["X"]])
    with open(OUT / "n3_bot_tiers_pathsum.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["country", "language", "tier", "pv", "eng_per_user"])
        for (c, l), v in sorted(cl.items(), key=lambda x: -x[1][0]):
            if c != "South Korea" and c not in ("(not set)", "") and v[0] >= TIER_MIN_PV and v[1]:  # 국가 불명은 티어에서 뺀다(n3_users와 같은 대상)
                e = v[2] / v[1]
                w.writerow([c, l, tier_of(e), v[0], round(e, 2)])
    print(f"files {len(files)}, 월×세그 {len(month)}, 국가×언어 {len(cl)}, 기사 {len(art)}")


if __name__ == "__main__":
    main()
