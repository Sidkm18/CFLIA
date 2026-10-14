# LegacyDesk — vulnerable baseline

Phase 1 of **Web Application Attack Simulation and Layered Security Hardening using WAF, Rate Limiting and Defensive Controls**.

A fictional employee service portal with eight intentional findings, real SQLite records, a basic Nginx gateway, and repeatable baseline evidence. This phase implements the vulnerable site only. Hardened application code, WAF, before/after comparison, final report and final video are future phases.

The initial source and captured evidence are preserved in `output/legacydesk-vulnerable-baseline.zip`. Extract it into a separate directory to recover the vulnerable stage after later fixes. Stop the current Compose stack before running a recovered copy, since both use the same project name, ports and lab volume.

## Start the Nginx lab

```sh
docker compose up -d --build
```

Open **http://127.0.0.1:8080**. Use exactly `127.0.0.1` for the browser CSRF demonstration. The separate form is served at **http://127.0.0.1:8091/csrf.html**.

| Account | Password | Role |
|---|---|---|
| alice | alice123 | Employee |
| bob | bob123 | Employee |
| admin | admin | Administrator |

All data and credentials are fictional. Exposed host ports bind to loopback. The app container has no published port and sits on an internal network. Nginx also joins an edge bridge network to publish its localhost port; the separate CSRF demo uses that edge network. CPU/memory limits bound the demonstration. No public hosting is configured.

## Capture the baseline

```sh
python3 scripts/probe_baseline.py
docker compose logs --no-color nginx app > output/baseline-container.log
docker stats --no-stream > output/baseline-resources.txt
```

The collector sends only localhost requests, adds a harmless XSS comment, changes Alice's email and makes **40 requests with four workers**. It creates a timestamped `output/evidence/baseline-*/` directory containing real HTTP captures, JSON results and an editable evidence summary. Run on a fresh baseline for clean recordings. Screenshot/browser steps are in [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md). The [captured baseline report](docs/BASELINE_REPORT.md) includes screenshots of all eight findings.

To turn the latest captured JSON into a standalone evidence page:

```sh
python3 scripts/render_evidence.py
```

## Reset / stop

Stop the app before resetting the database; this deletes only seeded lab records and created tickets/comments. Request logs remain available.

```sh
docker compose stop app
docker compose run --rm --no-deps app python app/server.py --reset
docker compose up -d app
```

```sh
docker compose down
```

## Python-only fallback

No third-party Python packages are required. This fallback serves the app directly and **does not demonstrate Nginx or container isolation**.

```sh
python3 app/server.py
```

In a second terminal:

```sh
python3 -m http.server 8091 --bind 127.0.0.1 --directory demos
```

Stop the app with Ctrl+C before `python3 app/server.py --reset`.

## Eight findings

| ID | Vulnerability | Observable baseline failure |
|---|---|---|
| V01 | SQL injection | Sign in as admin without its password |
| V02 | Stored XSS | A ticket comment executes harmless browser code |
| V03 | Broken access control / IDOR | Alice reads Bob's confidential ticket |
| V04 | Weak authentication and sessions | Forged unsigned cookie grants administrator access |
| V05 | CSRF | A separate-origin form changes Alice's email |
| V06 | Path traversal | Download exposes a private dummy configuration file |
| V07 | Security misconfiguration | Public debug output leaks dummy passwords; secure headers absent |
| V08 | Unrestricted resource consumption | Slow report accepts repeated requests without rate limits |

See [docs/VULNERABILITIES.md](docs/VULNERABILITIES.md) for OWASP mappings, code locations and the planned controls. These are eight findings, not eight distinct OWASP Top 10 categories. OWASP is guidance used to design the fixes; it does not patch the site itself.

## Architecture and honest claims

```text
Browser / local test tools → 127.0.0.1:8080 → Nginx → Python app:8000 → SQLite
Separate CSRF origin      → 127.0.0.1:8091
```

Nginx already acts as a basic reverse proxy. This baseline lacks a WAF, CRS rules, rate/connection limits, cache, security headers and security-aware monitoring. Basic Nginx access logs and application latency/status logs exist so before/after comparison is possible. Their existence does not imply alerting or attack detection.

The “server neglected for years” scenario is represented by weak application code/configuration. Images are contemporary tags; **no old Nginx version, real CVE or known vulnerable dependency is claimed**. Image tags can drift: record image IDs from `docker compose images` for the exact recording run. The traversal sandbox, body ceiling and container limits are host-safety boundaries; application-level weaknesses remain demonstrable.

The bounded request probe shows missing admission control, not successful service denial or volumetric DDoS protection. A local Nginx WAF cannot establish protection against an upstream bandwidth-saturating DDoS attack. Later stages should measure latency, HTTP outcomes and container CPU/memory under the same test conditions.

## Baseline choice and sources

[OWASP Juice Shop](https://github.com/juice-shop/juice-shop) and [OWASP WebGoat](https://github.com/WebGoat/WebGoat) are established intentionally vulnerable training applications. This custom portal is used because exactly eight compact scenarios and direct source fixes fit the seven-minute demonstration better. No source code from those projects is copied.

- [OWASP Top 10, selected 2021 edition](https://top10.owasp.org/2021/)
- [OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [Nginx request limiting documentation](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [OWASP Core Rule Set](https://coreruleset.org/)
