# Hardened stack verification

| Check | Result | Details |
|---|---|---|
| Original source preserved | PASS | Checked all 51 previously tracked files by SHA-256. |
| Original site still running | PASS | Read-only health request on port 8080. |
| HTTP redirects to HTTPS | PASS | Dedicated port 8082 redirects to 8443. |
| Legitimate HTTPS sign-in | PASS | Server-side session established using v2's generated password. |
| Session cookie policy | PASS | Cookie values redacted from all saved evidence. |
| V01 SQL injection blocked | PASS | CRS block. Direct origin tests also verify parameterised queries and safe login input. |
| V02 XSS blocked | PASS | CRS block. Direct origin tests separately verify output encoding. |
| V03 ticket ownership enforced | PASS | Alice cannot read Bob's ticket. |
| V04 session forgery rejected | PASS | Unsigned v1 identity cookie is ignored; Alice lacks the admin role. |
| V05 forged account update rejected | PASS | Cross-origin tokenless request cannot change Alice's email. |
| V06 traversal rejected | PASS | Edge rules plus a fixed-file allowlist at the origin. |
| V07 diagnostics removed and headers enabled | PASS | Secure headers are also present on error responses. |
| Legitimate use remains available | PASS | Normal comment and handbook download pass the WAF and app. |
| V08 expensive requests throttled | PASS | {"requests": 40, "workers": 4, "elapsed_seconds": 0.107, "status_counts": {"200": 5, "429": 35}, "completed_responses_rps": 373.08, "median_latency_ms": 5.12, "p95_latency_ms": 44.1, "limitation": "Same request count and concurrency as v1; includes TLS and rejected requests. Throughput is not accepted report throughput or proof of DDoS resistance."} |
| Edge errors disable caching | PASS | WAF blocks and gateway rate-limit responses include Cache-Control: no-store. |
| Logout invalidates session | PASS | Old cookie no longer authenticates after logout. |
| Real WAF audit evidence | PASS | {"rule_ids": ["920350", "930110", "930120", "941100", "941120", "941160", "942100", "949110"], "crs_versions": ["OWASP_CRS/4.30.0"], "application_security_events": ["access_denied", "csrf_rejected", "invalid_session", "login_succeeded", "logout", "request"], "gateway_rejections": 140} |
