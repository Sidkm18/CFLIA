# Baseline findings and hardening contract

Scope: fictional local employee portal. OWASP mappings deliberately use **Top 10:2021**, a named edition, for consistent academic references. No claim is made that all Top 10 categories are covered. Findings sharing a category remain distinct mechanisms with distinct fixes.

| ID | Finding / source location | OWASP 2021 | Proof | Planned root-cause fix | Supporting edge control |
|---|---|---|---|---|---|
| V01 | SQL injection in `Handler.post` login and `Handler.get` ticket search | A03 Injection | Injected username selects admin; malicious search alters SQL | Parameterised SQL everywhere, input bounds, safe errors | CRS SQLi rules |
| V02 | Stored XSS in ticket comment rendering | A03 Injection | Saved SVG runs on reopen | Context-aware HTML output encoding; no raw user HTML | CSP and CRS XSS rules |
| V03 | IDOR in ticket read; missing permission check on comment target | A01 Broken Access Control | Alice opens Bob's ticket 1002 | Shared ownership/role checks on reads and writes | WAF alone cannot infer business permissions |
| V04 | Plaintext/default passwords and unsigned `user_id` cookie | A07 Authentication Failures; A02 Cryptographic Failures | Forged identity grants admin role; plaintext visible in debug | Password hashing; stronger demo passwords; random expiring server-side sessions; logout invalidation; HttpOnly cookie | Login-specific throttling; TLS when deployed |
| V05 | Tokenless account update | A01 Broken Access Control | Origin on port 8091 posts into port 8080 | Synchroniser CSRF token, Origin check, appropriate SameSite cookie; protect all state changes | Optional request policy; WAF is insufficient alone |
| V06 | Download traversal outside public directory | A01 Broken Access Control | Relative parent path returns private dummy config | Fixed file identifiers/allowlist and canonical containment in downloads | CRS traversal rules |
| V07 | Public `/debug`, detailed exceptions and absent secure headers | A05 Security Misconfiguration | Anonymous request reveals dummy passwords and paths | Remove debug; generic client errors; private diagnostics; CSP, nosniff, frame restrictions, referrer policy | Security headers in Nginx; remove version tokens |
| V08 | Slow report generation with no application/gateway admission limits | A04 Insecure Design | 40 repeated requests accepted; no 429 | Cost bounds, auth quotas, report caching and worker/backlog controls | Nginx rate/connection limits; body/time limits |

## Staged implementation planned for the next phase

1. Preserve this baseline and its evidence before changing source.
2. Fix database queries, output encoding, permissions, authentication, CSRF, downloads and debug settings in the application.
3. Add secure gateway headers and resource controls with measurable response codes (for example, 429 from a configured rate limiter).
4. Add a real ModSecurity/Coraza WAF with OWASP CRS. Record engine/rule versions, blocking mode, triggered rule IDs and audit records. Do not use a string blacklist and call it a WAF.
5. Repeat identical malicious requests and legitimate user workflows. Root-cause fixes must also work on the origin behind the WAF, so filtering does not hide unresolved app flaws.
6. Compare status, latency, request rate, resource measurements and audit logs. Expect different controls to stop different failures; a single WAF is not a complete fix.

Container/fixture safety limits are already present for the local lab and must be disclosed. HTTPS/HSTS requires a real TLS setup; do not claim it from an HTTP-only localhost demo. Local load limiting is not proof of volumetric DDoS resistance.
