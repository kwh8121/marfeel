#!/usr/bin/env python3
"""Search Console API 연결 확인 스크립트(읽기 전용). 표준 라이브러리만 사용한다.

하위 명령
  auth   브라우저 동의로 리프레시 토큰을 받아 저장한다(최초 1회).
  check  sites.list로 속성·권한 수준을 보고, 하루치 searchanalytics.query를 1회 호출한다.

자격 증명은 저장소 밖에 둔다.
  --client-json  GCP OAuth 클라이언트(데스크톱 앱) JSON. 기본 ~/.config/searchconsole/client.json
  --token-file   리프레시 토큰 저장 위치. 기본 ~/.cache/searchconsole/token.json (권한 600)
범위는 webmasters.readonly(Search Console)와 analytics.readonly(GA4)다. 둘 다 읽기 전용이다. 응답 원본은 저장하지 않고 요약만 출력한다.
"""
import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, timedelta
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",  # GA4 Data API용. 이 스크립트의 check는 쓰지 않는다
]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/webmasters/v3"
DEFAULT_CLIENT = Path.home() / ".config" / "searchconsole" / "client.json"
DEFAULT_TOKEN = Path.home() / ".cache" / "searchconsole" / "token.json"
DEFAULT_SITE = "sc-domain:koreatimes.co.kr"
TIMEOUT = 60
OLDEST_OFFSET_DAYS = 480  # 보존 16개월(약 486일)에서 며칠 여유를 둔다


def load_client(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    c = data.get("installed") or data.get("web")
    if not c:
        sys.exit("client.json에 installed(데스크톱 앱) 항목이 없다.")
    return c["client_id"], c["client_secret"]


def post_form(url, form):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode())
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        if "invalid_grant" in body:
            sys.exit(f"토큰 만료 또는 폐기(invalid_grant). 토큰 파일을 지우고 searchconsole_check.py auth를 다시 실행한다.\n{body}")
        sys.exit(f"토큰 요청 실패 HTTP {e.code}: {body}")


def cmd_auth(args):
    cid, secret = load_client(args.client_json)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    box = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            box["code"] = q.get("code", [None])[0]
            box["state"] = q.get("state", [None])[0]
            box["error"] = q.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("인증이 끝났다. 이 창을 닫아도 된다.".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = f"http://127.0.0.1:{srv.server_port}"
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent",
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    })
    print("브라우저에서 아래 주소로 kwh8121 계정 동의를 진행한다.\n" + url)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    t = threading.Thread(target=srv.handle_request)
    t.start()
    t.join(300)
    srv.server_close()
    if box.get("error") or not box.get("code") or box.get("state") != state:
        sys.exit(f"인증 실패 또는 시간 초과: {box.get('error')}")
    tok = post_form(TOKEN_URL, {
        "client_id": cid, "client_secret": secret, "code": box["code"],
        "code_verifier": verifier, "grant_type": "authorization_code", "redirect_uri": redirect,
    })
    if "refresh_token" not in tok:
        sys.exit("리프레시 토큰이 오지 않았다. 계정 연결 해제 후 다시 시도한다.")
    p = Path(args.token_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"refresh_token": tok["refresh_token"]}, f)
    print(f"토큰 저장: {p} (권한 600)")


def access_token(args):
    cid, secret = load_client(args.client_json)
    rt = json.loads(Path(args.token_file).read_text())["refresh_token"]
    return post_form(TOKEN_URL, {
        "client_id": cid, "client_secret": secret, "refresh_token": rt, "grant_type": "refresh_token",
    })["access_token"]


def call(token, method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {url}\n{e.read().decode()[:400]}")


def cmd_check(args):
    tok = access_token(args)
    sites = call(tok, "GET", f"{API}/sites").get("siteEntry", [])
    print("[sites.list]")
    for s in sites:
        print(f"  {s['siteUrl']}  permissionLevel={s['permissionLevel']}")
    if args.site not in {s["siteUrl"] for s in sites}:
        sys.exit(f"대상 속성 {args.site}이(가) 목록에 없다. --site를 위 목록 중 하나로 지정한다.")
    day = args.date or (date.today() - timedelta(days=OLDEST_OFFSET_DAYS)).isoformat()
    body = {"startDate": day, "endDate": day, "dimensions": ["date", "query", "page", "country"],
            "searchType": args.search_type, "rowLimit": 25}
    url = f"{API}/sites/{urllib.parse.quote(args.site, safe='')}/searchAnalytics/query"
    res = call(tok, "POST", url, body)
    rows = res.get("rows", [])
    print(f"[query] {day} searchType={args.search_type} 행 {len(rows)}건"
          f" (responseAggregationType={res.get('responseAggregationType')})")
    for r in rows[:5]:
        k = r["keys"]
        print(f"  {k[3]} | {k[1][:30]} | {k[2][:70]} | clicks={r['clicks']} imp={r['impressions']}")
    if not rows:
        print("  데이터 없음: 날짜가 보존 범위 밖이거나 해당 일 데이터가 없다. --date를 바꿔 본다.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client-json", default=str(DEFAULT_CLIENT))
    ap.add_argument("--token-file", default=str(DEFAULT_TOKEN))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth")
    c = sub.add_parser("check")
    c.add_argument("--site", default=DEFAULT_SITE)
    c.add_argument("--date", help="YYYY-MM-DD. 기본: 약 480일 전(가장 오래된 쪽)")
    c.add_argument("--search-type", default="web", choices=["web", "news", "image", "video", "discover", "googleNews"])
    args = ap.parse_args()
    {"auth": cmd_auth, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    main()
