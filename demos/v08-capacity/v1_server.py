"""Opt-in capacity model; imports the original V1 app without editing it.

Two real worker slots and a four-second report job make contention observable
at a few localhost requests per second. A full server returns HTTP 503 based
on actual occupied slots, never on a demo on/off flag. Demo databases are
separate Docker volumes. This is a capacity experiment, not production proof.
"""
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

sys.path.insert(0, "/lab/app")
import server as original

BUSY = b"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Service temporarily busy | LegacyDesk V08 lab</title>
<style>body{font:18px/1.6 system-ui;background:#f4f6f3;color:#193e32;margin:0}
main{max-width:680px;margin:12vh auto;padding:36px;background:white;border:1px solid #dae3db;border-radius:16px}
.tag{font-size:13px;letter-spacing:.08em;color:#7d5534}h1{font-size:38px;line-height:1.2}
code{background:#edf2eb;padding:4px 8px}a{color:#225b43}</style>
<main><p class="tag">LOCAL V08 CAPACITY LAB / V1</p><h1>Service temporarily busy</h1>
<p><code>HTTP 503</code></p><p>Both server worker slots are occupied by other requests.
Your page could not be served.</p><p>Stop the report traffic, wait up to five seconds,
then refresh this page.</p><p><small>Lab configuration: two shared workers;
each V1 report job takes about four seconds. This response reflects actual worker occupancy.</small></p></main></html>"""


class BusyHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(BUSY)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Retry-After", "5")
        self.send_header("X-V08-Lab", "two-worker-capacity-model")
        self.end_headers()
        self.wfile.write(BUSY)
        print('capacity_refused status=503 workers=2', flush=True)

    do_POST = do_GET


class DemoHandler(original.Handler):
    def get(self):
        if urlsplit(self.path).path == "/reports/export" and self.user():
            # The original job already waits 0.2 seconds. Only this lab adds
            # 3.8 seconds of occupied-worker time; no CPU/memory exhaustion.
            time.sleep(3.8)
        return super().get()

    def page(self, *args, **kwargs):
        page = super().page(*args, **kwargs)
        return page.replace("<main>", '<main><div class="notice">Local V08 capacity lab: 2 shared workers; 4-second V1 report jobs.</div>', 1)


class CapacityServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(2)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        # An idle browser preconnection must not hold a worker indefinitely.
        request.settimeout(2)
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(2)
                BusyHandler(request, client_address, self)
            except (OSError, TimeoutError):
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


if __name__ == "__main__":
    original.seed()
    print("V08 LOCAL LAB: two worker slots, four-second V1 report jobs", flush=True)
    CapacityServer(("0.0.0.0", 8000), DemoHandler).serve_forever()
