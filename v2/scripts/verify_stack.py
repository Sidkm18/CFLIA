#!/usr/bin/env python3
"""Bounded integration checks against the v2 localhost gateway only.

Does not send attack traffic to v1, reset its database, or modify its files.
Credentials, CSRF values and session cookies are never written to evidence.
"""
import concurrent.futures
import datetime
import hashlib
import http.client
import json
import re
import ssl
import statistics
import subprocess
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://127.0.0.1:8443"
creds = json.loads((ROOT / "state/credentials.json").read_text())
context = ssl.create_default_context(cafile=str(ROOT / "state/tls/ca.crt"))
COOKIE = "__Host-legacydesk_v2"
records, checks = [], []


def call(path, method="GET", data=None, cookie=None, origin=None, capture=True):
    headers = {}
    body = urlencode(data) if data is not None else None
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if cookie:
        headers["Cookie"] = cookie
    if origin:
        headers["Origin"] = origin
    start = time.perf_counter()
    con = http.client.HTTPSConnection("127.0.0.1", 8443, timeout=10, context=context)
    try:
        con.request(method, path, body, headers)
        response = con.getresponse()
        result = {"status": response.status, "headers": dict(response.getheaders()),
                  "body": response.read().decode("utf-8", errors="replace"),
                  "latency_ms": round((time.perf_counter()-start)*1000, 2)}
    finally:
        con.close()
    if capture:
        records.append({"method": method, "path": path, "status": result["status"],
                        "latency_ms": result["latency_ms"],
                        "request_id": result["headers"].get("X-Request-ID"),
                        "csrf_present": bool(data and "csrf_token" in data)})
    return result


def check(name, condition, details):
    checks.append({"check": name, "passed": bool(condition), "details": details})
    print(("PASS " if condition else "FAIL ") + name)


def login():
    first = call("/login")
    assert first["status"] == 200, "Sign-in page unavailable or throttled"
    token = re.search(r'name="csrf_token" value="([^"]+)"', first["body"])[1]
    cookie = first["headers"]["Set-Cookie"].split(";", 1)[0]
    result = call("/login", "POST", {"username": "alice", "password": creds["alice"], "csrf_token": token}, cookie, ORIGIN)
    assert result["status"] == 303, "Valid v2 sign-in failed"
    cookie = result["headers"]["Set-Cookie"].split(";", 1)[0]
    account = call("/account", cookie=cookie)
    token = re.search(r'name="csrf_token" value="([^"]+)"', account["body"])[1]
    return cookie, token, result


def main():
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = ROOT / "output" / ("verification-" + timestamp)
    dest.mkdir(parents=True)
    manifest = json.loads((ROOT / "output/original-manifest.json").read_text())
    unchanged = all(hashlib.sha256((ROOT.parent / p).read_bytes()).hexdigest() == sha for p, sha in manifest.items())
    check("Original source preserved", unchanged, f"Checked all {len(manifest)} previously tracked files by SHA-256.")
    baseline = http.client.HTTPConnection("127.0.0.1", 8080, timeout=5)
    baseline.request("GET", "/health")
    response = baseline.getresponse()
    check("Original site still running", response.status == 200, "Read-only health request on port 8080.")
    response.read()
    baseline.close()
    redirect = http.client.HTTPConnection("127.0.0.1", 8082, timeout=5)
    redirect.request("GET", "/login")
    response = redirect.getresponse()
    check("HTTP redirects to HTTPS", response.status == 308 and response.getheader("Location") == ORIGIN + "/login", "Dedicated port 8082 redirects to 8443.")
    response.read()
    redirect.close()
    cookie, token, auth = login()
    check("Legitimate HTTPS sign-in", auth["status"] == 303, "Server-side session established using v2's generated password.")
    flags = auth["headers"]["Set-Cookie"]
    check("Session cookie policy", all(x in flags for x in ["Secure", "HttpOnly", "SameSite=Strict", "Path=/"]), "Cookie values redacted from all saved evidence.")
    injected = call("/login", "POST", {"username": "' OR 1=1 -- ", "password": "wrong", "csrf_token": token}, cookie, ORIGIN)
    check("V01 SQL injection blocked", injected["status"] == 403, "CRS block. Direct origin tests also verify parameterised queries and safe login input.")
    xss = call("/comment", "POST", {"ticket_id": "1001", "body": '<svg onload="this.outerHTML=\'<p>XSS executed</p>\'"></svg>', "csrf_token": token}, cookie, ORIGIN)
    check("V02 XSS blocked", xss["status"] == 403, "CRS block. Direct origin tests separately verify output encoding.")
    private = call("/ticket?id=1002", cookie=cookie)
    check("V03 ticket ownership enforced", private["status"] == 403 and "payroll adjustment" not in private["body"], "Alice cannot read Bob's ticket.")
    forged = call("/admin", cookie="user_id=1")
    admin = call("/admin", cookie=cookie)
    check("V04 session forgery rejected", forged["status"] == 401 and admin["status"] == 403, "Unsigned v1 identity cookie is ignored; Alice lacks the admin role.")
    before = call("/account", cookie=cookie)
    original_email = re.search(r'name="email"[^>]*value="([^"]+)"', before["body"])[1]
    csrf = call("/account/email", "POST", {"email": "alice.updated@example.test"}, cookie, "http://127.0.0.1:8091")
    account = call("/account", cookie=cookie)
    check("V05 forged account update rejected", csrf["status"] == 403 and 'value="' + original_email + '"' in account["body"], "Cross-origin tokenless request cannot change Alice's email.")
    traversal = call("/download?" + urlencode({"file": "../private/legacy-config.txt"}), cookie=cookie)
    check("V06 traversal rejected", traversal["status"] in {403, 404} and "DB_PASSWORD" not in traversal["body"], "Edge rules plus a fixed-file allowlist at the origin.")
    debug = call("/debug")
    headers = {key.lower(): value for key, value in debug["headers"].items()}
    required = ["content-security-policy", "x-frame-options", "x-content-type-options", "strict-transport-security", "referrer-policy"]
    check("V07 diagnostics removed and headers enabled", debug["status"] == 404 and all(x in headers for x in required) and "password" not in debug["body"].lower(), "Secure headers are also present on error responses.")
    good = call("/comment", "POST", {"ticket_id": "1001", "body": "Verified secure workflow.", "csrf_token": token}, cookie, ORIGIN)
    own = call("/ticket?id=1001", cookie=cookie)
    handbook = call("/download?file=employee-handbook.txt", cookie=cookie)
    check("Legitimate use remains available", good["status"] == 303 and "Verified secure workflow." in own["body"] and handbook["status"] == 200, "Normal comment and handbook download pass the WAF and app.")
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: call("/reports/export", cookie=cookie, capture=False), range(40)))
    elapsed = time.perf_counter() - started
    statuses = dict(Counter(str(r["status"]) for r in results))
    latency = sorted(r["latency_ms"] for r in results)
    load = {"requests": 40, "workers": 4, "elapsed_seconds": round(elapsed, 3),
            "status_counts": statuses, "completed_responses_rps": round(40/elapsed, 2),
            "median_latency_ms": round(statistics.median(latency), 2), "p95_latency_ms": latency[37],
            "limitation": "Same request count and concurrency as v1; includes TLS and rejected requests. Throughput is not accepted report throughput or proof of DDoS resistance."}
    check("V08 expensive requests throttled", statuses.get("429", 0) > 0 and statuses.get("200", 0) <= 6 and set(statuses) <= {"200", "429"}, json.dumps(load))
    check("Edge errors disable caching", injected["headers"].get("Cache-Control") == "no-store" and all(r["headers"].get("Cache-Control") == "no-store" for r in results), "WAF blocks and gateway rate-limit responses include Cache-Control: no-store.")
    logout = call("/logout", "POST", {"csrf_token": token}, cookie, ORIGIN)
    reused = call("/account", cookie=cookie)
    check("Logout invalidates session", logout["status"] == 303 and reused["status"] == 401, "Old cookie no longer authenticates after logout.")
    logs = subprocess.check_output(["docker", "compose", "logs", "--no-color", "waf", "gateway", "app"], cwd=ROOT).decode()
    # Keep only audit rule IDs/version and structured application/gateway events.
    ids = sorted(set(re.findall(r'\[id "(\d+)"\]', logs)))
    versions = sorted(set(re.findall(r'OWASP_CRS/[\d.]+', logs)))
    evidence = {"rule_ids": ids, "crs_versions": versions,
        "application_security_events": sorted(set(re.findall(r'"event": "([a-z_]+)"', logs))),
        "gateway_rejections": logs.count('"status":429')}
    check("Real WAF audit evidence", any(x.startswith("942") for x in ids) and any(x.startswith("941") for x in ids), json.dumps(evidence))
    summary = {"target": ORIGIN, "recorded_at_utc": timestamp, "checks": checks, "load_probe": load, "waf_evidence": evidence}
    (dest / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    (dest / "requests.json").write_text(json.dumps(records, indent=2) + "\n")
    md = ["# Hardened stack verification", "", "| Check | Result | Details |", "|---|---|---|"]
    md += [f'| {r["check"]} | {"PASS" if r["passed"] else "FAIL"} | {r["details"]} |' for r in checks]
    (dest / "summary.md").write_text("\n".join(md) + "\n")
    print("Evidence:", dest)
    if not all(r["passed"] for r in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
