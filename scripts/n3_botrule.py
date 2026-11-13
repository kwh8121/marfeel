#!/usr/bin/env python3
"""N3 봇 의심 행 × 일 규칙(읽기 전용, 표준 라이브러리). 입력 data/ga4/raw/channel, n3_bot_tiers.csv.
규칙(해외 국가 × 언어 × 일, 모두 제안값):
  1) 그날 사용자당 참여 시간(Σ참여/Σ사용자) < 7초 → 후보
  2) 그날 PV >= 직전 28일 일 PV 중앙값(최소 50)의 5배 → 폭증
  3) 후보 & 폭증 & Direct+Unassigned 비중 >= 90% → 봇 의심
출력: data/analysis/n3_bot_days.csv(봇 의심 행×일), 표준 출력 검증 요약
검증: 의심 사례 포착, normal 티어 오탐, 임계값 민감도, 제외 전후 기사 순위(72시간 PV)
"""
import csv, glob, gzip, json, re, statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "data" / "analysis"
FILES = sorted(glob.glob(str(ROOT / "data/ga4/raw/channel/*.json.gz")))
ART = re.compile(r"^/(?:amp/)?[^?]*?/(20\d{6})/[^/]+$")
tier = {(r["country"], r["language"]): r["tier"] for r in csv.DictReader(open(A / "n3_bot_tiers.csv", encoding="utf-8"))}
CORE = {"Direct", "Unassigned"}
daily = defaultdict(dict)  # (country, lang) -> {date: [pv, au, eng, core_pv]}


def load(f):
    return json.load(gzip.open(f, "rt", encoding="utf-8"))


for f in FILES:
    d = load(f); day = date.fromisoformat(d["date"])
    for path, ch, ct, lg, pv, au, e in d["rows"]:
        if ct == "South Korea" or ct in ("(not set)", ""): continue
        a = daily[(ct, lg)].setdefault(day, [0, 0, 0, 0])
        a[0] += pv; a[1] += au; a[2] += e
        if ch in CORE: a[3] += pv


def flag(mult, share, eng_th=7.0, min_base=50):
    out = {}  # (row, day) -> pv
    for row, days in daily.items():
        for day, (pv, au, eng, core) in days.items():
            if au == 0 or eng / au >= eng_th: continue
            hist = [days.get(day - timedelta(k), [0])[0] for k in range(1, 29)]
            if day - timedelta(28) < min(days) and day - timedelta(28) < date(2025, 7, 1): continue  # 기준선 부족
            base = max(statistics.median(hist), min_base)
            if pv >= mult * base and core / pv >= share: out[(row, day)] = pv
    return out


base = flag(5, 0.90)
with open(A / "n3_bot_days.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["country", "language", "date", "pv", "tier"])
    for ((ct, lg), day), pv in sorted(base.items(), key=lambda x: (x[0][0], x[0][1])): w.writerow([ct, lg, day, pv, tier.get((ct, lg), "-")])
tot = sum(v[0] for r in daily.values() for v in r.values())
print(f"해외 PV 합 {tot:,} | 기본 규칙 의심 행×일 {len(base)}건, PV {sum(base.values()):,} ({sum(base.values()) / tot:.1%})")
bt = defaultdict(lambda: [0, 0])
for (row, day), pv in base.items(): bt[tier.get(row, "-")][0] += 1; bt[tier.get(row, "-")][1] += pv
print("티어별 의심 건수·PV:", {k: tuple(v) for k, v in bt.items()})
for d in ("2025-07-14", "2026-01-05", "2025-07-08"):
    hit = {k[0]: v for k, v in base.items() if str(k[1]) == d}
    print(f"사례 {d}: 의심 {len(hit)}행, PV {sum(hit.values()):,}", sorted(hit.items(), key=lambda x: -x[1])[:2])
normal_days = sum(len(days) for row, days in daily.items() if tier.get(row) == "normal")
print(f"normal 티어 행×일 {normal_days}개 중 의심 {bt['normal'][0]}건({bt['normal'][0] / max(normal_days, 1):.2%}), PV {bt['normal'][1]:,}")
print("민감도(배수, 비중) → 건수, PV:")
for m, s in ((3, .9), (5, .9), (10, .9), (5, .8), (5, .95)):
    r = flag(m, s); print(f"  {m}배·{s:.0%}: {len(r)}건, {sum(r.values()):,} ({sum(r.values()) / tot:.1%})")
loose = flag(3, .8)


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
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / ((sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** .5)


art = defaultdict(lambda: [0, 0, 0])
for f in FILES:
    d = load(f); day = date.fromisoformat(d["date"])
    for path, ch, ct, lg, pv, au, e in d["rows"]:
        m = ART.match(path)
        if not m: continue
        try: pub = date(int(m[1][:4]), int(m[1][4:6]), int(m[1][6:]))
        except ValueError: continue
        if date(2025, 7, 1) <= pub <= day <= pub + timedelta(days=2):
            a = art[path]; a[0] += pv
            if ((ct, lg), day) in base: a[1] += pv
            if ((ct, lg), day) in loose: a[2] += pv
paths = [p for p, a in art.items() if a[0] >= 20]
tt = [art[p][0] for p in paths]; rt = ranks(tt)
top = lambda xs: set(sorted(range(len(xs)), key=lambda i: -xs[i])[:100])
print(f"기사 {len(paths)}건")
for name, k in (("기본(5배·90%) 제외", 1), ("느슨(3배·80%) 제외", 2)):
    ex = [art[p][0] - art[p][k] for p in paths]
    print(f"[{name}] 스피어만 {corr(rt, ranks(ex)):.4f} | 상위100 겹침 {len(top(tt) & top(ex))} | 제외 PV {sum(art[p][k] for p in paths):,}")
