"""N3 분석 스크립트 공용 기준. 기준을 바꿀 때 여기 한 곳만 고친다."""
import csv
import sys
from datetime import timedelta
from pathlib import Path

from ga4_common import REFRESH_DAYS

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS = ROOT / "data" / "analysis"
TIER_MIN_PV = 10000       # 티어 판정 최소 PV(해외 국가 × 언어)
STRONG_SEC, BORDER_SEC = 7, 15


def akey(path):
    """기사 키: AMP 접두(/amp)를 떼고 앞 96자만 쓴다(AMP 경로는 100자에서 잘려 같은 기사가 둘로 갈라졌다)."""
    return (path[4:] if path.startswith("/amp/") else path)[:96]


def tier_of(eng_per_user):
    """반올림 전 값으로 판정한다(반올림하면 6.96초가 7.0초로 border가 된다)."""
    return "strong" if eng_per_user < STRONG_SEC else ("border" if eng_per_user < BORDER_SEC else "normal")


def load_tiers():
    """n3_segments.py가 만든 n3_bot_tiers.csv에서 (국가, 언어) → 티어. 없는 행은 normal로 본다."""
    path = ANALYSIS / "n3_bot_tiers.csv"
    if not path.exists():
        sys.exit("n3_bot_tiers.csv 없음: n3_segments.py를 먼저 실행한다")
    with open(path, encoding="utf-8") as fh:
        return {(r["country"], r["language"]): r["tier"] for r in csv.DictReader(fh)}


def window_closed(pub, last):
    """발행 후 72시간 창이 확정된 값으로 다 찼는가. 마지막 REFRESH_DAYS일은 GA4가 아직 고칠 수 있어 뺀다."""
    return pub + timedelta(days=2) <= last - timedelta(days=REFRESH_DAYS)
