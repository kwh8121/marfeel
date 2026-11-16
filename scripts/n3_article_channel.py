#!/usr/bin/env python3
"""N3 1단계: 기사 단위로 A 비율(국내 중 비한국어)이 유입 채널에 따라 갈라지는지 본다(읽기 전용).
기사 = 2025-07-01 ~ 2026-07-04 발행(72시간 창이 07-06 안에 차는 기사만, 07-07 이후 구간 제외), 발행일부터 3일 PV. 채널은 Direct·Organic Search 비교.
출력 data/analysis/n3_article_channel.csv (path, pub, A·C × 두 채널 PV), 표준 출력 요약
"""
import csv, glob, gzip, json, re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from n3_common import akey

ROOT = Path(__file__).resolve().parent.parent
START, END = date(2025, 7, 1), date(2026, 7, 6)
ART = re.compile(r"^/(?:amp/)?[^?]*?/(20\d{6})/[^/]+$")

art = defaultdict(lambda: defaultdict(int))
for f in sorted(glob.glob(str(ROOT / "data/ga4/raw/channel/*.json.gz"))):
    d = json.load(gzip.open(f, "rt", encoding="utf-8")); day = date.fromisoformat(d["date"])
    if day > END: continue  # 07-07 이후는 같은 척도가 아니므로 읽지 않는다
    for path, ch, ct, lg, pv, au, e in d["rows"]:
        if ct != "South Korea" or ch not in ("Direct", "Organic Search"): continue
        m = ART.match(path)
        if not m: continue
        try: pub = date(int(m[1][:4]), int(m[1][4:6]), int(m[1][6:]))
        except ValueError: continue
        if START <= pub <= day <= pub + timedelta(days=2) and pub + timedelta(days=2) <= END:  # 72시간 창이 END 안에 다 들어오는 기사만
            art[(akey(path), m[1])][(ch[0], "C" if lg.lower().split("-")[0] == "ko" else "A")] += pv
with open(ROOT / "data/analysis/n3_article_channel.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["path", "pub", "D_A", "D_C", "S_A", "S_C"])
    for (p, pub), v in art.items(): w.writerow([p, pub, v[("D", "A")], v[("D", "C")], v[("O", "A")], v[("O", "C")]])
rows = [(v[("D", "A")], v[("D", "C")], v[("O", "A")], v[("O", "C")]) for v in art.values()]
ok = [r for r in rows if r[0] + r[1] >= 50 and r[2] + r[3] >= 50]
da = [r[0] / (r[0] + r[1]) for r in ok]; sa = [r[2] / (r[2] + r[3]) for r in ok]
diff = sorted(abs(a - b) for a, b in zip(da, sa))
n = len(ok); mx, my = sum(da) / n, sum(sa) / n
cor = sum((a - mx) * (b - my) for a, b in zip(da, sa)) / ((sum((a - mx) ** 2 for a in da) * sum((b - my) ** 2 for b in sa)) ** .5)
print(f"기사 {len(rows)}건, 두 채널 모두 국내 PV 50 이상 {n}건")
print(f"기사별 A 비율 차이(|Direct-검색|) 중앙값 {100 * diff[n // 2]:.1f}%p, 75% {100 * diff[3 * n // 4]:.1f}%p, 90% {100 * diff[9 * n // 10]:.1f}%p")
print(f"기사별 A 비율 상관(Direct, 검색) {cor:.2f}")
print(f"A 비율 88% 이상인 기사: Direct {sum(a >= .88 for a in da)}건, 검색 {sum(b >= .88 for b in sa)}건, 둘 다 {sum(a >= .88 and b >= .88 for a, b in zip(da, sa))}건")
