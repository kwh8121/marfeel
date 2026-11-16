#!/usr/bin/env python3
"""N3 봇 의심 행 × 일 규칙(읽기 전용, 표준 라이브러리). 입력 data/ga4/raw/channel, n3_bot_tiers.csv.
규칙 v2(해외 국가 × 언어 × 일, 제안값, 2026-11-13 수정 승인):
  봇 의심 = 그날 PV >= 50 & 사용자당 참여 시간(Σ참여/Σ사용자) < 7초 & Direct+Unassigned 비중 >= 90%
  폭증 열(참고용, 제외 기준 아님) = 그날 PV >= 직전 28일 일 PV 중앙값(최소 50)의 5배
v1(폭증 필수)은 상시 봇 행(2026-01-05 중국 zh-cn, 기준선 대비 2.8배)을 못 잡아 폐기했다.
출력: data/analysis/n3_bot_days.csv(봇 의심 행×일), 표준 출력 검증 요약
검증: 의심 사례 포착, 티어와의 차이, 임계값 민감도, 제외 전후 기사 순위(72시간 PV)
"""
import csv, glob, gzip, json, re, statistics, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from n3_common import ANALYSIS as A, akey, load_tiers, window_closed

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted(glob.glob(str(ROOT / "data/ga4/raw/channel/*.json.gz")))
ART = re.compile(r"^/(?:amp/)?[^?]*?/(20\d{6})/[^/]+$")
if not FILES:
    sys.exit("입력 없음: data/ga4/raw/channel")
tier = load_tiers()
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


def flag(eng_th=7.0, share=0.90, min_pv=50):
    out = {}  # (row, day) -> pv
    for row, days in daily.items():
        for day, (pv, au, eng, core) in days.items():
            if pv >= min_pv and au and eng / au < eng_th and core / pv >= share:
                out[(row, day)] = pv
    return out


def spike(row, day):
    days = daily[row]
    if day - timedelta(28) < date(2025, 7, 1): return ""
    base = max(statistics.median([days.get(day - timedelta(k), [0])[0] for k in range(1, 29)]), 50)
    return int(days[day][0] >= 5 * base)


base = flag()
with open(A / "n3_bot_days.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["country", "language", "date", "pv", "tier", "spike5x"])
    for ((ct, lg), day), pv in sorted(base.items(), key=lambda x: (x[0][0], x[0][1])):
        w.writerow([ct, lg, day, pv, tier.get((ct, lg), "-"), spike((ct, lg), day)])
tot = sum(v[0] for r in daily.values() for v in r.values())
print(f"해외 PV 합 {tot:,} | v2 규칙 의심 행×일 {len(base)}건, PV {sum(base.values()):,} ({sum(base.values()) / tot:.1%})")
bt = defaultdict(lambda: [0, 0])
for (row, day), pv in base.items(): bt[tier.get(row, "-")][0] += 1; bt[tier.get(row, "-")][1] += pv
print("티어별 의심 건수·PV:", {k: tuple(v) for k, v in bt.items()})
for d in ("2026-01-05", "2026-01-04"):
    hit = {k[0]: v for k, v in base.items() if str(k[1]) == d}
    print(f"사례 {d}: 의심 {len(hit)}행, PV {sum(hit.values()):,}", sorted(hit.items(), key=lambda x: -x[1])[:2])
# 티어 대비 이점
st = [(r, days) for r, days in daily.items() if tier.get(r) == "strong"]
sd = sum(len(d) for _, d in st); spv = sum(v[0] for _, d in st for v in d.values())
flagged_in_strong = sum(1 for (r, dd) in base if tier.get(r) == "strong")
fpv = sum(pv for (r, dd), pv in base.items() if tier.get(r) == "strong")
print(f"strong 티어 행×일 {sd}개 중 의심 {flagged_in_strong}건({flagged_in_strong / max(sd, 1):.0%}), PV {fpv:,} / strong 전체 PV {spv:,} ({fpv / max(spv, 1):.0%}) → 나머지는 strong인데 그날은 정상으로 판정")
nd = sum(len(d) for r, d in daily.items() if tier.get(r) == "normal")
print(f"normal 티어 행×일 {nd}개 중 의심 {bt['normal'][0]}건({bt['normal'][0] / max(nd, 1):.2%}), PV {bt['normal'][1]:,}")
sp = sum(1 for (r, dd) in base if spike(r, dd) == 1)
print(f"의심 중 5배 폭증 동반 {sp}건({sp / max(len(base), 1):.0%})")
print("민감도(참여 초, 직접+미지정 비중) → 건수, PV:")
for e, sh in ((5, .9), (7, .9), (10, .9), (7, .8), (7, .95)):
    r = flag(e, sh); print(f"  {e}초·{sh:.0%}: {len(r)}건, {sum(r.values()):,} ({sum(r.values()) / tot:.1%})")
loose = flag(10, .8)


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
PUB = {}
LAST = date.fromisoformat(load(FILES[-1])["date"])
for f in FILES:
    d = load(f); day = date.fromisoformat(d["date"])
    for path, ch, ct, lg, pv, au, e in d["rows"]:
        m = ART.match(path)
        if not m: continue
        try: pub = date(int(m[1][:4]), int(m[1][4:6]), int(m[1][6:]))
        except ValueError: continue
        if date(2025, 7, 1) <= pub <= day <= pub + timedelta(days=2):
            k = akey(path); PUB[k] = pub
            a = art[k]; a[0] += pv
            if ((ct, lg), day) in base: a[1] += pv
            if ((ct, lg), day) in loose: a[2] += pv
paths = [p for p, a in art.items() if a[0] >= 20 and window_closed(PUB[p], LAST)]
tt = [art[p][0] for p in paths]; rt = ranks(tt)
top = lambda xs: set(sorted(range(len(xs)), key=lambda i: -xs[i])[:100])
print(f"기사 {len(paths)}건")
for name, k in (("v2 기본(7초·90%) 제외", 1), ("느슨(10초·80%) 제외", 2)):
    ex = [art[p][0] - art[p][k] for p in paths]
    print(f"[{name}] 스피어만 {corr(rt, ranks(ex)):.4f} | 상위100 겹침 {len(top(tt) & top(ex))} | 제외 PV {sum(art[p][k] for p in paths):,}")
