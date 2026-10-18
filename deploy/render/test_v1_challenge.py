"""Bounded HTTP regression checks; uses an isolated temporary database."""
import html
import http.client
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))
import server
import challenge


class ChallengeHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="legacydesk-challenge-")
        server.STATE = Path(cls.temp.name)
        server.DB = server.STATE / "test.sqlite3"
        server.LOG = server.STATE / "requests.jsonl"
        server.seed()
        server.CHALLENGE_ENABLED = True
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, data=None, cookie=None):
        con = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        headers = {"Cookie": cookie} if cookie else {}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        con.request("POST" if data is not None else "GET", path,
                    urlencode(data, doseq=True) if data is not None else None, headers)
        response = con.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode()
        con.close()
        return result

    def answers(self, values=None):
        return {f"passphrase_{i}": value for i, value in
                enumerate(values or challenge.PASSPHRASES.values(), 1)}

    def test_public_pages_do_not_disclose_answers_or_flag(self):
        for path, cookie in [("/login", None), ("/challenge", None), ("/", "user_id=2"),
                             ("/tickets", "user_id=2"), ("/ticket?id=1001", "user_id=2"),
                             ("/knowledge", "user_id=2"), ("/static/style.css", None),
                             ("/download?file=employee-handbook.txt", None)]:
            with self.subTest(path=path):
                status, _, body = self.request(path, cookie=cookie)
                self.assertEqual(status, 200)
                for value in [*challenge.PASSPHRASES.values(), challenge.FLAG]:
                    self.assertNotIn(value, body)

    def test_each_exploit_surface_reveals_only_its_own_passphrase(self):
        routes = [("/ticket?id=1002", "user_id=2", "ticket"),
                  ("/admin", "user_id=1", "admin"),
                  ("/download?file=../private/legacy-config.txt", None, "traversal"),
                  ("/debug", None, "debug")]
        for path, cookie, key in routes:
            with self.subTest(key=key):
                status, _, body = self.request(path, cookie=cookie)
                self.assertEqual(status, 200)
                self.assertIn(challenge.PASSPHRASES[key], body)
                self.assertNotIn(challenge.FLAG, body)
                for other, value in challenge.PASSPHRASES.items():
                    if other != key:
                        self.assertNotIn(value, body)

    def test_employee_cannot_open_admin_without_forged_identity(self):
        status, _, body = self.request("/admin", cookie="user_id=2")
        self.assertEqual(status, 403)
        self.assertNotIn(challenge.PASSPHRASES["admin"], body)

    def test_missing_wrong_duplicate_and_polluted_answers_do_not_unlock(self):
        valid = self.answers()
        invalid = [{}, {**valid, "passphrase_4": "wrong"},
                   {**valid, "passphrase_4": valid["passphrase_1"]},
                   {**valid, "passphrase_1": [valid["passphrase_1"], "extra"]}]
        for data in invalid:
            with self.subTest(data=data):
                status, headers, body = self.request("/challenge", data)
                self.assertEqual(status, 200)
                self.assertIn("vault is still locked", body)
                self.assertNotIn(challenge.FLAG, body)
                self.assertEqual(headers["Cache-Control"], "no-store")

    def test_all_four_in_any_order_unlock_without_persisting_completion(self):
        values = [" " + value.lower() + " " for value in reversed(list(challenge.PASSPHRASES.values()))]
        status, headers, body = self.request("/challenge", self.answers(values))
        self.assertEqual(status, 200)
        self.assertIn(challenge.FLAG, body)
        self.assertIn("Flag unlocked", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn(challenge.FLAG, self.request("/challenge")[2])
        self.assertNotIn(challenge.FLAG, self.request("/challenge?unlocked=1")[2])

    def test_reflected_submission_is_escaped(self):
        payload = '<img src=x onerror="alert(1)">'
        _, _, body = self.request("/challenge", {"passphrase_1": payload})
        self.assertNotIn(payload, body)
        self.assertIn(html.escape(payload, quote=True), body)

    def test_disabling_challenge_preserves_original_surfaces(self):
        server.CHALLENGE_ENABLED = False
        try:
            for path, key in [("/debug", "debug"), ("/admin", "admin"),
                              ("/ticket?id=1002", "ticket"),
                              ("/download?file=../private/legacy-config.txt", "traversal")]:
                self.assertNotIn(challenge.PASSPHRASES[key], self.request(path, cookie="user_id=1")[2])
            self.assertEqual(self.request("/challenge", cookie="user_id=2")[0], 404)
            self.assertEqual(self.request("/challenge", {}, cookie="user_id=2")[0], 404)
            self.assertNotIn("Unlock flag", self.request("/login")[2])
        finally:
            server.CHALLENGE_ENABLED = True


if __name__ == "__main__":
    unittest.main()
