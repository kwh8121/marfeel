#!/usr/bin/env python3
"""N3 M1: 고유 사용자 기준 사용자당 참여 시간으로 티어를 다시 계산해 M1 이전 정의와 비교한다(읽기 전용).
입력: data/ga4/raw/users(국가 × 언어 × 일, 하루 고유 활성 사용자), n3_bot_tiers_pathsum.csv(n3_segments.py가 만든 M1 이전 티어)
이전 지표: Σ참여 ÷ Σ경로별 활성 사용자(한 사람이 여러 경로를 보면 분모에 여러 번 들어가 작게 나옴)
현행 지표: Σ참여 ÷ Σ일별 고유 활성 사용자
판정 규칙(데이터를 보기 전에 고정, 2026-11-16): 7초·15초 그대로. 티어가 바뀌는 행의 PV가 해외 PV의 5% 미만이고
봇 규칙 v2 결론이 같으면 현행 기준 유지(정의만 반영), 아니면 기준 재설정을 논의한다. 임계값을 데이터에 맞춰 옮기지 않는다.
결정(2026-11-16): 판정은 '기준 재설정 논의'(5.28%)였으나 사용자가 새 정의 채택·7초·15초 유지로 결정. 봇 규칙 v2도 n3_botrule.py가 같은 지표를 쓴다.
출력: data/analysis/n3_bot_tiers.csv(현행 티어), n3_users_tiers.csv(이전 정의 대비 전이), 표준 출력 요약
"""
import csv, glob, gzip, json, sys
from collections import defaultdict
from datetime import date

from n3_common import ANALYSIS as A, ROOT, TIER_MIN_PV, load_tiers, tier_of

START = date(2025, 7, 1)
CHANGE_LIMIT = 0.05      # 사전 고정 판정 기준


def load(f):
    return json.load(gzip.open(f, "rt", encoding="utf-8"))


files = [f for f in sorted(glob.glob(str(ROOT / "data/ga4/raw/users/*.json.gz"))) if date.fromisoformat(f[-18:-8]) >= START]
if not files:
    sys.exit("입력 없음: data/ga4/raw/users")
cl = defaultdict(lambda: [0, 0, 0])      # (국가, 언어) → [PV, 고유 사용자 합, 참여 초]
for f in files:
    d = load(f); day = date.fromisoformat(d["date"])
    if day < START: continue
    for ct, lg, pv, au, e in d["rows"]:
        c = cl[(ct, lg)]; c[0] += pv; c[1] += au; c[2] += e
first, last = files[0][-18:-8], files[-1][-18:-8]
overseas = {k: v for k, v in cl.items() if k[0] != "South Korea" and k[0] not in ("(not set)", "")}
tot = sum(v[0] for v in overseas.values())
old = load_tiers("n3_bot_tiers_pathsum.csv")  # M1 이전 정의(비교용)
rows, trans = [], defaultdict(lambda: [0, 0])
for k, v in sorted(overseas.items(), key=lambda x: -x[1][0]):
    if v[0] < TIER_MIN_PV or not v[1]: continue
    e = v[2] / v[1]; new = tier_of(e); o = old.get(k, "normal")
    rows.append([k[0], k[1], o, new, v[0], round(e, 2)]); trans[(o, new)][0] += 1; trans[(o, new)][1] += v[0]
with open(A / "n3_bot_tiers.csv", "w", newline="", encoding="utf-8") as fh:  # 현행 티어(고유 사용자 기준)
    w = csv.writer(fh); w.writerow(["country", "language", "tier", "pv", "eng_per_user"])
    for r in rows: w.writerow([r[0], r[1], r[3], r[4], r[5]])
with open(A / "n3_users_tiers.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["country", "language", "old_tier", "new_tier", "pv", "eng_per_unique_user"]); w.writerows(rows)
moved = sum(p for (o, n), (_, p) in trans.items() if o != n)
print(f"users 파일 {len(files)}개({first}~{last}), 해외 PV {tot:,}, 티어 대상 행 {len(rows)}")
print("이전 → 현행 티어(행, PV):")
for (o, n), (r, p) in sorted(trans.items()):
    print(f"  {o:7s} → {n:7s} {r:4d}행 PV {p:>12,} ({p / tot:.1%})" + ("" if o == n else "  ← 변경"))
print(f"티어가 바뀌는 행 PV {moved:,} = 해외 PV의 {moved / tot:.2%} (기준 {CHANGE_LIMIT:.0%})")
for t in ("strong", "border", "normal"):
    s = [r for r in rows if r[3] == t]; print(f"  새 {t}: {len(s)}행, PV {sum(r[4] for r in s):,} ({sum(r[4] for r in s) / tot:.1%})")
