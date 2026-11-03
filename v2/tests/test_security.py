import concurrent.futures
import hashlib
import html
import re
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from app.server import COOKIE, create_app

ORIGIN = "https://127.0.0.1:8443"
PASSWORDS = {name: "Test-Only-" + name + "-Password-For-Unit-Tests-926!" for name in ("admin", "alice", "bob")}
XSS = '<svg onload="this.outerHTML=\'<p>XSS executed</p>\'"></svg>'


class SecurityTests(unittest.TestCase):
    """Exercise root-cause fixes directly, without the gateway or WAF."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({"STATE": Path(self.temp.name), "TESTING": True, "BOOTSTRAP_PASSWORDS": PASSWORDS})
        self.app.logger.disabled = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def get(self, path, client=None):
        return (client or self.client).get(path, base_url=ORIGIN)

    def csrf(self, path="/account", client=None):
        response = self.get(path, client)
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match, response.status_code)
        return match[1]

    def post(self, path, data, token=None, origin=ORIGIN, client=None):
        body = dict(data)
        if token is not None:
            body["csrf_token"] = token
        return (client or self.client).post(path, data=body, base_url=ORIGIN, headers={"Origin": origin})

    def login(self, name="alice", client=None):
        c = client or self.client
        token = self.csrf("/login", c)
        response = self.post("/login", {"username": name, "password": PASSWORDS[name]}, token, client=c)
        self.assertEqual(response.status_code, 303)
        return c

    def sql(self, statement, args=()):
        with sqlite3.connect(Path(self.temp.name) / "portal.sqlite3") as con:
            cur = con.execute(statement, args)
            return cur.fetchall()

    def test_legitimate_employee_workflows(self):
        self.login()
        token = self.csrf()
        result = self.post("/tickets", {"subject": "Working request", "body": "Normal request details", "category": "Software"}, token)
        self.assertEqual(result.status_code, 303)
        ident = result.location.split("=")[-1]
        result = self.post("/comment", {"ticket_id": ident, "body": "Normal comment"}, token)
        self.assertEqual(result.status_code, 303)
        self.assertIn("Normal comment", self.get("/ticket?id=" + ident).get_data(as_text=True))
        self.assertEqual(self.post("/account/email", {"email": "alice.updated@example.test"}, token).status_code, 303)
        with self.get("/download?file=employee-handbook.txt") as download:
            self.assertEqual(download.status_code, 200)

    def test_sql_injection_does_not_authenticate(self):
        token = self.csrf("/login")
        result = self.post("/login", {"username": "' OR 1=1 -- ", "password": "wrong"}, token)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.get("/admin").status_code, 401)
        self.assertNotIn("sqlite", result.get_data(as_text=True).lower())

    def test_search_treats_sql_and_wildcards_as_data(self):
        self.login()
        for value in ["' OR 1=1 -- ", "'", "%", "_"]:
            result = self.client.get("/tickets", query_string={"q": value}, base_url=ORIGIN)
            self.assertEqual(result.status_code, 200)
            self.assertNotIn("Confidential payroll correction", result.get_data(as_text=True))
            self.assertIn("No matching tickets", result.get_data(as_text=True))

    def test_stored_xss_is_output_encoded(self):
        self.login()
        result = self.post("/comment", {"ticket_id": "1001", "body": XSS}, self.csrf())
        self.assertEqual(result.status_code, 303)
        page = self.get("/ticket?id=1001").get_data(as_text=True)
        self.assertIn(html.escape(XSS, quote=True), page)
        self.assertNotIn(XSS, page)
        self.assertNotIn("<svg", page)
        self.assertIn("default-src 'none'", self.get("/").headers["Content-Security-Policy"])

    def test_ticket_permissions_protect_reads_and_writes(self):
        self.login()
        self.assertEqual(self.get("/ticket?id=1002").status_code, 403)
        token = self.csrf()
        self.assertEqual(self.post("/comment", {"ticket_id": "1002", "body": "Unauthorised comment"}, token).status_code, 403)
        self.assertEqual(self.sql("SELECT count(*) FROM comments WHERE ticket_id=1002")[0][0], 0)
        bob = self.login("bob", self.app.test_client())
        self.assertEqual(self.get("/ticket?id=1002", bob).status_code, 200)
        admin = self.login("admin", self.app.test_client())
        self.assertEqual(self.get("/ticket?id=1002", admin).status_code, 200)
        self.assertEqual(self.get("/admin", admin).status_code, 200)

    def test_unsigned_and_forged_sessions_are_rejected(self):
        self.client.set_cookie("user_id", "1", domain="127.0.0.1")
        self.assertEqual(self.get("/admin").status_code, 401)
        self.client.set_cookie(COOKIE, "A" * 43, domain="127.0.0.1")
        self.assertEqual(self.get("/admin").status_code, 401)
        self.login()
        self.assertEqual(self.get("/admin").status_code, 403)

    def test_password_hashes_and_old_password_rejection(self):
        hashes = [x[0] for x in self.sql("SELECT password_hash FROM users")]
        self.assertEqual(len(set(hashes)), 3)
        self.assertTrue(all(x.startswith("pbkdf2:sha256:600000$") for x in hashes))
        token = self.csrf("/login")
        self.assertEqual(self.post("/login", {"username": "alice", "password": "alice123"}, token).status_code, 401)

    def test_session_rotation_secure_cookie_and_logout_invalidation(self):
        token = self.csrf("/login")
        old = self.client.get_cookie(COOKIE, domain="127.0.0.1").value
        result = self.post("/login", {"username": "alice", "password": PASSWORDS["alice"]}, token)
        self.assertEqual(result.status_code, 303)
        current = self.client.get_cookie(COOKIE, domain="127.0.0.1").value
        self.assertNotEqual(current, old)
        cookie = result.headers["Set-Cookie"]
        for attr in ["Secure", "HttpOnly", "SameSite=Strict", "Path=/"]:
            self.assertIn(attr, cookie)
        self.assertEqual(self.sql("SELECT count(*) FROM sessions WHERE token_hash=?", (hashlib.sha256(old.encode()).hexdigest(),))[0][0], 0)
        token = self.csrf()
        self.assertEqual(self.get("/logout").status_code, 405)
        self.assertEqual(self.post("/logout", {}, token).status_code, 303)
        self.client.set_cookie(COOKIE, current, domain="127.0.0.1")
        self.assertEqual(self.get("/account").status_code, 401)

    def test_expired_and_idle_sessions_cannot_be_reused(self):
        for column in ["expires", "last_seen"]:
            self.login()
            self.sql("UPDATE sessions SET " + column + "=? WHERE user_id=2", (time.time() - 7200,))
            self.assertEqual(self.get("/account").status_code, 401)

    def test_abandoned_login_sessions_are_collected_and_bounded(self):
        self.app.config["MAX_ANONYMOUS_SESSIONS"] = 5
        now = time.time()
        for index in range(8):
            self.sql("INSERT INTO sessions VALUES(?,?,?,?,?,?)", (f"anonymous-{index}", None, "csrf", now-index, now+900, now))
        for token, expires, seen in [("expired", now-1, now), ("idle", now+900, now-901)]:
            self.sql("INSERT INTO sessions VALUES(?,?,?,?,?,?)", (token, None, "csrf", now, expires, seen))
        self.sql("INSERT INTO sessions VALUES(?,?,?,?,?,?)", ("authenticated", 2, "csrf", now, now+3600, now))
        self.assertEqual(self.get("/login").status_code, 200)
        self.assertEqual(self.sql("SELECT count(*) FROM sessions WHERE user_id IS NULL")[0][0], 5)
        self.assertEqual(self.sql("SELECT count(*) FROM sessions WHERE token_hash IN ('expired','idle')")[0][0], 0)
        self.assertEqual(self.sql("SELECT count(*) FROM sessions WHERE token_hash='authenticated'")[0][0], 1)

    def test_csrf_token_and_origin_are_both_required(self):
        self.login()
        token = self.csrf()
        data = {"email": "forged@example.test"}
        self.assertEqual(self.post("/account/email", data).status_code, 403)
        self.assertEqual(self.post("/account/email", data, token, "http://127.0.0.1:8091").status_code, 403)
        self.assertEqual(self.post("/account/email", data, "wrong").status_code, 403)
        self.assertEqual(self.sql("SELECT email FROM users WHERE id=2")[0][0], "alice@example.test")
        self.assertEqual(self.post("/account/email", data, token).status_code, 303)

    def test_login_csrf_is_rejected(self):
        data = {"username": "alice", "password": PASSWORDS["alice"]}
        self.assertEqual(self.post("/login", data).status_code, 403)
        token = self.csrf("/login")
        self.assertEqual(self.post("/login", data, token, "http://127.0.0.1:8091").status_code, 403)

    def test_download_allowlist_rejects_traversal(self):
        self.login()
        for value in ["../private/legacy-config.txt", "../../state/portal.sqlite3", "/etc/passwd", "%2e%2e%2fprivate%2flegacy-config.txt", "employee-handbook.txt/../private"]:
            response = self.client.get("/download", query_string={"file": value}, base_url=ORIGIN)
            self.assertEqual(response.status_code, 404, value)
        result = self.get("/download?file=employee-handbook.txt")
        self.assertEqual(result.status_code, 200)
        self.assertIn("attachment", result.headers["Content-Disposition"])
        result.close()

    def test_debug_removed_and_secure_headers_on_errors(self):
        for path, code in [("/debug", 404), ("/account", 401), ("/missing", 404)]:
            result = self.get(path)
            self.assertEqual(result.status_code, code)
            for header in ["Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Strict-Transport-Security"]:
                self.assertIn(header, result.headers)
            self.assertEqual(result.headers["Cache-Control"], "no-store")
            self.assertNotIn("password", result.get_data(as_text=True).lower())

    def test_reports_are_scoped_cached_and_limited(self):
        self.login()
        results = [self.get("/reports/export") for _ in range(40)]
        self.assertEqual(sum(r.status_code == 200 for r in results), 6)
        self.assertEqual(sum(r.status_code == 429 for r in results), 34)
        self.assertTrue(all(r.json == {"tickets": 2} for r in results if r.status_code == 200))
        self.assertEqual(len(self.sql("SELECT * FROM report_cache WHERE user_id=2")), 1)

    def test_concurrent_report_quota_is_atomic(self):
        self.login()
        cookie = self.client.get_cookie(COOKIE, domain="127.0.0.1").value
        def run(_):
            client = self.app.test_client()
            client.set_cookie(COOKIE, cookie, domain="127.0.0.1")
            return self.get("/reports/export", client).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(run, range(40)))
        self.assertEqual(codes.count(200), 6)
        self.assertEqual(codes.count(429), 34)

    def test_login_attempts_are_throttled(self):
        token = self.csrf("/login")
        codes = [self.post("/login", {"username": "alice", "password": "incorrect"}, token).status_code for _ in range(10)]
        self.assertEqual(codes.count(401), 8)
        self.assertEqual(codes.count(429), 2)

    def test_input_bounds_and_duplicate_fields(self):
        self.login()
        token = self.csrf()
        self.assertEqual(self.post("/account/email", {"email": "not-an-email"}, token).status_code, 400)
        self.assertEqual(self.post("/tickets", {"subject": "A" * 161, "body": "body", "category": "Other"}, token).status_code, 400)
        self.assertEqual(self.post("/comment", {"ticket_id": "1001", "body": "A" * 2001}, token).status_code, 400)
        from werkzeug.datastructures import MultiDict
        result = self.client.post("/account/email", data=MultiDict([("email", "a@example.test"), ("email", "b@example.test"), ("csrf_token", token)]), base_url=ORIGIN, headers={"Origin": ORIGIN})
        self.assertEqual(result.status_code, 400)
        result = self.client.post("/comment", data={"body": "A" * 20000}, base_url=ORIGIN, headers={"Origin": ORIGIN})
        self.assertEqual(result.status_code, 413)

    def test_invalid_hosts_are_rejected(self):
        result = self.client.get("/", base_url="https://untrusted.example")
        self.assertEqual(result.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
