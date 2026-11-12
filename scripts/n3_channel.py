#!/usr/bin/env python3
"""N3 1단계: 채널 × 세그먼트 집계와 봇 의심 행의 채널 분포(읽기 전용).
입력 data/ga4/raw/channel (행: pagePath, channel, country, languageCode, PV, 사용자, 참여 시간), n3_country_lang.csv(분류)
출력 data/analysis/n3_channel_seg.csv(월 × 채널 × 티어/세그먼트 PV), n3_channel_tier_day.csv(일 × 티어 × 채널 PV)
티어: 해외 행 중 strong(<7초)·border(7~15초)·normal, 국내는 A·C
"""
import csv, glob, gzip, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "data" / "analysis"
tier = {}
for r in csv.DictReader(open(A / "n3_country_lang.csv", encoding="utf-8")):
    if r["eng_per_user"] and int(r["pv"]) >= 10000 and r["country"] != "South Korea":
        e = float(r["eng_per_user"]); tier[(r["country"], r["language"])] = "B_strong" if e < 7 else ("B_border" if e < 15 else "B_normal")
month = defaultdict(int); day = defaultdict(int)
for f in sorted(glob.glob(str(ROOT / "data/ga4/raw/channel/*.json.gz"))):
    d = json.load(gzip.open(f, "rt", encoding="utf-8")); ds = d["date"]
    for path, ch, ct, lg, pv, au, e in d["rows"]:
        if ct == "South Korea": t = "C" if lg.lower().split("-")[0] == "ko" else "A"
        elif ct in ("(not set)", ""): t = "X"
        else: t = tier.get((ct, lg), "B_normal")
        month[(ds[:7], ch, t)] += pv; day[(ds, t, ch)] += pv
with open(A / "n3_channel_seg.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["month", "channel", "tier", "pv"])
    for k, v in sorted(month.items()): w.writerow([*k, v])
with open(A / "n3_channel_tier_day.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["date", "tier", "channel", "pv"])
    for k, v in sorted(day.items()): w.writerow([*k, v])
print("done", len(month), len(day))
