# Re-testing the two versions

Leave v1 on `http://127.0.0.1:8080` and v2 on `https://127.0.0.1:8443`. Use separate tabs and the correct passwords for each. V2 retains the same portal appearance; identify versions using the address bar in the recording.

| ID | Repeated request | Expected v2 result | Root-cause evidence |
|---|---|---|---|
| V01 | Login username `' OR 1=1 -- `, any wrong password | 403 from WAF; no admin session | With a valid v2 CSRF token and the WAF bypassed in tests, login rejects input and search treats SQL text literally |
| V02 | Comment `<svg onload="this.outerHTML='<p>XSS executed</p>'"></svg>` | WAF 403; the comment is not stored at the edge | Direct app tests store it as text and verify HTML encoding; browser origin-proof screenshot shows literal text without an SVG element |
| V03 | As Alice, open `/ticket?id=1002` or comment on ticket 1002 | 403; Bob's content is absent | The handler checks ownership for both reads and writes; Bob/admin can access as authorised |
| V04 | Send `Cookie: user_id=1` to `/admin` | 401; v1 cookie ignored | Random session hashes, password-hash checks, expiry and logout-reuse tests |
| V05 | Send an account-update POST from origin `http://127.0.0.1:8091` without a token | 403; account unchanged | Tests also reject a correct token with a wrong Origin and a missing/wrong token with the right Origin |
| V06 | `/download?file=../private/legacy-config.txt` | WAF 403 or app 404; no file content | Direct origin tests cover relative, encoded and absolute paths; handbook still downloads |
| V07 | Anonymous `/debug`; inspect response headers | 404 with no credentials; secure headers present | Error-header checks cover 400/401/403/404/405/413/429 |
| V08 | 40 `/reports/export` requests using four workers and a valid session | Mixture of accepted reports and 429; bounded work | Direct app tests enforce six reports/minute atomically, including concurrent requests; edge has separate throttling |

Use `python3 scripts/verify_stack.py` for one reproducible integration run. It trusts only the generated local CA for the HTTPS target, saves no passwords/tokens and records actual response outcomes. Allow the quota window to expire before repeating. Individual UI retests need the hidden CSRF token provided by that v2 page; otherwise a 403 may demonstrate CSRF rejection rather than the intended SQL/XSS/permission check.

For a browser CSRF recording, host the original `demos/csrf.html` unchanged on port 8091 and use an intercepting tool to change only its target to v2's account-update URL. The v1 page itself is preserved. A Secure/Strict v2 cookie and the application token/Origin checks prevent the forged write. The saved integration evidence exercises the same request with an authenticated cookie deliberately supplied, proving the server rejects it even when cookie delivery is assumed.

Capture the v2 address, user identity, failed operation and relevant status/log entry. WAF failures may be a generic Nginx 403 page; pair that screenshot with the CRS rule IDs in the saved verification result. Do not infer business-logic protection from a WAF 403 alone: the direct tests establish ownership, session and CSRF enforcement.

Suggested seven-minute edit: 30 seconds architecture/scope, 2 minutes original failures, 1 minute application and gateway changes, 2.5 minutes repeated requests and valid use, 1 minute measured outcomes and limits. Full payloads and screenshots belong in the report.
