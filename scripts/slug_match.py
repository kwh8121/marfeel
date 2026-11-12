#!/usr/bin/env python3
"""슬러그 변경 보정 매칭(원장 읽기, url_aliases 표에만 쓴다). 표준 라이브러리만 사용한다.

GA4·Search Console의 기사 경로가 원장 canonical_url과 다를 때(발행 후 제목 수정으로 슬러그가 바뀜,
GA4 경로 100자 절단, 섹션 변경) 같은 기사를 찾아 url_aliases에 기록한다.

규칙(위에서부터 적용, 같은 URL 날짜 /YYYYMMDD/ 안에서만 찾는다)
  exact   정규화한 경로가 원장 canonical_url·slug_url과 같다(/amp 접두와 쿼리·끝 슬래시 제거)
  prefix  경로가 90자 이상이거나 …로 끝나고 원장 URL이 그 앞부분과 같다(GA4 절단)
  slug    섹션을 무시하고 슬러그가 같다
  fuzzy   슬러그 단어 집합의 자카드 ≥ 0.6, 1등이 2등보다 0.1 이상 높다
  canonical  --live: 옛 슬러그 URL을 열어 <link rel=canonical>이 가리키는 현재 URL로 원장과 맞춘다(제목이 크게 바뀐 기사)
  gone    --live: canonical이 섹션 페이지라 기사가 내려갔거나 열리지 않는다
  missing --live: 열리는 기사인데 canonical이 원장에 없다. 원장에서 빠진 기사다
  pre_ledger  URL 날짜가 원장 시작(최초 pub_dt) 이전이라 원장 범위 밖이다
  none    위에 해당 없음. 원장에 없는 기사이거나 매칭하기 어려운 변경이다

사용
  python3 scripts/slug_match.py ga4 --days 2026-11-04 2026-10-20     GA4 경로를 받아 매칭 기록·요약
  python3 scripts/slug_match.py sc --live 500                         Search Console 원본 전체의 기사 경로를 매칭
  python3 scripts/slug_match.py urls --file paths.txt                 경로 목록(한 줄에 하나)을 매칭
  python3 scripts/slug_match.py sample --n 30                         기록된 fuzzy 매칭 표본 출력(사람이 검수)
"""
import argparse
import gzip
import json
import re
import sqlite3
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "ledger" / "ledger.sqlite"
DATE_RE = re.compile(r"/(20\d{6})/")
TRUNC_MIN = 90        # 이 길이 이상이면 GA4 절단으로 보고 앞부분을 비교한다
JACCARD_MIN = 0.6
MARGIN_MIN = 0.1
STOP = {"a", "an", "the", "of", "to", "in", "on", "at", "for", "and", "or", "as", "is", "by", "with", "from"}

SITE = "https://www.koreatimes.co.kr"
LIVE_SLEEP = 0.3
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]*)"')

SCHEMA = """
CREATE TABLE IF NOT EXISTS url_aliases(
  alias_url TEXT PRIMARY KEY, article_id TEXT, canonical_url TEXT, method TEXT, score REAL,
  second_score REAL, matched_at TEXT);
"""


def norm(path):
    p = path.split("?")[0].split("#")[0]
    p = re.sub(r"^https?://[^/]+", "", p).rstrip("/")
    return p[4:] if p.startswith("/amp/") else p


def tokens(slug):
    return {t for t in slug.split("-") if t and t not in STOP}


def split(url):
    """('/섹션/…', 'YYYYMMDD', slug) 또는 None."""
    m = DATE_RE.search(url)
    if not m:
        return None
    return m.group(1), url[m.end():]


class Index:
    def __init__(self, conn):
        r = conn.execute("SELECT MIN(substr(pub_dt,1,10)) FROM articles").fetchone()[0]
        self.min_day = r.replace("-", "") if r else "00000000"
        self.by_date = defaultdict(list)       # 날짜 -> [(article_id, canonical_url, slug, tokens)]
        self.exact = {}
        for aid, cu, su in conn.execute("SELECT article_id, canonical_url, slug_url FROM articles"):
            for u in {cu, su}:
                if u:
                    self.exact[u] = (aid, cu)
            s = split(cu or "")
            if s:
                self.by_date[s[0]].append((aid, cu, s[1], tokens(s[1])))

    def match(self, path):
        """(method, article_id, canonical_url, score, second)"""
        p = norm(path)
        if p in self.exact:
            a, c = self.exact[p]
            return "exact", a, c, 1.0, 0.0
        s = split(p)
        if not s:
            return "none", None, None, 0.0, 0.0
        day, slug = s
        if day < self.min_day:
            return "pre_ledger", None, None, 0.0, 0.0
        cands = self.by_date.get(day, [])
        if p.endswith("…"):                       # GA4가 잘라 붙인 말줄임표
            p = p[:-1]
        if len(p) >= TRUNC_MIN or path.rstrip().endswith("…"):
            hit = [(a, c) for a, c, _, _ in cands if c.startswith(p)]
            if len(hit) == 1:
                return "prefix", hit[0][0], hit[0][1], 1.0, 0.0
        same = [(a, c) for a, c, sl, _ in cands if sl == slug]
        if len(same) == 1:
            return "slug", same[0][0], same[0][1], 1.0, 0.0
        tk = tokens(slug)
        if not tk or not cands:
            return "none", None, None, 0.0, 0.0
        scored = sorted(((len(tk & t) / len(tk | t) if t else 0.0, a, c) for a, c, _, t in cands), reverse=True)
        best = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0.0
        if best[0] >= JACCARD_MIN and best[0] - second >= MARGIN_MIN:
            return "fuzzy", best[1], best[2], round(best[0], 3), round(second, 3)
        return "none", None, None, round(best[0], 3), round(second, 3)


def live_canonical(idx, path):
    """실제 페이지의 canonical로 원장과 맞춘다. (method, article_id, canonical_url)"""
    req = urllib.request.Request(SITE + norm(path), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read(200000).decode("utf-8", "ignore")
    except Exception:
        return "none", None, None
    m = CANON_RE.search(html)
    if not m:
        return "none", None, None
    c = norm(m.group(1))
    if not split(c):
        return "gone", None, None
    if c in idx.exact:
        a, cu = idx.exact[c]
        return "canonical", a, cu
    return "missing", None, c


def apply_live(idx, rows, results, limit):
    """PV 큰 순으로 none·fuzzy 경로에 live_canonical을 적용한다. 확인되면 fuzzy 결과를 덮어쓴다."""
    todo = sorted((x for x in rows if results[x[0]][0] in ("none", "fuzzy")), key=lambda x: -x[1])[:limit]
    for path, _ in todo:
        m, a, c = live_canonical(idx, path)
        if m != "none":
            results[path] = (m, a, c, 1.0, 0.0)
        time.sleep(LIVE_SLEEP)


def connect_rw():
    conn = sqlite3.connect(DB, timeout=30)
    conn.executescript(SCHEMA)
    return conn


def save(conn, results):
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        for path, (m, a, c, sc, sec) in results.items():
            if m in ("exact", "none", "pre_ledger"):
                continue   # 원장 URL 그대로이거나 매칭 실패는 기록하지 않는다
            conn.execute("INSERT OR REPLACE INTO url_aliases VALUES(?,?,?,?,?,?,?)",
                         (norm(path), a, c, m, sc, sec, now))


def summarize(rows, results):
    """rows: [(path, pv)]. 방법별 경로 수와 PV."""
    agg = defaultdict(lambda: [0, 0])
    for path, pv in rows:
        m = results[path][0]
        agg[m][0] += 1
        agg[m][1] += pv
    total = sum(v[1] for v in agg.values()) or 1
    for m in ("exact", "prefix", "slug", "fuzzy", "canonical", "missing", "gone", "pre_ledger", "none"):
        n, pv = agg.get(m, (0, 0))
        print(f"  {m:6s} 경로 {n:4d}  PV {pv:7d} ({pv / total:.1%})")


def ga4_rows(token, day):
    from ga4_check import DATA, call
    ymd = day.replace("-", "")
    out, off = {}, 0
    while True:
        r = call(token, "POST", f"{DATA}/properties/340662437:runReport", {
            "dateRanges": [{"startDate": day, "endDate": day}],
            "dimensions": [{"name": "pagePath"}], "metrics": [{"name": "screenPageViews"}],
            "dimensionFilter": {"filter": {"fieldName": "pagePath",
                                           "stringFilter": {"matchType": "CONTAINS", "value": f"/{ymd}/"}}},
            "limit": 100000, "offset": off})
        for x in r.get("rows", []):
            k = x["dimensionValues"][0]["value"]
            out[k] = out.get(k, 0) + int(x["metricValues"][0]["value"])
        off += 100000
        if off >= r.get("rowCount", 0):
            return list(out.items())


def cmd_ga4(args):
    import argparse as ap
    from searchconsole_check import DEFAULT_CLIENT, DEFAULT_TOKEN, access_token
    token = access_token(ap.Namespace(client_json=str(DEFAULT_CLIENT), token_file=str(DEFAULT_TOKEN)))
    conn = connect_rw()
    idx = Index(conn)
    for day in args.days:
        rows = ga4_rows(token, day)
        results = {p: idx.match(p) for p, _ in rows}
        if args.live:
            apply_live(idx, rows, results, args.live)
        print(f"{day}: GA4 경로 {len(rows)}개")
        summarize(rows, results)
        if not args.dry_run:
            save(conn, results)


def sc_paths(types):
    """Search Console 원본에서 기사 경로(URL에 /YYYYMMDD/ 포함)별 합계를 모은다. {path: [clicks, impressions]}"""
    agg = defaultdict(lambda: [0, 0])
    files = 0
    for t in types:
        for f in sorted((ROOT / "data" / "searchconsole" / "raw" / t).glob("*.json.gz")):
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                d = json.load(fh)
            pi = d["dimensions"].index("page")
            for r in d["rows"]:
                url = norm(r["keys"][pi])
                sp = split(url)
                if sp and sp[1]:               # 날짜 뒤에 슬러그가 있는 기사 경로만(날짜별 목록 페이지 제외)
                    a = agg[url]
                    a[0] += r["clicks"]
                    a[1] += r["impressions"]
            files += 1
    print(f"파일 {files}개, 기사 경로 {len(agg)}개", flush=True)
    return agg


def cmd_sc(args):
    conn = connect_rw()
    idx = Index(conn)
    agg = sc_paths(args.types.split(","))
    rows = [(p, v[0]) for p, v in agg.items()]          # PV 대신 클릭 수로 우선순위
    results = {p: idx.match(p) for p, _ in rows}
    if args.live:
        # 클릭이 0인 경로가 대부분이라 노출 수도 함께 본다: 클릭 → 노출 순
        order = sorted(agg, key=lambda p: (-agg[p][0], -agg[p][1]))
        sel = [(p, agg[p][0] * 1000 + agg[p][1]) for p in order]
        apply_live(idx, sel, results, args.live)
    for name, k in (("클릭", 0), ("노출", 1)):
        print(f"[{name} 기준]")
        summarize([(p, agg[p][k]) for p in agg], results)
    print(f"경로 수 기준 none {sum(1 for r in results.values() if r[0] == 'none')}개 / {len(results)}개")
    if not args.dry_run:
        save(conn, results)


def cmd_urls(args):
    conn = connect_rw()
    idx = Index(conn)
    paths = [l.strip() for l in Path(args.file).read_text(encoding="utf-8").splitlines() if l.strip()]
    results = {p: idx.match(p) for p in paths}
    if args.live:
        apply_live(idx, [(p, 1) for p in paths], results, args.live)
    summarize([(p, 1) for p in paths], results)
    if not args.dry_run:
        save(conn, results)


def cmd_sample(args):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=30)
    for a, c, m, sc, sec in conn.execute(
            "SELECT alias_url, canonical_url, method, score, second_score FROM url_aliases "
            "WHERE method=? ORDER BY RANDOM() LIMIT ?", (args.method, args.n)):
        print(f"[{m} {sc} / 2등 {sec}]\n  GA4 {a}\n  원장 {c}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("ga4")
    g.add_argument("--days", nargs="+", required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--live", type=int, default=0, help="매칭 실패 경로 중 PV 상위 N개를 실제 페이지로 확인")
    u = sub.add_parser("urls")
    u.add_argument("--file", required=True)
    u.add_argument("--dry-run", action="store_true")
    u.add_argument("--live", type=int, default=0, help="매칭 실패 경로 중 상위 N개를 실제 페이지로 확인")
    c = sub.add_parser("sc")
    c.add_argument("--types", default="web,news,discover,googleNews")
    c.add_argument("--live", type=int, default=0, help="매칭 실패·fuzzy 경로 중 클릭·노출 상위 N개를 실제 페이지로 확인")
    c.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("sample")
    s.add_argument("--n", type=int, default=30)
    s.add_argument("--method", default="fuzzy")
    args = ap.parse_args()
    {"ga4": cmd_ga4, "sc": cmd_sc, "urls": cmd_urls, "sample": cmd_sample}[args.cmd](args)


if __name__ == "__main__":
    main()
