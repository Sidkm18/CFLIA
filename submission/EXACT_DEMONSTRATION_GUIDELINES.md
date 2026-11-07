# LegacyDesk: exact demonstration guidelines

Use this recording sequence: **show V1 failing -> explain the fix -> repeat on V2 -> show a normal action still working.**

Use **localhost for V01 and V08**. Use the deployed websites for V02-V07.

## 1. Prepare everything before recording

Open these tabs:

| Purpose | Address |
|---|---|
| Deployed V1 | https://legacydesk-v1-demo.onrender.com |
| Deployed V2 | https://legacydesk-v2-demo.onrender.com |
| Local V1 | http://127.0.0.1:8080 |
| Local V2 | https://127.0.0.1:8443 |
| Separate CSRF form | http://127.0.0.1:8091/csrf.html |

Start the existing local stacks:

```bash
cd /Users/sid/Desktop/NewProjects/CFL_IA_2
docker compose up -d
docker compose -f v2/compose.yaml up -d
```

- On V1, sign in with **alice / alice123**.
- On deployed V2, use alice and its generated password from Render's Environment page: https://dashboard.render.com/web/srv-db9oi73ncjis73a3m9r0/env
- Local V2 uses the separate credentials in v2/state/credentials.json.
- Retrieve passwords before recording; hide passwords and real session-cookie values.
- Use a separate private browser window for the local V1 administrator demonstration.
- Open DevTools -> Network, enable Preserve log, and clear the request list before each scene.

Keep v2/app/server.py and v2/infra/gateway.conf ready for brief fix explanations. Paths in this guide are relative to the project directory shown above.

For a local HTTPS certificate warning, complete the exception manually in your dedicated recording browser. Do not disable certificate verification globally.

These are recording instructions, not a fresh verification run. The earlier hosted checks were captured on 17 October 2026. Wake the free Render services before the take; their databases and sessions can reset after sleep or restart.

<!-- PAGE -->

## 2. V01 - SQL injection: use localhost

### V1 demonstration
1. Open local V1 /login in your separate private window.
2. Enter the values below. Keep a space after the two hyphens in the username.

```text
Username: ' OR 1=1 -- 
Password: wrong
```

3. Click Sign in.
4. Show the resulting Portal Administrator identity.

**Say:** "V1 inserts the username directly into SQL. This input changes the query condition and allows administrator login without the correct password."

### V2 retest
1. Sign out of local V2 if already authenticated.
2. Open its /login page.
3. Submit the same username and wrong password through its normal form.
4. Show the rejected request in Network. Expect 403 from the WAF, or 400 if rejected by application validation. Administrator access must not be granted.
5. Show the login function: parameterized lookup and separate password-hash verification.
6. Sign in normally as Alice to demonstrate legitimate login.

**Do not use the deployed V1 rejection as the vulnerable before result.** Our hosted check found Cloudflare filtered this payload before it reached V1.

## 3. V02 - Stored XSS: use the deployed websites

### V1 demonstration
1. Sign in as Alice.
2. Open https://legacydesk-v1-demo.onrender.com/ticket?id=1001
3. Paste this into Add a comment:

```html
<svg onload="this.outerHTML='<p>XSS executed</p>'"></svg>
```

4. Click Post comment.
5. Reload the ticket.
6. Show XSS executed in the conversation.

**Say:** "The comment is stored and later interpreted as browser code. This harmless example changes its own displayed content."

### V2 retest
1. Open V2 ticket 1001 while signed in as Alice.
2. Submit the identical comment through its normal form.
3. Show 403 Forbidden.
4. In V2's Render logs, search for 941100 to identify the XSS WAF rule. Logs: https://dashboard.render.com/web/srv-db9oi73ncjis73a3m9r0/logs
5. Return to the ticket and submit: Normal demonstration comment.
6. Show that this ordinary comment succeeds.

Explain output encoding, CSP and WAF filtering. Direct application tests establish encoding independently of the WAF.

<!-- PAGE -->

## 4. V03 - IDOR: use the deployed websites

1. Confirm both headers identify Alice Morgan.
2. Open V1 ticket 1001, then change only the identifier to:

```text
https://legacydesk-v1-demo.onrender.com/ticket?id=1002
```

3. Show Alice's identity and Bob's ticket ownership/payroll details together.
4. Repeat on V2:

```text
https://legacydesk-v2-demo.onrender.com/ticket?id=1002
```

5. Show Access unavailable and HTTP 403.
6. Open V2 ticket 1001 again to prove Alice can access her own ticket.

**Say:** "V1 checks that Alice is signed in but misses permission on the selected ticket. V2 checks ownership or administrator permission."

Show the ticket_for function as the fix.

## 5. V04 - Forged sessions: use the deployed websites

### V1 demonstration
1. While signed in as Alice, visit V1 /admin. Show 403.
2. Open DevTools -> Application -> Cookies -> the V1 website.
3. Find user_id.
4. Change its value from 2 to 1.
5. Reload /admin.
6. Show that administration now opens.
7. Restore user_id to 2 or sign out and sign back in as Alice.

### V2 retest
In Terminal, send only the same fictional V1 cookie:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -H 'Cookie: user_id=1' \
  https://legacydesk-v2-demo.onrender.com/admin
```

Expected: **401**.

Then visit V2 /admin in your genuine Alice browser session. Expected: **403**.

**Say:** "The forged cookie does not establish a V2 session. A genuine Alice session is valid, but still lacks administrator permission."

Show new_session, session validation and cookie flags. Keep the real V2 token value hidden.

<!-- PAGE -->

## 6. V05 - CSRF: deployed targets with the separate local form

The existing demo form initially targets local V1, so change its target explicitly for this hosted demonstration.

### V1 demonstration
1. Sign in to deployed V1 as Alice.
2. Open /account and note the current email.
3. In another tab in the same browser profile, open:

```text
http://127.0.0.1:8091/csrf.html
```

4. Right-click Confirm contact details -> Inspect.
5. In Elements, locate the enclosing form.
6. Double-click its action value and replace it with:

```text
https://legacydesk-v1-demo.onrender.com/account/email
```

7. Enter an email different from the current one, for example:

```text
csrf.demo@example.test
```

8. Click Confirm contact details.
9. Return to V1's original /account tab and refresh.
10. Show the changed email.

### V2 retest
1. Confirm you are signed in to deployed V2 and note its current email.
2. Reopen the separate form.
3. Change its action to:

```text
https://legacydesk-v2-demo.onrender.com/account/email
```

4. Submit another distinct email.
5. Expect 403.
6. Refresh the original V2 account tab and show that its email is unchanged.

**Say:** "V1 accepts the outside account-update request. V2 requires an allowed Origin and a session-bound CSRF token, with Strict cookies providing another layer."

This particular hosted browser-form sequence still needs a rehearsal; the earlier hosted verification checked the requests programmatically. If browser cookie restrictions prevent the V1 change, use the verified local form demonstration rather than claiming success.

For that local fallback, use the original form target and sign Alice in at http://127.0.0.1:8080. The form on port 8091 and portal on port 8080 are different origins on the same site. For the local V2 server-side rejection, use the saved verifier evidence: it deliberately supplies an authenticated cookie with an invalid Origin and no token.

<!-- PAGE -->

## 7. V06 - Path traversal: use the deployed websites

1. On V1, first demonstrate the normal handbook.
2. Then open:

```text
https://legacydesk-v1-demo.onrender.com/download?file=../private/legacy-config.txt
```

3. Show the returned dummy configuration fixture.
4. While signed in to V2, open:

```text
https://legacydesk-v2-demo.onrender.com/download?file=../private/legacy-config.txt
```

5. Show 403 or 404, without configuration contents.
6. Open the normal V2 handbook:

```text
https://legacydesk-v2-demo.onrender.com/download?file=employee-handbook.txt
```

**Say:** "V1 allows the requested filename to escape the public download directory into a private fixture. V2 selects only an explicitly allowed file."

Show the download allowlist. Describe this as fixture disclosure, not access to the server's real secrets.

## 8. V07 - Debug exposure and missing headers

Use the deployed websites.

1. Open V1 /debug.
2. Briefly show the fictional account/password details.
3. Open V2 /debug.
4. Show 404 and the absence of account data.
5. In DevTools -> Network, select the V2 request -> Headers.
6. Show these headers:

```text
Content-Security-Policy
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security
```

7. Compare with V1's response. Header names are case-insensitive.

**Say:** "V2 removes public diagnostics and adds browser security headers, including on error responses."

Do not describe deployed V1 as HTTP-only: Render provides HTTPS to both websites.

<!-- PAGE -->

## 9. V08 - Repeated expensive requests: localhost only

Keep this scene local. Render expressly prohibits DoS testing, including customer-hosted environments. Policy: https://render.com/docs/penetration-testing

From the project directory:

```bash
python3 scripts/probe_baseline.py
```

Show the generated baseline result's requests (40), concurrency (4) and status_counts.

Then, allowing at least 60 seconds since the previous complete V2 quota run:

```bash
python3 v2/scripts/verify_stack.py
```

Show the new V2 result's status counts and the V08 expensive requests throttled check.

The saved historical comparison was:

| Local version | HTTP 200 | HTTP 429 |
|---|---|---|
| V1 | 40 | 0 |
| V2 | 5 | 35 |

Use the actual counts from your new run. Do not promise the same split, because existing quota state affects it.

**Say:** "V1 accepts repeated report work. V2 adds request limits, account quotas and caching. This bounded experiment demonstrates admission control, not complete DDoS resistance."

Both scripts create small amounts of fictional demonstration data; run this scene last.

## 10. Close the presentation

Use this speaker order:

| Time | Speaker | Findings |
|---|---|---|
| 00:00-01:45 | Member 1 | SQL injection and XSS |
| 01:45-03:30 | Member 2 | IDOR and forged sessions |
| 03:30-05:15 | Member 3 | CSRF and traversal |
| 05:15-07:00 | Member 4 | Misconfiguration and resource controls |

End with:

"We fixed the application and added supporting security layers. The demonstrations show the difference between authentication, authorization, input handling, browser protections and traffic controls. The complete eight-finding experiment runs locally; the public demos have hosting-platform limitations."

Label every screen LOCAL or RENDER, and every saved result with its capture date.
