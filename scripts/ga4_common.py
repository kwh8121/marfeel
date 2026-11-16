"""GA4 수집·점검이 함께 쓰는 기준(수집 확정 판정). 표준 라이브러리만 사용한다."""
import gzip
import re
import zlib
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
REFRESH_DAYS = 4  # 오늘 기준 이 일수 이내의 날은 GA4 후처리로 값이 바뀔 수 있다
_FETCHED = re.compile(rb'"fetchedAt": "([^"]+)"')


def fetched_date(path: Path) -> date:
    """파일을 받은 날(KST). 파일 안의 fetchedAt을 쓰고(복사·복원에 안전), 없으면 수정 시각으로 대체한다."""
    try:
        with gzip.open(path, "rb") as f:
            head = f.read(2048)
        m = _FETCHED.search(head)
        if m:
            return datetime.fromisoformat(m[1].decode()).astimezone(KST).date()
    except zlib.error:
        return date.min  # 손상된 파일은 확정 아님으로 보고 다시 받게 한다
    except (OSError, EOFError, ValueError):
        pass
    return datetime.fromtimestamp(path.stat().st_mtime, KST).date()


def settled(path: Path, day: date) -> bool:
    """후처리가 끝난 뒤(그날 + REFRESH_DAYS일 초과)에 받은 파일인가."""
    return (fetched_date(path) - day).days > REFRESH_DAYS
