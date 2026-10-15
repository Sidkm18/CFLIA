# LegacyDesk v2

This directory is an independent hardened copy of the employee portal. The original application, database, Compose configuration and saved evidence in the parent directory are unchanged.

| Version | URL | Compose project | Data |
|---|---|---|---|
| Original vulnerable portal | http://127.0.0.1:8080 | `legacydesk-lab` | Existing `legacydesk-lab_lab-data` volume |
| Hardened v2 portal | https://127.0.0.1:8443 | `legacydesk-v2` | Separate `legacydesk-v2_portal-data` volume |
| v2 HTTP redirect | http://127.0.0.1:8082 | `legacydesk-v2` | Redirects to v2 HTTPS |

## Start v2

From **this directory**:

```sh
python3 scripts/setup.py
docker compose up -d --build
```

The setup script generates unique passwords for `alice`, `bob` and `admin`, plus a local CA and a server certificate with localhost/127.0.0.1 SANs. Read the passwords in `state/credentials.json`. They differ from v1's passwords; `alice123` and `admin` no longer work in v2. The credentials, bootstrap environment file, private keys, sessions and database are excluded from Git.

Open **https://127.0.0.1:8443**. Your browser may display a certificate warning because the generated local CA is not installed in your trust store. For local recording, accept the certificate exception for this address. Automated integration checks verify TLS using `state/tls/ca.crt`; the browser QA configuration ignores certificate errors only for its isolated test browser. Public deployment needs a trusted certificate for the actual hostname and corresponding origin/host configuration. No system trust store has been changed.

The normal portal layout is retained. Security instructions and proof labels are kept out of the website.

## Layers

```text
HTTPS browser / local security tools
  → Nginx gateway :8443  [TLS, secure headers, request/body/time/connection limits]
  → ModSecurity + OWASP CRS  [blocking mode, paranoia level 1, audit records]
  → Gunicorn / Flask :8000  [application fixes, sessions, CSRF, ownership and quotas]
  → SQLite  [hashed passwords, hashed session IDs, atomic limits, report cache]
```

Only the gateway publishes localhost ports. The WAF and application run on separate internal Docker networks; neither has a published origin port. The app runs as a non-root user with a read-only root filesystem, a dedicated data volume, dropped Linux capabilities and bounded workers/resources. The local CA private key is not mounted in any service.

## Eight fixes

| ID | Root-cause application fix | Additional layer |
|---|---|---|
| V01 SQL injection | Bound SQL parameters; constrained usernames and literal search terms | CRS SQLi rules |
| V02 Stored XSS | HTML-context output encoding for comments and all displayed fields | Strict CSP without inline scripts; CRS XSS rules |
| V03 IDOR/access control | Same ownership/administrator checks for ticket reads and comment writes | Anonymous requests require sign-in |
| V04 Weak authentication/sessions | Unique generated passwords; salted PBKDF2-SHA256 at 600,000 iterations; random server-side sessions stored by hash; rotation, idle/absolute expiry and logout invalidation | `__Host-` cookie with Secure, HttpOnly and SameSite=Strict; login limits |
| V05 CSRF | Synchroniser token and exact Origin checks on login, logout and every write | HTTPS and strict cookie policy; logout is POST-only |
| V06 Traversal | Fixed handbook allowlist; authenticated download; no user-controlled filesystem path | CRS traversal rules |
| V07 Misconfiguration | `/debug` removed; generic errors; trusted hosts; no plaintext passwords in DB | Secure headers on success and errors; Nginx version hidden |
| V08 Resource consumption | Per-account/IP limits persisted atomically in SQLite; cached, user-scoped reports; bounded input and report cost | Nginx rate/connection/body/time limits; bounded workers and containers |

The WAF is pinned by image digest. The verified image runs **ModSecurity 3.0.17**, **ModSecurity-nginx 1.0.4** and **OWASP CRS 4.30.0**. See `output/runtime-versions.txt` for the actual runtime/image metadata captured during verification. Python dependencies are pinned in `requirements.txt`.

## Verify

From this directory:

```sh
docker compose exec -T app python -m unittest discover -s tests -v
python3 scripts/verify_stack.py
docker compose exec -T gateway nginx -t
docker compose exec -T waf nginx -t
```

The 19 direct application tests use temporary databases inside the v2 app container and bypass the WAF. They verify real root-cause fixes and normal employee/admin workflows. The integration script checks the full deployed stack, replays the original attack payloads where applicable, sends 40 bounded report requests with four workers and records redacted evidence under `output/verification-*/`. It creates one normal comment in v2 during its legitimate-use check. It never attacks, resets or writes to v1. Rate limits persist, so wait at least 60 seconds between full integration runs to begin with a fresh quota window.

The report probe uses the same count/concurrency as the captured v1 probe. The endpoints now enforce authentication/quota and use HTTPS; rejected responses and accepted reports are separate outcomes. The measured HTTP-response rate is not equivalent to report-generation throughput or proof of DDoS resistance. Local controls cannot absorb an upstream bandwidth-saturating attack.

## Logs and evidence

```sh
docker compose logs --no-color app
docker compose logs --no-color gateway
docker compose logs --no-color waf
docker stats --no-stream
```

The app emits structured security events such as denied access, CSRF rejection, failed sign-in, invalid sessions and quotas. Gateway logs include HTTP status, latency, limit outcome and a request ID; the gateway forwards the same ID to the app. WAF audit records include real CRS rule IDs and versions. WAF audit parts exclude request bodies and header blocks; application logs omit passwords, cookies, CSRF values and query strings. This is log-based detection/verification, not an installed SIEM or alert-notification service.

Read [docs/HARDENING_REPORT.md](docs/HARDENING_REPORT.md) for the observed before/after results and [docs/RETEST_GUIDE.md](docs/RETEST_GUIDE.md) for recording steps.

## Stop v2 only

```sh
docker compose down
```

Run it from `v2`, or use `docker compose -f v2/compose.yaml down` from the repository root. Do not use `-v` unless you intend to delete v2's records. These commands do not stop the original project.

## References

- [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [OWASP XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Official CRS container](https://github.com/coreruleset/modsecurity-crs-docker)
- [Flask security considerations](https://flask.palletsprojects.com/en/stable/web-security/)
- [Nginx request limits](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
