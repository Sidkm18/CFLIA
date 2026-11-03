#!/usr/bin/env python3
"""V08-only, bounded localhost request-burst demonstration (stdlib only).

Run with v1, v2, or both. Targets, 40 requests and four workers are fixed.
Normal Alice sign-in is used; no other vulnerability payloads are sent.
No passwords, session cookies, CSRF tokens or response bodies are saved.
"""
import argparse
import concurrent.futures
import datetime
import http.client
import json
import re
import ssl
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
REQUESTS, WORKERS = 40, 4


class LocalPortal:
    def __init__(self, version):
        self.version = version
        self.cookie = None
        self.csrf = None
        self.context = None
        self.origin = "http://127.0.0.1:8080"
        if version == "v2":
            self.origin = "https://127.0.0.1:8443"
            self.context = ssl.create_default_context(cafile=str(ROOT / "v2/state/tls/ca.crt"))

    def request(self, path, method="GET", data=None, authenticated=True):
        headers = {}
        if authenticated and self.cookie:
            headers["Cookie"] = self.cookie
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Origin"] = self.origin
        if self.version == "v1":
            con = http.client.HTTPConnection("127.0.0.1", 8080, timeout=10)
        else:
            con = http.client.HTTPSConnection("127.0.0.1", 8443, timeout=10, context=self.context)
        try:
            con.request(method, path, urlencode(data) if data is not None else None, headers)
            response = con.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode(errors="replace")
        finally:
            con.close()

    @staticmethod
    def token(body):
        match = re.search(r'name="csrf_token" value="([^"]+)"', body)
        if not match:
            raise RuntimeError("V2 sign-in form/session is unavailable. Wait 60 seconds and retry.")
        return match[1]

    def sign_in(self):
        if self.version == "v1":
            data = {"username": "alice", "password": "alice123"}
        else:
            status, headers, body = self.request("/login", authenticated=False)
            if status != 200:
                raise RuntimeError(f"V2 sign-in page returned HTTP {status}; wait 60 seconds and retry.")
            self.cookie = headers.get("Set-Cookie", "").split(";", 1)[0]
            password = json.loads((ROOT / "v2/state/credentials.json").read_text())["alice"]
            data = {"username": "alice", "password": password, "csrf_token": self.token(body)}
        status, headers, _ = self.request("/login", "POST", data)
        if status != 303 or not headers.get("Set-Cookie"):
            raise RuntimeError(f"Normal Alice sign-in failed (HTTP {status}). Check the local stack and credentials; wait 60 seconds if throttled.")
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        if self.version == "v2":
            status, _, body = self.request("/")
            if status != 200:
                raise RuntimeError(f"Authenticated V2 page returned HTTP {status}.")
            self.csrf = self.token(body)

    def sign_out(self):
        if not self.cookie:
            return
        if self.version == "v1":
            self.request("/logout")
        elif self.csrf:
            self.request("/logout", "POST", {"csrf_token": self.csrf})
        self.cookie = None
        self.csrf = None


def demonstrate(version):
    portal = LocalPortal(version)
    label = "BEFORE: V1 vulnerable" if version == "v1" else "AFTER: V2 hardened"
    print(f"\n{'=' * 62}\n{label}\nTarget: {portal.origin}/reports/export", flush=True)
    print(f"Exactly {REQUESTS} requests | {WORKERS} concurrent workers | Alice", flush=True)
    records = []
    try:
        portal.sign_in()
        print("Normal sign-in complete. Starting the report-request batch...\n", flush=True)

        def one(number):
            start = time.perf_counter()
            try:
                status, _, _ = portal.request("/reports/export")
                error = None
            except (OSError, http.client.HTTPException):
                status, error = 0, "connection_or_protocol_error"
            return {"request": number, "status": status,
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2), "error": error}

        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(one, number) for number in range(1, REQUESTS + 1)]
            for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
                item = future.result()
                records.append(item)
                outcome = {200: "ACCEPTED", 429: "RATE LIMITED"}.get(item["status"], "UNEXPECTED / ERROR")
                print(f"{completed:02}/{REQUESTS}  request #{item['request']:02}  HTTP {item['status']:3}  {outcome}", flush=True)
        elapsed = time.perf_counter() - started
    finally:
        try:
            portal.sign_out()
        except (OSError, http.client.HTTPException):
            print("Session cleanup unavailable; the normal session will expire.", flush=True)
    counts = Counter(item["status"] for item in records)
    other = sum(count for status, count in counts.items() if status not in (200, 429))
    print(f"\nRESULT - {label}", flush=True)
    print(f"Accepted (HTTP 200):      {counts[200]:2}/{REQUESTS}", flush=True)
    print(f"Rate limited (HTTP 429):  {counts[429]:2}/{REQUESTS}", flush=True)
    print(f"Other/errors:            {other:2}/{REQUESTS}", flush=True)
    print(f"Batch elapsed: {elapsed:.2f}s", flush=True)
    expected = other == 0 and (counts[200] == REQUESTS if version == "v1" else counts[429] > 0 and counts[200] <= 6)
    if version == "v1":
        print("No admission limit observed in this batch." if expected else "Unexpected outcome: inspect the local V1 stack.", flush=True)
    else:
        print("Request throttling demonstrated." if expected else "Expected throttling was not established; inspect the local V2 stack.", flush=True)
        if counts[200] == 0 and counts[429]:
            print("The quota may already be warm. Wait at least 60 seconds before repeating.", flush=True)
    return {"version": version, "target": portal.origin + "/reports/export", "requests": REQUESTS,
            "workers": WORKERS, "status_counts": {str(k): v for k, v in sorted(counts.items())},
            "elapsed_seconds": round(elapsed, 3), "median_latency_ms": round(statistics.median(r["latency_ms"] for r in records), 2),
            "expected_outcome_observed": expected, "responses": sorted(records, key=lambda r: r["request"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("v1", "v2", "both"), nargs="?", default="both")
    args = parser.parse_args()
    print("V08 ONLY - LOCAL REQUEST BURST / RATE LIMITING DEMO", flush=True)
    print("This bounded single-client test is not a distributed DDoS simulation.", flush=True)
    results = []
    for version in (("v1", "v2") if args.stage == "both" else (args.stage,)):
        results.append(demonstrate(version))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = ROOT / "output/v08-demo" / stamp
    dest.mkdir(parents=True)
    (dest / "results.json").write_text(json.dumps({"captured_at_utc": stamp, "scope": "V08 only; fixed localhost targets", "results": results,
        "limitation": "One client, 40 requests, four workers. Shows admission control, not service denial or volumetric DDoS protection."}, indent=2) + "\n")
    print(f"\nEvidence: {dest / 'results.json'}", flush=True)
    return not all(result["expected_outcome_observed"] for result in results)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, http.client.HTTPException, RuntimeError, KeyError, ValueError) as error:
        # Do not print raw exception messages from credentials/config parsing.
        message = str(error) if isinstance(error, RuntimeError) else "Local stack, certificate or credential file unavailable. Check the existing Docker setup."
        print("Demo stopped: " + message, file=sys.stderr)
        sys.exit(1)
