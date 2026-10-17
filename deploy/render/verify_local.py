"""Bounded localhost checks of the combined Render images. No hosted load test."""
import html
import http.client
import json
import re
from urllib.parse import urlencode

checks = []


def call(port, path, method="GET", data=None, cookie=None, origin=None):
    headers = {"Host": "localhost"}
    if cookie:
        headers["Cookie"] = cookie
    if origin:
        headers["Origin"] = origin
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    con = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        con.request(method, path, urlencode(data) if data is not None else None, headers)
        response = con.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode(errors="replace")
    finally:
        con.close()


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})
    print(("PASS " if condition else "FAIL ") + name)


def main():
    v1, v2 = 18080, 18443
    check("V1 health", call(v1, "/health")[0] == 200)
    result = call(v1, "/login", "POST", {"username": "' OR 1=1 -- ", "password": "wrong"})
    check("V1 SQL injection retained", result[0] == 303 and "user_id=1" in result[1].get("Set-Cookie", ""))
    check("V1 cross-site identity cookie", all(flag in result[1].get("Set-Cookie", "").lower() for flag in ("secure", "samesite=none")))
    marker = '<svg onload="this.outerHTML=\'<p>Render XSS demo</p>\'"></svg>'
    call(v1, "/comment", "POST", {"ticket_id": "1001", "body": marker}, "user_id=2")
    check("V1 stored XSS retained", marker in call(v1, "/ticket?id=1001", cookie="user_id=2")[2])
    check("V1 IDOR retained", "Bob's payroll" in html.unescape(call(v1, "/ticket?id=1002", cookie="user_id=2")[2]))
    check("V1 forged admin cookie retained", call(v1, "/admin", cookie="user_id=1")[0] == 200)
    result = call(v1, "/account/email", "POST", {"email": "render.demo@example.test"}, "user_id=2", "https://unrelated.example")
    check("V1 CSRF retained", result[0] == 303 and "render.demo@example.test" in call(v1, "/account", cookie="user_id=2")[2])
    check("V1 fixture traversal retained", call(v1, "/download?file=../private/legacy-config.txt")[0] == 200)
    debug = call(v1, "/debug")
    check("V1 debug and absent CSP retained", debug[0] == 200 and "password" in debug[2] and "Content-Security-Policy" not in debug[1])
    check("V1 report remains accessible (one request)", call(v1, "/reports/export", cookie="user_id=2")[0] == 200)

    check("V2 health", call(v2, "/health")[0] == 200)
    first = call(v2, "/login")
    check("V2 headers on login", first[0] == 200 and all(key in first[1] for key in ("Content-Security-Policy", "X-Content-Type-Options", "Strict-Transport-Security")))
    cookie = first[1]["Set-Cookie"].split(";", 1)[0]
    token = re.search(r'name="csrf_token" value="([^"]+)"', first[2])[1]
    result = call(v2, "/login", "POST", {"username": "alice", "password": "TestOnly-render-alice-83-long-password", "csrf_token": token}, cookie, "https://localhost")
    check("V2 legitimate sign-in", result[0] == 303)
    flags = result[1].get("Set-Cookie", "")
    check("V2 secure session cookie", all(flag in flags for flag in ("Secure", "HttpOnly", "SameSite=Strict")))
    cookie = flags.split(";", 1)[0]
    account = call(v2, "/account", cookie=cookie)
    token = re.search(r'name="csrf_token" value="([^"]+)"', account[2])[1]
    check("V2 legitimate workflow", call(v2, "/tickets", cookie=cookie)[0] == 200 and call(v2, "/download?file=employee-handbook.txt", cookie=cookie)[0] == 200)
    check("V2 IDOR denied", call(v2, "/ticket?id=1002", cookie=cookie)[0] == 403)
    check("V2 forged v1 cookie denied", call(v2, "/admin", cookie="user_id=1")[0] == 401)
    check("V2 CSRF denied", call(v2, "/account/email", "POST", {"email": "bad@example.test"}, cookie, "https://unrelated.example")[0] == 403)
    check("V2 debug removed", call(v2, "/debug")[0] == 404)
    check("V2 anonymous report denied", call(v2, "/reports/export")[0] == 401)
    result = call(v2, "/comment", "POST", {"ticket_id": "1001", "body": marker, "csrf_token": token}, cookie, "https://localhost")
    check("V2 WAF XSS block", result[0] == 403)
    result = call(v2, "/login", "POST", {"username": "' OR 1=1 -- ", "password": "wrong", "csrf_token": token}, cookie, "https://localhost")
    check("V2 WAF SQLi block", result[0] == 403)
    check("V2 traversal denied", call(v2, "/download?file=../private/legacy-config.txt", cookie=cookie)[0] in (403, 404))
    print(json.dumps({"passed": sum(item["passed"] for item in checks), "total": len(checks)}))
    return not all(item["passed"] for item in checks)


if __name__ == "__main__":
    raise SystemExit(main())
