"""Intentionally vulnerable local training app.

Standard library only. Never contains real data. The download flaw is constrained
to fixtures so its demonstration cannot read the host filesystem.
"""
import argparse
import html
import json
import os
import sqlite3
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
STATE = ROOT.parent / "state"
DB = STATE / "legacydesk.sqlite3"
LOG = STATE / "requests.jsonl"
LOG_LOCK = threading.Lock()
FIXTURES = ROOT / "fixtures"


def connect():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def seed(reset=False):
    STATE.mkdir(exist_ok=True)
    if reset and DB.exists():
        DB.unlink()
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT,
          name TEXT, email TEXT, role TEXT);
        CREATE TABLE IF NOT EXISTS tickets (
          id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER,
          subject TEXT, body TEXT, category TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS comments (
          id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER,
          author TEXT, body TEXT);
        """)
        if con.execute("SELECT count(*) FROM users").fetchone()[0]:
            return
        con.executemany("INSERT INTO users VALUES (?,?,?,?,?,?)", [
            (1, "admin", "admin", "Portal Administrator", "admin@example.test", "admin"),
            (2, "alice", "alice123", "Alice Morgan", "alice@example.test", "employee"),
            (3, "bob", "bob123", "Bob Chen", "bob@example.test", "employee"),
        ])
        con.executemany("INSERT INTO tickets VALUES (?,?,?,?,?,?)", [
            (1001, 2, "Unable to connect to office VPN", "The VPN disconnects after sign-in. Please help restore access.", "Network", "Open"),
            (1002, 3, "Confidential payroll correction", "Bob's payroll adjustment is ₹12,500. Please review the correction before the next payroll cycle.", "Finance", "Pending"),
            (1003, 2, "Request for design software licence", "Please allocate a design software licence for the upcoming project.", "Software", "Pending"),
            (1004, 1, "Quarterly backup review", "Review the internal backup process and retention settings.", "Operations", "Closed"),
        ])
        con.execute("INSERT INTO comments(ticket_id,author,body) VALUES (1001, 'Service Desk', 'We have received your request. Please attach the connection details.')")


def esc(value):
    return html.escape(str(value), quote=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "LegacyDesk/1.0"

    def log_message(self, *_):
        pass

    def send(self, body, status=200, content_type="text/html; charset=utf-8", headers=None):
        raw = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        # V07: no CSP, frame protection, nosniff or secure transport headers.
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "method": self.command, "path": urlsplit(self.path).path,
                  "status": status, "latency_ms": round((time.perf_counter() - self.started) * 1000, 2)}
        with LOG_LOCK:
            with LOG.open("a") as f:
                f.write(json.dumps(record) + "\n")

    def redirect(self, path, cookie=None):
        headers = {"Location": path}
        if cookie:
            headers["Set-Cookie"] = cookie
        self.send("", 303, headers=headers)

    def user(self):
        # V04: unsigned identity cookie; forge user_id=1 to impersonate admin.
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            ident = cookie["user_id"].value if "user_id" in cookie else "0"
            with connect() as con:
                row = con.execute("SELECT id,username,name,email,role FROM users WHERE id=?", (ident,)).fetchone()
                return dict(row) if row else None
        except Exception:
            return None

    def page(self, title, content, active="overview", user=None):
        nav = [("overview", "/", "◫", "Overview"), ("tickets", "/tickets", "▤", "Support tickets"),
               ("knowledge", "/knowledge", "◇", "Knowledge base"), ("account", "/account", "◎", "My account")]
        links = "".join(f'<a class="nav-link {"active" if key == active else ""}" href="{url}"><span>{icon}</span>{label}</a>' for key, url, icon, label in nav)
        identity = f'<span class="avatar">{esc(user["name"][0])}</span><div><strong>{esc(user["name"])}</strong><small>{esc(user["role"].title())}</small></div>' if user else '<span class="avatar">?</span><div><strong>Guest visitor</strong><small>Employee portal</small></div>'
        return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · LegacyDesk</title><link rel="stylesheet" href="/static/style.css"></head><body>
        <aside class="sidebar"><a class="brand" href="/"><span class="brand-icon">L<span>↗</span></span><div>LegacyDesk<small>EMPLOYEE SERVICE PORTAL</small></div></a><div class="nav-label">WORKSPACE</div><nav>{links}</nav><div class="sidebar-bottom"><p class="muted">Need a hand?</p><a class="nav-link" href="/tickets#new"><span>＋</span>Contact the service desk</a></div></aside>
        <div class="workspace"><header><div class="breadcrumb">Workspace <span>/</span> {esc(title)}</div><div class="identity">{identity}{'<a class="quiet-link" href="/logout">Sign out</a>' if user else '<a class="quiet-link" href="/login">Sign in</a>'}</div></header><main>{content}</main><footer>LegacyDesk service portal <span>Employee support &amp; resources</span></footer></div></body></html>'''

    def do_GET(self):
        self.started = time.perf_counter()
        try:
            self.get()
        except Exception as error:
            # V07: verbose SQL/debug error returned to client.
            self.send(self.page("Application error", '<div class="page-heading"><p class="eyebrow">DEBUG OUTPUT</p><h1>Application error</h1></div><pre>' + esc(type(error).__name__ + ": " + str(error)) + '</pre>'), 500)

    def get(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        user = self.user()
        if path == "/health":
            return self.send(json.dumps({"status": "ok", "service": "LegacyDesk"}), content_type="application/json")
        if path == "/static/style.css":
            return self.send((ROOT / "static/style.css").read_bytes(), content_type="text/css")
        if path == "/favicon.ico":
            return self.send(b"", 204)
        if path == "/logout":
            return self.redirect("/login", "user_id=; Path=/; Max-Age=0")
        if path == "/login":
            error = '<div class="notice danger">Sign-in failed. Check your username and password.</div>' if query.get("error") else ""
            return self.send(self.page("Sign in", f'''<div class="login-layout"><section class="login-story"><p class="eyebrow">YOUR WORKDAY, CONNECTED</p><h1>A little support.<br>A better workday.</h1><p>One place for the tools, answers and support you need to keep things moving.</p><div class="story-card"><span>01 / SERVICE DESK</span><h3>Help is one ticket away.</h3><p>Raise a request, follow the conversation and get back to what matters.</p></div></section><section class="panel login-panel"><p class="eyebrow">EMPLOYEE ACCESS</p><h2>Welcome back</h2><p class="muted">Sign in to your workspace.</p>{error}<form method="post" action="/login"><label>Username<input name="username" autocomplete="username" required placeholder="Enter your username"></label><label>Password<input name="password" type="password" autocomplete="current-password" required placeholder="Enter your password"></label><button class="button full">Sign in <span>↗</span></button></form><p class="muted account-help">For account access, contact your service desk.</p></section></div>''', user=user))
        if path == "/debug":
            with connect() as con:
                users = [dict(x) for x in con.execute("SELECT * FROM users")]
            return self.send(json.dumps({"database": str(DB), "debug": True, "session": "unsigned user_id cookie", "users": users}, indent=2), content_type="application/json")
        if path == "/download":
            # V06: relative parent path escapes downloads. The fixtures root is
            # a lab containment boundary, not a fix for the download flaw.
            target = (FIXTURES / "downloads" / query.get("file", ["employee-handbook.txt"])[0]).resolve()
            if FIXTURES.resolve() not in target.parents or not target.is_file():
                return self.send("File not found", 404, "text/plain")
            return self.send(target.read_bytes(), content_type="text/plain; charset=utf-8")
        if not user:
            return self.redirect("/login")
        if path == "/":
            with connect() as con:
                tickets = [dict(x) for x in con.execute("SELECT * FROM tickets WHERE owner_id=? ORDER BY id DESC", (user["id"],))]
            opened = sum(t["status"] != "Closed" for t in tickets)
            content = f'''<div class="page-heading heading-row"><div><p class="eyebrow">YOUR WORKSPACE</p><h1>Hello, {esc(user['name'].split()[0])}.</h1><p>Here’s what’s happening with your support requests.</p></div><a class="button" href="/tickets#new">＋ Create a ticket</a></div>
            <div class="stats"><div class="stat"><span>Active requests</span><strong>{opened:02}</strong><small>Awaiting a resolution</small></div><div class="stat"><span>Total tickets</span><strong>{len(tickets):02}</strong><small>In your workspace</small></div><div class="stat"><span>Resolved tickets</span><strong>{len(tickets) - opened:02}</strong><small>Completed requests</small></div></div>
            <div class="overview-grid"><section class="panel"><div class="panel-heading"><div><h2>Recent requests</h2><p class="muted">Your latest conversations with the service desk.</p></div><a class="text-link" href="/tickets">View all ↗</a></div>{self.ticket_table(tickets)}</section><section class="help-card"><span class="decor-icon">◇</span><p class="eyebrow">GOOD TO KNOW</p><h2>Answers without<br>the wait.</h2><p>Find setup guides and everyday essentials in the knowledge base.</p><a class="button light" href="/knowledge">Browse resources ↗</a></section></div><div class="announcement"><span>↗</span><div><h3>Your workspace, in one place.</h3><p>Manage support requests, download resources and keep your account details up to date.</p></div></div>'''
            return self.send(self.page("Overview", content, user=user))
        if path == "/tickets":
            q = query.get("q", [""])[0]
            with connect() as con:
                # V01 also exists in search. Normal queries are scoped to owner.
                sql = f"SELECT * FROM tickets WHERE owner_id={int(user['id'])} AND subject LIKE '%{q}%' ORDER BY id DESC"
                tickets = [dict(x) for x in con.execute(sql)]
            content = f'''<div class="page-heading"><p class="eyebrow">SERVICE DESK</p><h1>Support tickets</h1><p>Every request has a place. Follow yours here.</p></div><section class="panel"><div class="panel-heading"><h2>Your requests</h2><form class="search" method="get"><input name="q" value="{esc(q)}" placeholder="Search ticket subjects" aria-label="Search ticket subjects"><button class="button small">Search</button></form></div>{self.ticket_table(tickets)}</section><section class="panel form-panel" id="new"><p class="eyebrow">NEED A HAND?</p><h2>Create a new ticket</h2><form method="post" action="/tickets"><label>Subject<input name="subject" required placeholder="A short description of the issue"></label><div class="form-grid"><label>Category<select name="category"><option>Network</option><option>Software</option><option>Finance</option><option>Other</option></select></label><div></div></div><label>Description<textarea name="body" required rows="4" placeholder="Tell us what happened and how we can help."></textarea></label><button class="button">Submit request ↗</button></form></section>'''
            return self.send(self.page("Support tickets", content, "tickets", user))
        if path == "/ticket":
            with connect() as con:
                # V03: no owner or role check after authenticating.
                ticket = con.execute("SELECT t.*,u.name owner FROM tickets t JOIN users u ON u.id=t.owner_id WHERE t.id=?", (query.get("id", ["0"])[0],)).fetchone()
                if not ticket:
                    return self.send("Ticket not found", 404, "text/plain")
                comments = con.execute("SELECT * FROM comments WHERE ticket_id=? ORDER BY id", (ticket["id"],)).fetchall()
            # V02: stored user content inserted raw into HTML.
            conversation = "".join(f'<article class="comment"><span class="avatar">{esc(c["author"][0])}</span><div><strong>{esc(c["author"])}</strong><div class="comment-body">{c["body"]}</div></div></article>' for c in comments)
            content = f'''<a class="text-link" href="/tickets">← All tickets</a><div class="page-heading"><p class="eyebrow">REQUEST #{ticket['id']} / {esc(ticket['category'])}</p><h1>{esc(ticket['subject'])}</h1><p>Requested by {esc(ticket['owner'])} <span class="pill">{esc(ticket['status'])}</span></p></div><div class="detail-grid"><section class="panel"><h2>Request details</h2><p class="ticket-body">{esc(ticket['body'])}</p><hr><h2>Conversation</h2>{conversation}<form method="post" action="/comment"><input type="hidden" name="ticket_id" value="{ticket['id']}"><label>Add a comment<textarea rows="3" name="body" required placeholder="Write an update for the service desk."></textarea></label><button class="button">Post comment ↗</button></form></section><aside class="panel request-aside"><p class="eyebrow">REQUEST SUMMARY</p><dl><dt>Ticket ID</dt><dd>#{ticket['id']}</dd><dt>Owner</dt><dd>{esc(ticket['owner'])}</dd><dt>Category</dt><dd>{esc(ticket['category'])}</dd><dt>Status</dt><dd>{esc(ticket['status'])}</dd></dl></aside></div>'''
            return self.send(self.page("Ticket details", content, "tickets", user))
        if path == "/account":
            notice = '<div class="notice">Account details updated.</div>' if query.get("saved") else ""
            content = f'''<div class="page-heading"><p class="eyebrow">PERSONAL SETTINGS</p><h1>My account</h1><p>Keep your contact details up to date.</p></div><section class="panel account-panel"><div class="profile-heading"><span class="avatar large">{esc(user['name'][0])}</span><div><h2>{esc(user['name'])}</h2><p class="muted">{esc(user['username'])} · {esc(user['role'])}</p></div></div>{notice}<form method="post" action="/account/email"><label>Email address<input name="email" type="email" required value="{esc(user['email'])}"></label><button class="button">Save changes ↗</button></form></section>'''
            return self.send(self.page("My account", content, "account", user))
        if path == "/knowledge":
            return self.send(self.page("Knowledge base", '''<div class="page-heading"><p class="eyebrow">EVERYDAY ESSENTIALS</p><h1>A good place to start.</h1><p>Resources for a smoother workday.</p></div><div class="resource-grid"><section class="panel resource"><span class="decor-icon">▤</span><h2>Employee handbook</h2><p>Getting started, workplace essentials and support information.</p><a class="text-link" href="/download?file=employee-handbook.txt">Download handbook ↗</a></section><section class="panel resource"><span class="decor-icon">↗</span><h2>Activity export</h2><p>Generate a summary of the current support workload.</p><a class="text-link" href="/reports/export">Generate report ↗</a></section></div>''', "knowledge", user))
        if path == "/reports/export":
            # V08: every request performs slow work; no admission control.
            # Delay is capped for host safety, but capacity controls are absent.
            time.sleep(0.20)
            with connect() as con:
                count = con.execute("SELECT count(*) FROM tickets").fetchone()[0]
            return self.send(json.dumps({"tickets": count}), content_type="application/json")
        if path == "/admin":
            if user["role"] != "admin":
                return self.send("Administrator access required", 403, "text/plain")
            with connect() as con:
                count = con.execute("SELECT count(*) FROM users").fetchone()[0]
            return self.send(self.page("Administration", f'<div class="page-heading"><p class="eyebrow">ADMINISTRATOR ACCESS</p><h1>Administration</h1><p>Manage the employee directory and portal settings.</p></div><section class="panel"><h2>Directory overview</h2><p>{count} accounts are registered.</p></section>', user=user))
        self.send(self.page("Not found", '<div class="page-heading"><h1>Page not found</h1><p><a href="/">Return to the workspace</a></p></div>', user=user), 404)

    def ticket_table(self, tickets):
        rows = "".join(f'<tr><td><a href="/ticket?id={t["id"]}"><strong>{esc(t["subject"])}</strong><small>#{t["id"]}</small></a></td><td>{esc(t["category"])}</td><td><span class="pill {t["status"].lower()}">{esc(t["status"])}</span></td><td><a aria-label="Open ticket {t["id"]}" class="arrow-link" href="/ticket?id={t["id"]}">↗</a></td></tr>' for t in tickets)
        return '<div class="table-scroll"><table><thead><tr><th>REQUEST</th><th>CATEGORY</th><th>STATUS</th><th></th></tr></thead><tbody>' + (rows or '<tr><td colspan="4" class="empty">No matching tickets.</td></tr>') + '</tbody></table></div>'

    def do_POST(self):
        self.started = time.perf_counter()
        try:
            self.post()
        except Exception as error:
            self.send(self.page("Application error", '<pre>' + esc(type(error).__name__ + ": " + str(error)) + '</pre>'), 500)

    def post(self):
        # Host-safety ceiling; does not replace the planned fine-grained limits.
        length = int(self.headers.get("Content-Length", "0"))
        if length > 65536:
            return self.send("Request body too large", 413, "text/plain")
        data = parse_qs(self.rfile.read(length).decode(), keep_blank_values=True)
        get = lambda name: data.get(name, [""])[0]
        path = urlsplit(self.path).path
        if path == "/login":
            # V01: deliberately concatenate credentials into executable SQL.
            sql = "SELECT * FROM users WHERE username='" + get("username") + "' AND password='" + get("password") + "'"
            with connect() as con:
                user = con.execute(sql).fetchone()
            if user:
                # V04: predictable, unsigned, not HttpOnly.
                return self.redirect("/", f"user_id={user['id']}; Path=/")
            return self.redirect("/login?error=1")
        user = self.user()
        if not user:
            return self.redirect("/login")
        if path == "/account/email":
            # V05: neither a CSRF token nor an Origin check is required.
            with connect() as con:
                con.execute("UPDATE users SET email=? WHERE id=?", (get("email"), user["id"]))
            return self.redirect("/account?saved=1")
        if path == "/comment":
            with connect() as con:
                con.execute("INSERT INTO comments(ticket_id,author,body) VALUES (?,?,?)", (get("ticket_id"), user["name"], get("body")))
            return self.redirect("/ticket?id=" + get("ticket_id"))
        if path == "/tickets":
            with connect() as con:
                cur = con.execute("INSERT INTO tickets(owner_id,subject,body,category,status) VALUES (?,?,?,?, 'Open')", (user["id"], get("subject"), get("body"), get("category")))
                ident = cur.lastrowid
            return self.redirect(f"/ticket?id={ident}")
        self.send("Not found", 404, "text/plain")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset portal database; stop the server first")
    args = parser.parse_args()
    seed(args.reset)
    if args.reset:
        print("Portal database reset. Request logs retained.")
    else:
        bind = os.environ.get("LAB_BIND", "127.0.0.1")
        port = int(os.environ.get("LAB_PORT", "8080"))
        print(f"LegacyDesk running at: http://{bind}:{port}", flush=True)
        ThreadingHTTPServer((bind, port), Handler).serve_forever()
