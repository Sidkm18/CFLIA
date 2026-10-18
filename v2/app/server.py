"""Hardened LegacyDesk application. Kept entirely separate from the v1 portal."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, abort, g, redirect, request, send_file
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from .views import Renderer, esc

ROOT = Path(__file__).resolve().parent
RENDER = Renderer()
COOKIE = "__Host-legacydesk_v2"
PASSWORD_METHOD = "pbkdf2:sha256:600000"
CSP = "default-src 'none'; style-src 'self'; img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'"


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(
        STATE=Path(os.environ.get("PORTAL_STATE", str(ROOT.parent / "state"))),
        ORIGINS=set(os.environ.get("PORTAL_ORIGINS", "https://127.0.0.1:8443,https://localhost:8443").split(",")),
        TRUSTED_HOSTS=["127.0.0.1", "localhost"],
        MAX_CONTENT_LENGTH=16384, MAX_FORM_MEMORY_SIZE=16384, MAX_FORM_PARTS=12,
        SESSION_LIFETIME=3600, SESSION_IDLE=900, MAX_ANONYMOUS_SESSIONS=1000,
    )
    if test_config:
        app.config.update(test_config)
    state = Path(app.config["STATE"])
    state.mkdir(parents=True, exist_ok=True)
    state.chmod(0o700)
    os.umask(0o077)
    db = state / "portal.sqlite3"
    # Exactly two controlled proxy hops; the gateway replaces client-supplied XFF.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=2, x_proto=1)

    @contextmanager
    def connect():
        con = sqlite3.connect(db, timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    with connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE,
          password_hash TEXT NOT NULL, name TEXT, email TEXT, role TEXT);
        CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT,
          owner_id INTEGER REFERENCES users(id), subject TEXT, body TEXT, category TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT,
          ticket_id INTEGER REFERENCES tickets(id), author TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,
          user_id INTEGER REFERENCES users(id), csrf TEXT NOT NULL,
          created REAL, expires REAL, last_seen REAL);
        CREATE TABLE IF NOT EXISTS limits(bucket TEXT PRIMARY KEY, starts REAL, hits INTEGER);
        CREATE TABLE IF NOT EXISTS report_cache(user_id INTEGER PRIMARY KEY,
          data TEXT, expires REAL);
        """)
        if not con.execute("SELECT count(*) FROM users").fetchone()[0]:
            credentials = app.config.get("BOOTSTRAP_PASSWORDS") or {
                name: os.environ.get("PORTAL_" + name.upper() + "_PASSWORD", "")
                for name in ("admin", "alice", "bob")}
            if any(len(value) < 20 for value in credentials.values()) or len(set(credentials.values())) != 3:
                raise RuntimeError("Initialise unique strong credentials with scripts/setup.py before starting v2")
            for ident, username, name, role in [(1, "admin", "Portal Administrator", "admin"),
                    (2, "alice", "Alice Morgan", "employee"), (3, "bob", "Bob Chen", "employee")]:
                con.execute("INSERT INTO users VALUES(?,?,?,?,?,?)", (
                    ident, username, generate_password_hash(credentials[username], method=PASSWORD_METHOD),
                    name, username + "@example.test", role))
            con.executemany("INSERT INTO tickets VALUES(?,?,?,?,?,?)", [
                (1001, 2, "Unable to connect to office VPN", "The VPN disconnects after sign-in. Please help restore access.", "Network", "Open"),
                (1002, 3, "Confidential payroll correction", "Bob's payroll adjustment is ₹12,500. Please review the correction before the next payroll cycle.", "Finance", "Pending"),
                (1003, 2, "Request for design software licence", "Please allocate a design software licence for the upcoming project.", "Software", "Pending"),
                (1004, 1, "Quarterly backup review", "Review the internal backup process and retention settings.", "Operations", "Closed")])
            con.execute("INSERT INTO comments(ticket_id,author,body) VALUES(1001,?,?)", (
                "Service Desk", "We have received your request. Please attach the connection details."))
    db.chmod(0o600)
    dummy_hash = generate_password_hash(secrets.token_urlsafe(32), method=PASSWORD_METHOD)

    def event(kind, **details):
        # Deliberately exclude bodies, query strings, credentials and session tokens.
        app.logger.warning(json.dumps({"event": kind, "request_id": getattr(g, "request_id", "startup"),
            "path": request.path, "ip": request.remote_addr, "user_id": (g.user or {}).get("id"), **details}))

    def rate(bucket, count, seconds):
        now = time.time()
        with connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT starts,hits FROM limits WHERE bucket=?", (bucket,)).fetchone()
            if row and now - row["starts"] < seconds:
                if row["hits"] >= count:
                    event("rate_limited", policy=bucket.split(":")[0])
                    abort(429)
                con.execute("UPDATE limits SET hits=hits+1 WHERE bucket=?", (bucket,))
            else:
                con.execute("INSERT OR REPLACE INTO limits VALUES(?,?,1)", (bucket, now))
            con.execute("DELETE FROM limits WHERE starts<?", (now - 3600,))

    def new_session(user_id=None):
        now = time.time()
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with connect() as con:
            # Bound abandoned pre-login sessions even when clients discard cookies.
            # Serialize cleanup and insertion across workers to keep the cap exact.
            con.execute("BEGIN IMMEDIATE")
            con.execute("DELETE FROM sessions WHERE expires<=? OR last_seen<=?", (now, now - app.config["SESSION_IDLE"]))
            old = getattr(g, "session", None)
            if old:
                con.execute("DELETE FROM sessions WHERE token_hash=?", (old["token_hash"],))
            con.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?)", (
                token_hash, user_id, secrets.token_urlsafe(32), now,
                now + (app.config["SESSION_LIFETIME"] if user_id else 900), now))
            con.execute("DELETE FROM sessions WHERE user_id IS NULL AND token_hash IN (SELECT token_hash FROM sessions WHERE user_id IS NULL ORDER BY created DESC, token_hash DESC LIMIT -1 OFFSET ?)", (app.config["MAX_ANONYMOUS_SESSIONS"],))
            if user_id:
                con.execute("DELETE FROM sessions WHERE user_id=? AND token_hash NOT IN (SELECT token_hash FROM sessions WHERE user_id=? ORDER BY created DESC LIMIT 5)", (user_id, user_id))
            g.session = dict(con.execute("SELECT * FROM sessions WHERE token_hash=?", (token_hash,)).fetchone())
        g.new_token = token

    @app.before_request
    def prepare():
        g.started = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID", "")
        if not re.fullmatch(r"[a-f0-9]{32}", g.request_id):
            g.request_id = uuid.uuid4().hex
        g.user = None
        g.session = None
        g.new_token = None
        g.clear_cookie = False
        if request.path in {"/health", "/static/style.css", "/favicon.ico"}:
            return
        rate("global:" + str(request.remote_addr), 240, 60)
        cookie = request.cookies.get(COOKIE, "")
        if cookie:
            if re.fullmatch(r"[A-Za-z0-9_-]{43}", cookie):
                now = time.time()
                with connect() as con:
                    con.execute("DELETE FROM sessions WHERE expires<=? OR last_seen<=?", (now, now - app.config["SESSION_IDLE"]))
                    row = con.execute("SELECT * FROM sessions WHERE token_hash=?", (hashlib.sha256(cookie.encode()).hexdigest(),)).fetchone()
                    if row:
                        g.session = dict(row)
                        con.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (now, row["token_hash"]))
                        if row["user_id"]:
                            user = con.execute("SELECT id,username,name,email,role FROM users WHERE id=?", (row["user_id"],)).fetchone()
                            g.user = dict(user) if user else None
            if not g.session:
                g.clear_cookie = True
                event("invalid_session")
        if request.method == "POST":
            # Login, logout and every write use both Origin and synchroniser token.
            if request.headers.get("Origin", "") not in app.config["ORIGINS"]:
                event("csrf_rejected", reason="origin")
                abort(403)
            if request.mimetype != "application/x-www-form-urlencoded":
                abort(415)
            if any(len(request.form.getlist(key)) != 1 for key in request.form):
                abort(400)
            token = request.form.get("csrf_token", "")
            if not g.session or not token.isascii() or not hmac.compare_digest(token, g.session["csrf"]):
                event("csrf_rejected", reason="token")
                abort(403)

    @app.after_request
    def finish(response):
        response.headers.update({
            "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cache-Control": "no-store", "X-Request-ID": getattr(g, "request_id", ""),
        })
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=86400"
        if getattr(g, "new_token", None):
            response.set_cookie(COOKIE, g.new_token, max_age=app.config["SESSION_LIFETIME"],
                                secure=True, httponly=True, samesite="Strict", path="/")
        elif getattr(g, "clear_cookie", False):
            response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="Strict", path="/")
        app.logger.info(json.dumps({"event": "request", "request_id": getattr(g, "request_id", ""),
            "path": request.path, "method": request.method, "status": response.status_code,
            "latency_ms": round((time.perf_counter() - getattr(g, "started", time.perf_counter())) * 1000, 2)}))
        return response

    def page(title, content, active="overview", status=200):
        rendered = RENDER.page(title, content, active, g.user)
        if g.session:
            hidden = '<input type="hidden" name="csrf_token" value="' + esc(g.session["csrf"]) + '">'
            rendered = re.sub(r'(<form\b[^>]*method="post"[^>]*>)', lambda m: m[0] + hidden, rendered)
        return rendered, status

    def require_user():
        if not g.user:
            abort(401)

    def field(name, minimum=1, maximum=2000):
        value = request.form.get(name, "").strip()
        if not minimum <= len(value) <= maximum or any(ord(ch) < 32 and ch not in "\n\r\t" for ch in value):
            abort(400)
        return value

    def ticket_for(ident):
        if not re.fullmatch(r"[1-9][0-9]{0,8}", str(ident)):
            abort(400)
        with connect() as con:
            ticket = con.execute("SELECT t.*,u.name owner FROM tickets t JOIN users u ON u.id=t.owner_id WHERE t.id=?", (ident,)).fetchone()
        if not ticket:
            abort(404)
        if ticket["owner_id"] != g.user["id"] and g.user["role"] != "admin":
            event("access_denied", resource="ticket", resource_id=int(ident))
            abort(403)
        return ticket

    @app.errorhandler(Exception)
    def error(error):
        status = error.code if isinstance(error, HTTPException) else 500
        if status == 500:
            app.logger.exception("Unhandled server error; request_id=%s", getattr(g, "request_id", ""))
        titles = {400: "Check your request", 401: "Please sign in", 403: "Access unavailable",
                  404: "Page not found", 405: "Method not allowed", 413: "Request too large",
                  415: "Unsupported request", 429: "Please try again shortly"}
        title = titles.get(status, "Something went wrong")
        body, _ = page(title, f'<div class="page-heading"><h1>{title}</h1><p>Your request could not be completed.</p></div><a class="text-link" href="/login">Return to sign in</a>', status=status)
        response = app.make_response((body, status))
        if status == 429:
            response.headers["Retry-After"] = "60"
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "LegacyDesk"}

    @app.get("/static/style.css")
    def stylesheet():
        return send_file(ROOT / "static/style.css", mimetype="text/css")

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            if g.user:
                return redirect("/", code=303)
            if not g.session:
                new_session()
            return page("Sign in", '''<div class="login-layout"><section class="login-story"><p class="eyebrow">YOUR WORKDAY, CONNECTED</p><h1>A little support.<br>A better workday.</h1><p>One place for the tools, answers and support you need to keep things moving.</p><div class="story-card"><span>01 / SERVICE DESK</span><h3>Help is one ticket away.</h3><p>Raise a request, follow the conversation and get back to what matters.</p></div></section><section class="panel login-panel"><p class="eyebrow">EMPLOYEE ACCESS</p><h2>Welcome back</h2><p class="muted">Sign in to your workspace.</p><form method="post" action="/login"><label>Username<input name="username" autocomplete="username" required placeholder="Enter your username"></label><label>Password<input name="password" type="password" autocomplete="current-password" required placeholder="Enter your password"></label><button class="button full">Sign in <span>↗</span></button></form><p class="muted account-help">For account access, contact your service desk.</p></section></div>''')
        rate("login_ip:" + str(request.remote_addr), 10, 60)
        username = field("username", 3, 40)
        password = field("password", 1, 128)
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", username):
            event("invalid_login_input")
            abort(400)
        rate("login_account:" + username.lower(), 8, 60)
        with connect() as con:
            row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        valid = check_password_hash(row["password_hash"] if row else dummy_hash, password)
        if not row or not valid:
            event("login_failed")
            abort(401)
        new_session(row["id"])
        event("login_succeeded", account_id=row["id"])
        return redirect("/", code=303)

    @app.post("/logout")
    def logout():
        if g.session:
            with connect() as con:
                con.execute("DELETE FROM sessions WHERE token_hash=?", (g.session["token_hash"],))
        g.session = None
        g.clear_cookie = True
        event("logout")
        return redirect("/login", code=303)

    @app.get("/")
    def overview():
        if not g.user:
            return redirect("/login", code=303)
        with connect() as con:
            tickets = [dict(t) for t in con.execute("SELECT * FROM tickets WHERE owner_id=? ORDER BY id DESC", (g.user["id"],))]
        opened = sum(t["status"] != "Closed" for t in tickets)
        content = f'''<div class="page-heading heading-row"><div><p class="eyebrow">YOUR WORKSPACE</p><h1>Hello, {esc(g.user['name'].split()[0])}.</h1><p>Here’s what’s happening with your support requests.</p></div><a class="button" href="/tickets#new">＋ Create a ticket</a></div><div class="stats"><div class="stat"><span>Active requests</span><strong>{opened:02}</strong><small>Awaiting a resolution</small></div><div class="stat"><span>Total tickets</span><strong>{len(tickets):02}</strong><small>In your workspace</small></div><div class="stat"><span>Resolved tickets</span><strong>{len(tickets)-opened:02}</strong><small>Completed requests</small></div></div><div class="overview-grid"><section class="panel"><div class="panel-heading"><div><h2>Recent requests</h2><p class="muted">Your latest conversations with the service desk.</p></div><a class="text-link" href="/tickets">View all ↗</a></div>{RENDER.ticket_table(tickets)}</section><section class="help-card"><span class="decor-icon">◇</span><p class="eyebrow">GOOD TO KNOW</p><h2>Answers without<br>the wait.</h2><p>Find setup guides and everyday essentials in the knowledge base.</p><a class="button light" href="/knowledge">Browse resources ↗</a></section></div><div class="announcement"><span>↗</span><div><h3>Your workspace, in one place.</h3><p>Manage support requests, download resources and keep your account details up to date.</p></div></div>'''
        return page("Overview", content)

    @app.route("/tickets", methods=["GET", "POST"])
    def tickets():
        require_user()
        if request.method == "POST":
            rate("create:" + str(g.user["id"]), 10, 60)
            subject, body, category = field("subject", 3, 160), field("body", 1, 4000), field("category", 1, 20)
            if category not in {"Network", "Software", "Finance", "Other"}:
                abort(400)
            with connect() as con:
                cur = con.execute("INSERT INTO tickets(owner_id,subject,body,category,status) VALUES(?,?,?,?,'Open')", (g.user["id"], subject, body, category))
                ident = cur.lastrowid
                con.execute("DELETE FROM report_cache WHERE user_id=?", (g.user["id"],))
            return redirect(f"/ticket?id={ident}", code=303)
        q = request.args.get("q", "")
        if len(q) > 120:
            abort(400)
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with connect() as con:
            rows = [dict(t) for t in con.execute("SELECT * FROM tickets WHERE owner_id=? AND subject LIKE ? ESCAPE '\\' ORDER BY id DESC", (g.user["id"], pattern))]
        content = f'''<div class="page-heading"><p class="eyebrow">SERVICE DESK</p><h1>Support tickets</h1><p>Every request has a place. Follow yours here.</p></div><section class="panel"><div class="panel-heading"><h2>Your requests</h2><form class="search" method="get"><input name="q" value="{esc(q)}" placeholder="Search ticket subjects" aria-label="Search ticket subjects"><button class="button small">Search</button></form></div>{RENDER.ticket_table(rows)}</section><section class="panel form-panel" id="new"><p class="eyebrow">NEED A HAND?</p><h2>Create a new ticket</h2><form method="post" action="/tickets"><label>Subject<input name="subject" required maxlength="160" placeholder="A short description of the issue"></label><div class="form-grid"><label>Category<select name="category"><option>Network</option><option>Software</option><option>Finance</option><option>Other</option></select></label><div></div></div><label>Description<textarea name="body" required maxlength="4000" rows="4" placeholder="Tell us what happened and how we can help."></textarea></label><button class="button">Submit request ↗</button></form></section>'''
        return page("Support tickets", content, "tickets")

    @app.get("/ticket")
    def ticket():
        require_user()
        t = ticket_for(request.args.get("id", ""))
        with connect() as con:
            comments = con.execute("SELECT author,body FROM comments WHERE ticket_id=? ORDER BY id", (t["id"],)).fetchall()
        conversation = "".join(f'<article class="comment"><span class="avatar">{esc(c["author"][0])}</span><div><strong>{esc(c["author"])}</strong><div class="comment-body">{esc(c["body"])}</div></div></article>' for c in comments)
        content = f'''<a class="text-link" href="/tickets">← All tickets</a><div class="page-heading"><p class="eyebrow">REQUEST #{t['id']} / {esc(t['category'])}</p><h1>{esc(t['subject'])}</h1><p>Requested by {esc(t['owner'])} <span class="pill">{esc(t['status'])}</span></p></div><div class="detail-grid"><section class="panel"><h2>Request details</h2><p class="ticket-body">{esc(t['body'])}</p><hr><h2>Conversation</h2>{conversation}<form method="post" action="/comment"><input type="hidden" name="ticket_id" value="{t['id']}"><label>Add a comment<textarea rows="3" name="body" maxlength="2000" required placeholder="Write an update for the service desk."></textarea></label><button class="button">Post comment ↗</button></form></section><aside class="panel request-aside"><p class="eyebrow">REQUEST SUMMARY</p><dl><dt>Ticket ID</dt><dd>#{t['id']}</dd><dt>Owner</dt><dd>{esc(t['owner'])}</dd><dt>Category</dt><dd>{esc(t['category'])}</dd><dt>Status</dt><dd>{esc(t['status'])}</dd></dl></aside></div>'''
        return page("Ticket details", content, "tickets")

    @app.post("/comment")
    def comment():
        require_user()
        t = ticket_for(field("ticket_id", 1, 9))
        body = field("body", 1, 2000)
        rate("comment:" + str(g.user["id"]), 20, 60)
        with connect() as con:
            con.execute("INSERT INTO comments(ticket_id,author,body) VALUES(?,?,?)", (t["id"], g.user["name"], body))
        return redirect(f"/ticket?id={t['id']}", code=303)

    @app.get("/account")
    def account():
        require_user()
        u = g.user
        notice = '<div class="notice">Account details updated.</div>' if request.args.get("saved") == "1" else ""
        return page("My account", f'''<div class="page-heading"><p class="eyebrow">PERSONAL SETTINGS</p><h1>My account</h1><p>Keep your contact details up to date.</p></div><section class="panel account-panel"><div class="profile-heading"><span class="avatar large">{esc(u['name'][0])}</span><div><h2>{esc(u['name'])}</h2><p class="muted">{esc(u['username'])} · {esc(u['role'])}</p></div></div>{notice}<form method="post" action="/account/email"><label>Email address<input name="email" type="email" required maxlength="254" value="{esc(u['email'])}"></label><button class="button">Save changes ↗</button></form></section>''', "account")

    @app.post("/account/email")
    def email():
        require_user()
        value = field("email", 3, 254)
        if not re.fullmatch(r"[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", value):
            abort(400)
        rate("profile:" + str(g.user["id"]), 5, 60)
        with connect() as con:
            con.execute("UPDATE users SET email=? WHERE id=?", (value, g.user["id"]))
        event("account_updated")
        return redirect("/account?saved=1", code=303)

    @app.get("/download")
    def download():
        require_user()
        filename = request.args.get("file", "employee-handbook.txt")
        allowed = {"employee-handbook.txt": ROOT / "fixtures/downloads/employee-handbook.txt"}
        if filename not in allowed:
            event("download_rejected")
            abort(404)
        return send_file(allowed[filename], mimetype="text/plain", as_attachment=True, download_name=filename)

    @app.get("/knowledge")
    def knowledge():
        require_user()
        return page("Knowledge base", '''<div class="page-heading"><p class="eyebrow">EVERYDAY ESSENTIALS</p><h1>A good place to start.</h1><p>Resources for a smoother workday.</p></div><div class="resource-grid"><section class="panel resource"><span class="decor-icon">▤</span><h2>Employee handbook</h2><p>Getting started, workplace essentials and support information.</p><a class="text-link" href="/download?file=employee-handbook.txt">Download handbook ↗</a></section><section class="panel resource"><span class="decor-icon">↗</span><h2>Activity export</h2><p>Generate a summary of the current support workload.</p><a class="text-link" href="/reports/export">Generate report ↗</a></section></div>''', "knowledge")

    @app.get("/reports/export")
    def report():
        require_user()
        uid = g.user["id"]
        rate("report:" + str(uid), 6, 60)
        now = time.time()
        with connect() as con:
            row = con.execute("SELECT data FROM report_cache WHERE user_id=? AND expires>?", (uid, now)).fetchone()
            if row:
                return app.response_class(row["data"], mimetype="application/json")
            count = con.execute("SELECT count(*) FROM tickets WHERE owner_id=?", (uid,)).fetchone()[0]
            data = json.dumps({"tickets": count})
            con.execute("INSERT OR REPLACE INTO report_cache VALUES(?,?,?)", (uid, data, now + 30))
        return app.response_class(data, mimetype="application/json")

    @app.get("/admin")
    def admin():
        require_user()
        if g.user["role"] != "admin":
            event("access_denied", resource="admin")
            abort(403)
        with connect() as con:
            count = con.execute("SELECT count(*) FROM users").fetchone()[0]
        return page("Administration", f'<div class="page-heading"><p class="eyebrow">ADMINISTRATOR ACCESS</p><h1>Administration</h1><p>Manage the employee directory and portal settings.</p></div><section class="panel"><h2>Directory overview</h2><p>{count} accounts are registered.</p></section>')

    app.logger.setLevel("INFO")
    return app
