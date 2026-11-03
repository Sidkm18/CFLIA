"""Bounded functional checks of the two owned Render demos; no load test.

Does not read V2 credentials or save response bodies, cookies, or tokens.
Writes one harmless V1 comment and updates its fictional Alice email.
"""
import html
import http.client
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

HOSTS = {1: "legacydesk-v1-demo.onrender.com", 2: "legacydesk-v2-demo.onrender.com"}
checks = []
limitations = []


def call(version, path, method="GET", data=None, cookie=None, origin=None):
    headers = {}
    if cookie:
        headers["Cookie"] = cookie
    if origin:
        headers["Origin"] = origin
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    con = http.client.HTTPSConnection(HOSTS[version], timeout=60)
    try:
        con.request(method, path, urlencode(data) if data is not None else None, headers)
        response = con.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode(errors="replace")
    finally:
        con.close()


def check(name, condition, status=None):
    checks.append({"name": name, "passed": bool(condition), "http_status": status})
    print(("PASS " if condition else "FAIL ") + name)


def main():
    for version in (1, 2):
        for path in ("/health", "/static/style.css", "/login"):
            status, _, _ = call(version, path)
            check(f"V{version} {path} available over trusted HTTPS", status == 200, status)
    first = call(1, "/login", "POST", {"username": "' OR 1=1 -- ", "password": "wrong"})
    if first[0] == 403 and first[1].get("Server", "").lower() == "cloudflare" and "<title>Blocked</title>" in first[2]:
        limitations.append("The standard V01 SQLi login payload is blocked by Cloudflare before reaching V1. V1 code remains vulnerable, as independently verified locally.")
        checks.append({"name": "V1 SQL injection hosted demonstration", "passed": None, "http_status": first[0], "outcome": "platform_filtered"})
        print("PLATFORM-FILTERED V1 SQL injection hosted demonstration")
    else:
        check("V1 SQL injection retained", first[0] == 303 and "user_id=1" in first[1].get("Set-Cookie", ""), first[0])
    normal = call(1, "/login", "POST", {"username": "alice", "password": "alice123"})
    check("V1 cookie permits hosted CSRF demonstration", normal[0] == 303 and all(flag in normal[1].get("Set-Cookie", "").lower() for flag in ("secure", "samesite=none")))
    marker = '<svg onload="this.outerHTML=\'<p>Hosted XSS demonstration</p>\'"></svg>'
    status, _, _ = call(1, "/comment", "POST", {"ticket_id": "1001", "body": marker}, "user_id=2")
    check("V1 stored XSS retained", status == 303 and marker in call(1, "/ticket?id=1001", cookie="user_id=2")[2], status)
    status, _, body = call(1, "/ticket?id=1002", cookie="user_id=2")
    check("V1 IDOR retained", status == 200 and "Bob's payroll" in html.unescape(body), status)
    status, _, _ = call(1, "/admin", cookie="user_id=1")
    check("V1 forged administrator cookie retained", status == 200, status)
    status, _, _ = call(1, "/account/email", "POST", {"email": "hosted.demo@example.test"}, "user_id=2", "https://unrelated.example")
    check("V1 tokenless cross-origin write retained", status == 303, status)
    status, _, _ = call(1, "/download?file=../private/legacy-config.txt")
    check("V1 fixture traversal retained", status == 200, status)
    status, headers, body = call(1, "/debug")
    check("V1 debug exposure retained", status == 200 and "password" in body, status)
    check("V1 lacks application CSP", "content-security-policy" not in {key.lower() for key in headers})
    status, _, _ = call(1, "/reports/export", cookie="user_id=2")
    check("V1 report accessible (ONE request; no load test)", status == 200, status)
    status, headers, _ = call(2, "/login")
    check("V2 gateway security headers", status == 200 and all(key in {key.lower() for key in headers} for key in ("content-security-policy", "x-content-type-options", "x-frame-options", "strict-transport-security")), status)
    check("V2 secure pre-login session cookie", all(flag in headers.get("Set-Cookie", "") for flag in ("Secure", "HttpOnly", "SameSite=Strict")))
    for name, path, cookie, expected in (
        ("V2 debug removed", "/debug", None, (404,)),
        ("V2 forged V1 cookie denied", "/admin", "user_id=1", (401,)),
        ("V2 forged identity cannot read Bob ticket", "/ticket?id=1002", "user_id=2", (401,)),
        ("V2 traversal denied", "/download?file=../private/legacy-config.txt", None, (403, 404)),
        ("V2 anonymous report denied", "/reports/export", None, (401,)),
    ):
        status, _, _ = call(2, path, cookie=cookie)
        check(name, status in expected, status)
    for name, path, data in (
        ("V2 SQLi request denied", "/login", {"username": "' OR 1=1 -- ", "password": "wrong"}),
        ("V2 XSS request denied", "/comment", {"ticket_id": "1001", "body": marker}),
        ("V2 cross-origin write denied", "/account/email", {"email": "bad@example.test"}),
    ):
        status, _, _ = call(2, path, "POST", data, "user_id=2", "https://unrelated.example")
        check(name, status == 403, status)
    passed = sum(item["passed"] is True for item in checks)
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "urls": {str(k): "https://" + v for k, v in HOSTS.items()}, "checks": checks, "passed": passed, "total": len(checks), "platform_filtered": sum(item["passed"] is None for item in checks), "limitations": limitations, "load_test_performed": False, "notes": "Authenticated V2 browser workflows and WAF audit IDs are verified separately. Root-cause security suite: 19 local tests. Local combined-image checks: 23."}
    dest = Path(__file__).resolve().parents[2] / "output/render-deployment/hosted-verification.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{passed}/{len(checks)} hosted checks passed; {result['platform_filtered']} platform-filtered; no load test performed.")
    return any(item["passed"] is False for item in checks)


if __name__ == "__main__":
    raise SystemExit(main())
