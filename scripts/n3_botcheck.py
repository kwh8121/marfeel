#!/usr/bin/env python3
"""N3 봇 의심 행 컷오프 확인(읽기 전용). n3_bot_tiers.csv(n3_users.py가 고유 사용자당 참여 시간으로 만든 티어)의 3단계로 행을 나눠 본다.
  strong: <7초, border: 7~15초, normal: 15초 이상 (PV 1만 이상 행만 분류, 나머지는 normal)
확인 1) 일별 PV 패턴: strong·border 일별 PV가 normal과 같이 움직이는가(상관·요일 패턴·급변일)
확인 3) 기사 순위 민감도: 제외 기준에 따라 기사별 PV 순위가 바뀌는가(스피어만 상관, 상위 100 겹침)
출력: data/analysis/n3_botcheck_daily.csv, 표준 출력 요약
"""
import csv, glob, gzip, json, re, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from n3_common import ANALYSIS as A, akey, load_tiers, window_closed

ROOT = Path(__file__).resolve().parent.parent
START = date(2025, 7, 1)
ART = re.compile(r"^/(?:amp/)?[^?]*?/(20\d{6})/[^/]+$")

tier = load_tiers()  # n3_users.py가 만든 티어(고유 사용자 기준)(없는 행은 normal)
print("분류 행:", {t: sum(1 for v in tier.values() if v == t) for t in ("strong", "border", "normal")})


def ranks(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def corr(x, y):
    n = len(x); mx, my = sum(x) / n, sum(y) / n
    sx = sum((a - mx) ** 2 for a in x) ** .5; sy = sum((b - my) ** 2 for b in y) ** .5
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy) if sx and sy else float("nan")


daily = {}
PUB = {}
LAST = None
art = defaultdict(lambda: [0, 0, 0])  # path -> [전체, strong, border]
for f in sorted(glob.glob(str(ROOT / "data/ga4/raw/segment/*.json.gz"))):
    d = json.load(gzip.open(f, "rt", encoding="utf-8")); day = date.fromisoformat(d["date"]); LAST = day
    if day < START: continue
    t = {"strong": 0, "border": 0, "normal": 0}
    for path, ct, lg, pv, au, e in d["rows"]:
        k = tier.get((ct, lg), "normal"); t[k] += pv
        m = ART.match(path)
        if m:
            try: pub = date(int(m[1][:4]), int(m[1][4:6]), int(m[1][6:]))
            except ValueError: continue
            if START <= pub <= day <= pub + timedelta(days=2):
                a = art[akey(path)]; a[0] += pv; PUB[akey(path)] = pub
                if k == "strong": a[1] += pv
                elif k == "border": a[2] += pv
    daily[day] = t
with open(A / "n3_botcheck_daily.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["date", "strong", "border", "normal"])
    for d, t in sorted(daily.items()): w.writerow([d, t["strong"], t["border"], t["normal"]])
if not daily:
    sys.exit("입력 없음: data/ga4/raw/segment")
days = sorted(daily)
for k in ("strong", "border"):
    s = [daily[d][k] for d in days]; n = [daily[d]["normal"] for d in days]
    share = [a / (a + b) for a, b in zip(s, n)]
    wk = lambda xs, w: sum(x for x, d in zip(xs, days) if (d.weekday() >= 5) == w) / max(1, sum(1 for d in days if (d.weekday() >= 5) == w))
    jumps = sorted(((abs(s[i] - s[i - 1]) / max(s[i - 1], 1), days[i]) for i in range(1, len(s))), reverse=True)[:3]
    print(f"[{k}] 일별 PV 상관(normal과) {corr(s, n):.2f} | 비중 {min(share):.1%}~{max(share):.1%} | 주말/평일 PV 비 {wk(s, True) / wk(s, False):.2f} (normal {wk(n, True) / wk(n, False):.2f}) | 전일 대비 급변 상위 {[(str(d), round(j, 2)) for j, d in jumps]}")
paths = [p for p, a in art.items() if a[0] >= 20 and window_closed(PUB[p], LAST)]
tot = [art[p][0] for p in paths]
ex1 = [art[p][0] - art[p][1] for p in paths]
ex2 = [art[p][0] - art[p][1] - art[p][2] for p in paths]
top = lambda xs: set(sorted(range(len(xs)), key=lambda i: -xs[i])[:100])
rt = ranks(tot)
print(f"기사 {len(paths)}건(72시간 PV 20 이상)")
for name, ex in (("strong 제외", ex1), ("strong+border 제외", ex2)):
    print(f"[{name}] 스피어만 {corr(rt, ranks(ex)):.3f} | 상위100 겹침 {len(top(tot) & top(ex))}")
