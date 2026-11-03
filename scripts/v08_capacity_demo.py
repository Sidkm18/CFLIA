#!/usr/bin/env python3
"""Isolated V08 capacity demo: up, traffic v1/v2, verify, down.

Only fixed loopback ports 18080/18443 are traffic targets. Four workers,
one request per worker per second at most, 360 requests and 90 seconds maximum.
Default traffic duration is 60 seconds. Ctrl+C drains in-flight work and exits.
No third-party packages; no credentials, cookies or response bodies in evidence.
"""
import argparse
import datetime
import hashlib
import http.client
import json
import re
import signal
import ssl
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "demos/v08-capacity/compose.yaml"
ORIGINS = {"v1": "http://127.0.0.1:18080", "v2": "https://127.0.0.1:18443"}
WORKERS, MAX_REQUESTS = 4, 360
SOURCE_FILES = ("app/server.py", "v2/app/server.py", "compose.yaml", "v2/compose.yaml", "v2/infra/gateway.conf")


class Portal:
    def __init__(self, version):
        self.version = version
        self.cookie = self.csrf = None
        self.context = ssl.create_default_context(cafile=str(ROOT / "v2/state/tls/ca.crt")) if version == "v2" else None

    def request(self, path, method="GET", data=None):
        if path not in {"/", "/login", "/logout", "/health", "/tickets", "/reports/export"}:
            raise ValueError("Only fixed lab routes are permitted")
        headers = {"X-V08-Lab-Client": "bounded-local-capacity-demo"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if data is not None:
            headers.update({"Content-Type": "application/x-www-form-urlencoded", "Origin": ORIGINS[self.version]})
        if self.version == "v1":
            con = http.client.HTTPConnection("127.0.0.1", 18080, timeout=6)
        else:
            con = http.client.HTTPSConnection("127.0.0.1", 18443, context=self.context, timeout=6)
        start = time.perf_counter()
        try:
            con.request(method, path, urlencode(data) if data is not None else None, headers)
            response = con.getresponse()
            body = response.read().decode(errors="replace")
            return response.status, dict(response.getheaders()), body, round((time.perf_counter() - start) * 1000, 2)
        finally:
            con.close()

    @staticmethod
    def token(body):
        found = re.search(r'name="csrf_token" value="([^"]+)"', body)
        if not found:
            raise RuntimeError("V2 form unavailable; allow its quota to cool down and retry")
        return found[1]

    def sign_in(self):
        data = {"username": "alice", "password": "alice123"}
        if self.version == "v2":
            status, headers, body, _ = self.request("/login")
            if status != 200:
                raise RuntimeError("V2 login is not ready or is limited; wait 70 seconds and retry")
            self.cookie = headers.get("Set-Cookie", "").split(";", 1)[0]
            values = json.loads((ROOT / "v2/state/credentials.json").read_text())
            data.update(password=values["alice"], csrf_token=self.token(body))
        status, headers, _, _ = self.request("/login", "POST", data)
        if status != 303 or not headers.get("Set-Cookie"):
            raise RuntimeError("Normal demo sign-in failed; check the demo stack and wait 70 seconds if limited")
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        if self.version == "v2":
            status, _, body, _ = self.request("/")
            if status != 200:
                raise RuntimeError("Authenticated V2 page unavailable")
            self.csrf = self.token(body)

    def sign_out(self):
        try:
            if self.cookie:
                self.request("/logout", "POST", {"csrf_token": self.csrf}) if self.version == "v2" else self.request("/logout")
        except (OSError, http.client.HTTPException):
            pass
        self.cookie = self.csrf = None


class Traffic:
    def __init__(self, portal, seconds):
        self.portal, self.seconds = portal, seconds
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.records, self.issued, self.threads = [], 0, []

    def start(self):
        self.started = time.monotonic()
        self.deadline = self.started + self.seconds
        self.threads = [threading.Thread(target=self.worker, name=f"v08-{i}") for i in range(WORKERS)]
        for thread in self.threads:
            thread.start()

    def worker(self):
        while not self.stop.is_set() and time.monotonic() < self.deadline:
            started = time.monotonic()
            with self.lock:
                if self.issued >= MAX_REQUESTS:
                    return
                self.issued += 1
                number = self.issued
            try:
                status, _, _, latency = self.portal.request("/reports/export")
                error = None
            except (OSError, http.client.HTTPException):
                status, latency, error = 0, round((time.monotonic() - started) * 1000, 2), "connection_or_protocol_error"
            with self.lock:
                self.records.append({"request": number, "status": status, "latency_ms": latency, "error": error})
            self.stop.wait(max(0, 1.0 - (time.monotonic() - started)))

    def counts(self):
        with self.lock:
            return Counter(record["status"] for record in self.records)

    def finish(self):
        self.stop.set()
        for thread in self.threads:
            thread.join()
        return {"version": self.portal.version, "target": ORIGINS[self.portal.version] + "/reports/export",
                "workers": WORKERS, "max_requests": MAX_REQUESTS,
                "max_requests_per_second": 4, "requested_duration_seconds": self.seconds,
                "elapsed_seconds": round(time.monotonic() - self.started, 2),
                "status_counts": {str(k): v for k, v in sorted(self.counts().items())},
                "responses": sorted(self.records, key=lambda r: r["request"])}


def save(kind, data):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = ROOT / "output/v08-capacity" / stamp
    directory.mkdir(parents=True)
    path = directory / (kind + ".json")
    path.write_text(json.dumps({"captured_at_utc": stamp, "scope": "Isolated local two-worker capacity lab; not a DDoS-resistance claim", **data}, indent=2) + "\n")
    print(f"Evidence: {path}", flush=True)


def compose(*args):
    subprocess.run(["docker", "compose", "-f", str(COMPOSE), *args], cwd=ROOT, check=True)


def up():
    required = [ROOT / "v2/.env", ROOT / "v2/state/credentials.json", ROOT / "v2/state/tls/ca.crt", ROOT / "v2/state/tls/server.crt"]
    if not all(path.exists() for path in required):
        subprocess.run([sys.executable, str(ROOT / "v2/scripts/setup.py")], check=True, cwd=ROOT)
    compose("config", "--quiet")
    compose("up", "-d", "--build", "--wait", "--wait-timeout", "120")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if all(Portal(version).request("/health")[0] == 200 for version in ORIGINS):
                print("\nV08 capacity lab ready. Original stacks and databases were not changed.")
                for version, origin in ORIGINS.items():
                    print(f"{version.upper()}: {origin}")
                print("Use a separate/private browser window to avoid cookies shared with other localhost ports.")
                print("V1: alice / alice123. V2: alice with the password in v2/state/credentials.json.")
                print("Guide: docs/V08_CAPACITY_DEMO.md")
                return
        except (OSError, http.client.HTTPException):
            pass
        time.sleep(1)
    raise RuntimeError("Containers started but public lab health checks failed; inspect the isolated Compose logs")


def traffic(version, seconds):
    portal = Portal(version)
    portal.sign_in()
    run = Traffic(portal, seconds)
    print(f"\n{version.upper()} LOCAL CAPACITY DEMO - {ORIGINS[version]}", flush=True)
    print(f"4 workers | at most 4 requests/second | at most {seconds}s / {MAX_REQUESTS} requests", flush=True)
    print("Ctrl+C stops new requests; in-flight jobs finish within about six seconds.", flush=True)
    run.start()

    def stop(*_):
        if not run.stop.is_set():
            print("\nStopping traffic; draining in-flight requests...", flush=True)
            run.stop.set()

    old_handlers = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        while not run.stop.wait(1) and time.monotonic() < run.deadline and any(t.is_alive() for t in run.threads):
            counts = run.counts()
            print(f"{time.monotonic()-run.started:4.0f}s | HTTP 200: {counts[200]:3} | 429 limited: {counts[429]:3} | 503 busy: {counts[503]:3} | errors: {counts[0]}", flush=True)
    finally:
        result = run.finish()
        portal.sign_out()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    print("Traffic stopped. Refresh the browser now.", flush=True)
    save("traffic", result)


def verify():
    before = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_FILES}
    checks, runs = [], []

    def check(name, condition, **details):
        checks.append({"check": name, "passed": bool(condition), **details})
        print(("PASS " if condition else "FAIL ") + name, flush=True)

    for version in ("v1", "v2"):
        sender, visitor = Portal(version), Portal(version)
        sender.sign_in()
        visitor.sign_in()
        run = Traffic(sender, 15)
        try:
            status, _, _, latency = visitor.request("/")
            check(f"{version.upper()} normal page before traffic", status == 200, status=status, latency_ms=latency)
            run.start()
            # Sample actual normal routes while concurrent report jobs run.
            time.sleep(1)
            observations = []
            for path in ("/", "/tickets", "/"):
                status, _, _, latency = visitor.request(path)
                observations.append({"path": path, "status": status, "latency_ms": latency})
                time.sleep(1)
            if version == "v1":
                check("V1 normal browsing receives real capacity refusals", all(r["status"] == 503 for r in observations), requests=observations)
            else:
                check("V2 normal browsing remains available during report traffic", all(r["status"] == 200 for r in observations), requests=observations)
            result = run.finish()
            runs.append(result)
            counts = result["status_counts"]
            if version == "v1":
                check("V1 report jobs occupied capacity", int(counts.get("200", 0)) >= 2 and int(counts.get("503", 0)) > 0, counts=counts)
            else:
                check("V2 rejects excess report requests", int(counts.get("429", 0)) > 0 and int(counts.get("200", 0)) <= 6, counts=counts)
            check(f"{version.upper()} no traffic transport errors", not int(counts.get("0", 0)), counts=counts)
            status, _, _, latency = visitor.request("/")
            check(f"{version.upper()} normal page after traffic stops", status == 200, status=status, latency_ms=latency)
        finally:
            if run.threads:
                run.finish()
            sender.sign_out()
            visitor.sign_out()
    check("Original apps and Compose configuration preserved", all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in before.items()))
    save("verification", {"checks": checks, "traffic": runs})
    return not all(item["passed"] for item in checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("up")
    commands.add_parser("down")
    commands.add_parser("verify")
    load = commands.add_parser("traffic")
    load.add_argument("version", choices=("v1", "v2"))
    load.add_argument("--seconds", type=int, choices=(15, 30, 60, 90), default=60)
    args = parser.parse_args()
    if args.command == "up":
        up()
    elif args.command == "down":
        compose("down")  # Retain dedicated volumes; never delete original data.
    elif args.command == "traffic":
        traffic(args.version, args.seconds)
    else:
        return verify()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        print("Demo stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
    except (OSError, http.client.HTTPException, subprocess.CalledProcessError, ValueError, KeyError):
        print("Demo stopped: check Docker, demo readiness, local TLS files and credentials. Wait 70 seconds if a quota is warm. See docs/V08_CAPACITY_DEMO.md. No secrets were recorded.", file=sys.stderr)
        sys.exit(1)
