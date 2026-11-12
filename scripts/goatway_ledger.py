#!/usr/bin/env python3
"""goatway 기사 API 원장 수집 스크립트. 표준 라이브러리만 사용한다.

계획: docs/jobs/2026-11-06-goatway-ledger-collection-plan.md

하위 명령
  find-start    시작일에 해당하는 마지막 페이지를 이분 탐색으로 찾는다(저장하지 않음).
  collect       전체 수집(0페이지 → 깊은 페이지). --resume 이면 중단된 실행을 이어 받는다.
  retry-failed  실패한 페이지만 다시 받는다.
  incremental   0페이지부터 받아 이미 가진 기사만 나오는 페이지에서 멈춘다.
  check         V1~V4 검사를 하고 checks 표에 기록한다.
  export        articles를 CSV로 내보내고 SQLite를 백업한다.

저장: data/ledger/{raw/{run_id}/page_NNNNN.json.gz, ledger.sqlite, exports/, backup/}
기자 이메일은 원장에 넣지 않는다(원본 파일에만 남는다).
"""
import argparse
import csv
import fcntl
import gzip
import hashlib
import json
import os
import re
import sqlite3
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "ledger"
URL = "https://goatway.koreatimes.co.kr/api/home/article/latest?page={page}&size=10"
UA = "kt-ledger-collector/0.1"
KST = ZoneInfo("Asia/Seoul")
INTERVAL = 0.3
TIMEOUT = 30
RETRY_WAIT = (2, 5, 15)
MAX_PAGE = 40000  # 총 397,925건 / 10 = 약 39,793 페이지
MARGIN_PAGES = 50
DEFAULT_START = "2025-03-01"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, mode TEXT, started_at TEXT, ended_at TEXT,
  start_date TEXT, last_page INTEGER, ok_pages INTEGER, failed_pages INTEGER, memo TEXT);
CREATE TABLE IF NOT EXISTS pages(
  run_id TEXT, page INTEGER, fetched_at TEXT, http_status INTEGER, elapsed_ms INTEGER,
  attempts INTEGER, n_items INTEGER, first_pub TEXT, last_pub TEXT, raw_path TEXT,
  sha256 TEXT, ok INTEGER, PRIMARY KEY(run_id, page));
CREATE TABLE IF NOT EXISTS articles(
  article_id TEXT PRIMARY KEY, herb_article_id TEXT, pub_dt_raw TEXT,
  pc_title TEXT, mobile_title TEXT, seo_title TEXT, lead TEXT, reporter_name TEXT,
  main_section_id TEXT, main_section_en TEXT, section_breadcrumb TEXT,
  canonical_url TEXT, slug_url TEXT, read_time TEXT, thumbnail TEXT,
  pub_dt TEXT, is_yonhap INTEGER, slug_date TEXT, amp_match_key TEXT,
  first_seen_run TEXT, last_seen_run TEXT, first_seen_at TEXT, last_seen_at TEXT, content_hash TEXT);
CREATE INDEX IF NOT EXISTS ix_articles_pub ON articles(pub_dt);
CREATE INDEX IF NOT EXISTS ix_articles_url ON articles(canonical_url);
CREATE INDEX IF NOT EXISTS ix_articles_herb ON articles(herb_article_id);
CREATE INDEX IF NOT EXISTS ix_articles_amp ON articles(amp_match_key);
CREATE TABLE IF NOT EXISTS article_versions(
  article_id TEXT, content_hash TEXT, pc_title TEXT, mobile_title TEXT, seo_title TEXT,
  lead TEXT, canonical_url TEXT, replaced_in_run TEXT, replaced_at TEXT,
  PRIMARY KEY(article_id, content_hash));
CREATE TABLE IF NOT EXISTS checks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, kind TEXT, severity TEXT,
  detail TEXT, created_at TEXT);
"""


def now():
    return datetime.now(KST).isoformat(timespec="seconds")


def connect():
    LEDGER.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LEDGER / "ledger.sqlite")
    conn.executescript(SCHEMA)
    return conn


def lock():
    LEDGER.mkdir(parents=True, exist_ok=True)
    f = open(LEDGER / ".lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("다른 수집이 실행 중이다.")
    return f


def fetch(page):
    """(body bytes, http_status, elapsed_ms, attempts) 또는 (None, status, ms, attempts)."""
    status, ms = 0, 0
    for attempt in range(len(RETRY_WAIT) + 1):
        t0 = time.time()
        try:
            req = urllib.request.Request(URL.format(page=page), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                status, body = r.status, r.read()
            ms = int((time.time() - t0) * 1000)
            if status == 200 and json.loads(body).get("result") == "success":
                return body, status, ms, attempt + 1
        except urllib.error.HTTPError as e:
            status, ms = e.code, int((time.time() - t0) * 1000)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            ms = int((time.time() - t0) * 1000)
        if attempt < len(RETRY_WAIT):
            time.sleep(RETRY_WAIT[attempt])
    return None, status, ms, len(RETRY_WAIT) + 1


def contents(body):
    return json.loads(body)["data"]["contents"]


def first_pub(page):
    body, *_ = fetch(page)
    if body is None:
        sys.exit(f"페이지 {page} 조회 실패")
    c = contents(body)
    return c[0]["pubDt"] if c else None


def find_last_page(start_date):
    """첫 기사 pubDt가 start_date 0시보다 이른 가장 작은 페이지 번호."""
    limit = f"{start_date} 00:00:00"
    lo, hi = 0, MAX_PAGE
    while lo < hi:
        mid = (lo + hi) // 2
        fp = first_pub(mid)
        print(f"  탐색 page={mid} 첫 pubDt={fp}", flush=True)
        if fp is None or fp < limit:
            hi = mid
        else:
            lo = mid + 1
        time.sleep(INTERVAL)
    return lo


def derive(a):
    canon = a.get("canonicalUrl") or ""
    m = re.search(r"/(\d{8})/", canon)
    pub_raw = a.get("pubDt") or ""
    iso = pub_raw.replace(" ", "T") + "+09:00" if pub_raw else None
    h = hashlib.sha256("\x1f".join([
        a.get("pcTitle") or "", a.get("mobileTitle") or "", a.get("seoTitle") or "",
        a.get("lead") or "", canon]).encode()).hexdigest()
    return {
        "article_id": a["articleId"], "herb_article_id": a.get("herbArticleId"), "pub_dt_raw": pub_raw,
        "pc_title": a.get("pcTitle"), "mobile_title": a.get("mobileTitle"), "seo_title": a.get("seoTitle"),
        "lead": a.get("lead"), "reporter_name": a.get("reporterName"),
        "main_section_id": a.get("mainSectionId"), "main_section_en": a.get("mainSectionNameEn"),
        "section_breadcrumb": a.get("sectionBreadcrumb"), "canonical_url": canon,
        "slug_url": a.get("slugUrl"), "read_time": a.get("articleReadTime"), "thumbnail": a.get("thumbnail"),
        "pub_dt": iso, "is_yonhap": 1 if a.get("reporterName") == "Yonhap" else 0,
        "slug_date": m.group(1) if m else None, "amp_match_key": ("/amp" + canon)[:100],
        "content_hash": h,
    }


def upsert_articles(conn, run_id, items):
    """저장 규칙: 덮어쓰지 않고 last_seen만 갱신. 내용이 바뀌면 이전 값을 article_versions에 남긴다."""
    ts, new = now(), 0
    for a in items:
        d = derive(a)
        row = conn.execute("SELECT content_hash, pc_title, mobile_title, seo_title, lead, canonical_url "
                           "FROM articles WHERE article_id=?", (d["article_id"],)).fetchone()
        if row is None:
            cols = list(d) + ["first_seen_run", "last_seen_run", "first_seen_at", "last_seen_at"]
            vals = list(d.values()) + [run_id, run_id, ts, ts]
            conn.execute(f"INSERT INTO articles({','.join(cols)}) VALUES({','.join('?' * len(cols))})", vals)
            new += 1
        elif row[0] != d["content_hash"]:
            conn.execute("INSERT OR IGNORE INTO article_versions VALUES(?,?,?,?,?,?,?,?,?)",
                         (d["article_id"], row[0], row[1], row[2], row[3], row[4], row[5], run_id, ts))
            sets = [k for k in d if k != "article_id"]
            conn.execute(f"UPDATE articles SET {','.join(k + '=?' for k in sets)}, last_seen_run=?, last_seen_at=? "
                         "WHERE article_id=?", [d[k] for k in sets] + [run_id, ts, d["article_id"]])
        else:
            conn.execute("UPDATE articles SET last_seen_run=?, last_seen_at=? WHERE article_id=?",
                         (run_id, ts, d["article_id"]))
    return new


def save_raw(run_id, page, body):
    p = LEDGER / "raw" / run_id / f"page_{page:05d}.json.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with gzip.open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, p)
    return str(p.relative_to(ROOT))


def process_page(conn, run_id, page):
    """한 페이지를 받아 저장. 반환: (성공 여부, 신규 기사 수, 전부 이미 아는 기사인지)."""
    body, status, ms, attempts = fetch(page)
    ts = now()
    if body is None:
        with conn:
            conn.execute("INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                         (run_id, page, ts, status, ms, attempts, 0, None, None, None, None, 0))
        return False, 0, False
    items = contents(body)
    known = (all(conn.execute("SELECT 1 FROM articles WHERE article_id=?", (a["articleId"],)).fetchone()
                 for a in items) if items else True)
    raw = save_raw(run_id, page, body)
    with conn:
        new = upsert_articles(conn, run_id, items)
        conn.execute("INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                     (run_id, page, ts, status, ms, attempts, len(items),
                      items[0]["pubDt"] if items else None, items[-1]["pubDt"] if items else None,
                      raw, hashlib.sha256(body).hexdigest(), 1))
    return True, new, known


def new_run_id():
    return datetime.now(KST).strftime("%Y%m%dT%H%M")


def finish_run(conn, run_id):
    ok, bad = conn.execute("SELECT COALESCE(SUM(ok=1),0), COALESCE(SUM(ok=0),0) FROM pages WHERE run_id=?",
                           (run_id,)).fetchone()
    with conn:
        conn.execute("UPDATE runs SET ended_at=?, ok_pages=?, failed_pages=? WHERE run_id=?",
                     (now(), ok, bad, run_id))
    return ok, bad


def cmd_find_start(args):
    last = find_last_page(args.start_date)
    print(f"시작일 {args.start_date}: 마지막 페이지 {last} (+{MARGIN_PAGES} 여유 = {last + MARGIN_PAGES})")


def cmd_collect(args):
    _lock = lock()
    conn = connect()
    if args.resume:
        r = conn.execute("SELECT run_id, start_date, last_page FROM runs WHERE mode='full' AND ended_at IS NULL "
                         "ORDER BY started_at DESC LIMIT 1").fetchone()
        if not r:
            sys.exit("이어 받을 미완료 전체 수집이 없다.")
        run_id, start_date, last_page = r
        print(f"이어받기: run_id={run_id} 마지막 페이지 {last_page}")
    else:
        start_date = args.start_date
        print(f"마지막 페이지 탐색 (시작일 {start_date})")
        last_page = find_last_page(start_date) + MARGIN_PAGES
        run_id = new_run_id()
        with conn:
            conn.execute("INSERT INTO runs(run_id,mode,started_at,start_date,last_page) VALUES(?,?,?,?,?)",
                         (run_id, "full", now(), start_date, last_page))
    done = {p for (p,) in conn.execute("SELECT page FROM pages WHERE run_id=? AND ok=1", (run_id,))}
    total_new = 0
    t0 = time.time()
    for page in range(0, last_page + 1):
        if page in done:
            continue
        if args.max_pages is not None and page >= args.max_pages:
            print(f"--max-pages {args.max_pages} 도달(시험). 실행은 미완료로 남는다.")
            return
        ok, new, _ = process_page(conn, run_id, page)
        total_new += new
        if page % 50 == 0 or not ok:
            print(f"page {page}/{last_page} {'OK' if ok else '실패'} 신규 {total_new} 경과 {int(time.time() - t0)}초",
                  flush=True)
        time.sleep(INTERVAL)
    # 마무리 재수집: 수집 중 새로 발행된 기사. 이미 가진 기사만 나오는 페이지에서 멈춘다
    page = 0
    while page < 200:
        ok, new, known = process_page(conn, run_id, page)
        total_new += new
        if ok and known:
            break
        page += 1
        time.sleep(INTERVAL)
    ok, bad = finish_run(conn, run_id)
    print(f"완료 run_id={run_id}: 성공 {ok}페이지, 실패 {bad}페이지, 신규 기사 {total_new}")


def cmd_retry_failed(args):
    _lock = lock()
    conn = connect()
    r = conn.execute("SELECT run_id FROM runs WHERE mode='full' ORDER BY started_at DESC LIMIT 1").fetchone()
    if not r:
        sys.exit("전체 수집 기록이 없다.")
    run_id = r[0]
    failed = [p for (p,) in conn.execute("SELECT page FROM pages WHERE run_id=? AND ok=0 ORDER BY page", (run_id,))]
    print(f"run_id={run_id} 실패 페이지 {len(failed)}건 재시도")
    for page in failed:
        ok, new, _ = process_page(conn, run_id, page)
        print(f"page {page} {'OK' if ok else '실패'}")
        time.sleep(INTERVAL)
    ok, bad = finish_run(conn, run_id)
    print(f"성공 {ok}, 실패 {bad}")


def cmd_incremental(args):
    _lock = lock()
    conn = connect()
    run_id = new_run_id()
    with conn:
        conn.execute("INSERT INTO runs(run_id,mode,started_at) VALUES(?,?,?)", (run_id, "incremental", now()))
    total_new = 0
    for page in range(0, 200):
        ok, new, known = process_page(conn, run_id, page)
        total_new += new
        print(f"page {page} {'OK' if ok else '실패'} 신규 {new}")
        if ok and known:
            break
        time.sleep(INTERVAL)
    else:
        print("경고: 200페이지(약 2000건)를 받도록 기존 기사에 닿지 않았다. 오래 꺼져 있어 빠진 구간이 있을 수 있다. "
              "collect로 전체 구간을 다시 받는다.", file=sys.stderr)
        bad_gap = True
    ok, bad = finish_run(conn, run_id)
    print(f"완료 run_id={run_id}: 성공 {ok}페이지, 실패 {bad}페이지, 신규 기사 {total_new}")
    if bad or locals().get("bad_gap"):
        sys.exit(1)


def add_check(conn, run_id, kind, severity, detail):
    conn.execute("INSERT INTO checks(run_id,kind,severity,detail,created_at) VALUES(?,?,?,?,?)",
                 (run_id, kind, severity, json.dumps(detail, ensure_ascii=False), now()))


def cmd_check(args):
    conn = connect()
    r = conn.execute("SELECT run_id FROM runs WHERE mode='full' ORDER BY started_at DESC LIMIT 1").fetchone()
    run_id = r[0] if r else None
    if run_id is None:
        sys.exit("전체 수집 기록이 없다.")
    with conn:
        # V1 실패 페이지
        failed = [p for (p,) in conn.execute("SELECT page FROM pages WHERE run_id=? AND ok=0", (run_id,))]
        print(f"V1 실패 페이지: {len(failed)}건")
        add_check(conn, run_id, "V1_failed_pages", "error" if failed else "ok", {"pages": failed[:50], "count": len(failed)})
        # V2 연속성
        rows = conn.execute("SELECT page, first_pub, last_pub FROM pages WHERE run_id=? AND ok=1 ORDER BY page",
                            (run_id,)).fetchall()
        bad = [(a[0], b[0], a[2], b[1]) for a, b in zip(rows, rows[1:])
               if b[0] == a[0] + 1 and a[2] and b[1] and a[2] < b[1]]
        print(f"V2 연속성 어긋남: {len(bad)}건")
        add_check(conn, run_id, "V2_continuity", "error" if bad else "ok",
                  {"count": len(bad), "samples": bad[:20]})
        # V3 pub_dt 날짜와 slug_date
        mism = conn.execute("SELECT article_id, pub_dt, slug_date FROM articles WHERE slug_date IS NOT NULL "
                            "AND replace(substr(pub_dt,1,10),'-','') <> slug_date").fetchall()
        n_slug = conn.execute("SELECT COUNT(*) FROM articles WHERE slug_date IS NOT NULL").fetchone()[0]
        near_mid = sum(1 for _, p, _ in mism if p[11:13] in ("23", "00", "01"))
        print(f"V3 pub_dt 날짜 ≠ slug_date: {len(mism)}건 / {n_slug}건 (자정 근처 23~01시 {near_mid}건)")
        add_check(conn, run_id, "V3_timezone", "warn" if mism else "ok",
                  {"count": len(mism), "of": n_slug, "near_midnight": near_mid, "samples": mism[:20]})
        # V4 일별 건수
        days = dict(conn.execute("SELECT substr(pub_dt,1,10), COUNT(*) FROM articles GROUP BY 1").fetchall())
        if days:
            d0, d1 = date.fromisoformat(min(days)), date.fromisoformat(max(days))
            lo = date.fromisoformat(conn.execute("SELECT start_date FROM runs WHERE run_id=?", (run_id,)).fetchone()[0])
            d0 = max(d0, lo)
            span = [d0 + timedelta(i) for i in range((d1 - d0).days + 1)]
            counts = [days.get(d.isoformat(), 0) for d in span]
            med = statistics.median(counts)
            zero = [d.isoformat() for d, c in zip(span, counts) if c == 0]
            low = [(d.isoformat(), c) for d, c in zip(span, counts) if 0 < c < med / 2]
            print(f"V4 일별 건수: 중앙 {med}, 0건 {len(zero)}일, 중앙의 절반 미만 {len(low)}일")
            add_check(conn, run_id, "V4_daily_counts", "warn" if zero or low else "ok",
                      {"median": med, "zero_days": zero[:60], "low_days": low[:60]})
    tot = conn.execute("SELECT COUNT(*), MIN(pub_dt), MAX(pub_dt), SUM(is_yonhap) FROM articles").fetchone()
    print(f"기사 {tot[0]}건, {tot[1]} ~ {tot[2]}, Yonhap {tot[3]}건")
    print("V5(표본 대조), V6(GA4 대조)는 사람이 하거나 별도 조회가 필요하다.")


def cmd_export(args):
    conn = connect()
    stamp = datetime.now(KST).strftime("%Y%m%d")
    (LEDGER / "exports").mkdir(parents=True, exist_ok=True)
    (LEDGER / "backup").mkdir(parents=True, exist_ok=True)
    path = LEDGER / "exports" / f"articles_{stamp}.csv"
    cur = conn.execute("SELECT * FROM articles ORDER BY pub_dt")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([c[0] for c in cur.description])
        w.writerows(cur)
    dst = sqlite3.connect(LEDGER / "backup" / f"ledger_{stamp}.sqlite")
    conn.backup(dst)
    dst.close()
    print(f"내보내기: {path}\n백업: {LEDGER / 'backup' / f'ledger_{stamp}.sqlite'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("find-start")
    p.add_argument("--start-date", default=DEFAULT_START)
    p = sub.add_parser("collect")
    p.add_argument("--start-date", default=DEFAULT_START)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--max-pages", type=int, help="시험용: 이 페이지 번호 전까지만 받고 멈춘다")
    sub.add_parser("retry-failed")
    sub.add_parser("incremental")
    sub.add_parser("check")
    sub.add_parser("export")
    args = ap.parse_args()
    {"find-start": cmd_find_start, "collect": cmd_collect, "retry-failed": cmd_retry_failed,
     "incremental": cmd_incremental, "check": cmd_check, "export": cmd_export}[args.cmd](args)


if __name__ == "__main__":
    main()
