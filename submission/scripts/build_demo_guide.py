"""Build the companion demonstration guide; preserve the existing team script."""
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT

ROOT=Path(__file__).resolve().parents[2]
PAGES=[
('Recording plan and setup', r'''
This guide accompanies the existing four-person Team Script. Each member presents two findings with the same sequence: BEFORE -> FIX -> AFTER -> one normal action that still works. The target is seven minutes; rehearse the screen transitions as well as the narration.

## Choose the right environment
For a continuous, controlled demonstration of all eight findings, use the local Docker stacks. For a hybrid recording, use Render for the ordinary portal and most before/after scenes, but use localhost for V01 SQL injection and V08 repeated requests. Keep the environment label visible when switching.

V1 hosted: https://legacydesk-v1-demo.onrender.com

V2 hosted: https://legacydesk-v2-demo.onrender.com

V1 local: http://127.0.0.1:8080

V2 local: https://127.0.0.1:8443

Separate CSRF page: http://127.0.0.1:8091/csrf.html

Hosted deployments were verified on 17 October 2026; these links have not been rechecked for this guide. Free services can take about a minute to wake up and lose their SQLite data on sleep, restart or redeployment. Do not claim that the public V1 SQLi payload succeeds: Cloudflare filtered it in the recorded hosted check.

## Accounts and browser preparation
V1: alice / alice123, bob / bob123, admin / admin. All accounts and data are fictional. For local V2, privately obtain the generated password from v2/state/credentials.json. For hosted V2, obtain PORTAL_ALICE_PASSWORD from the service's Render Environment page. These are different credential sets. Never record either source of credentials.

Use separate browser profiles or private contexts for V1 administrator proof, V1 Alice and V2 Alice. Cookies share a host across ports. Before every scene, check the visible identity and URL. For the local HTTPS site, complete the certificate exception yourself in the dedicated recording browser; do not disable certificate checks globally.

## Start the existing local stacks
```sh
cd /Users/sid/Desktop/NewProjects/CFL_IA_2
docker compose up -d
# First-time setup ONLY, if v2/.env and credentials are absent:
# python3 v2/scripts/setup.py
docker compose -f v2/compose.yaml up -d --build
```
Keep notifications off, zoom readable, credentials hidden, and a fresh screenshot folder ready. Do not reset databases just to prepare a take unless you intend to remove their fictional records.
'''),
('Member 1 | 00:00-01:45 | SQLi and XSS', r'''
## Opening | 00:00-00:10
Say: "This is LegacyDesk, an employee service portal. We kept a vulnerable version and built a separate hardened version. Each member will show two weaknesses, the implemented fix and a retest."

## V01 - SQL injection | 00:10-00:55
Use LOCALHOST for this complete before/after scene. Sign out of V1 and enter the username below; the password is wrong. Preserve the trailing space after the two hyphens.
```text
Username: ' OR 1=1 -- 
Password: wrong
```
BEFORE: V1 selects the administrator account. Hold the administrator name on screen. The weak query joins input into SQL instead of treating it as data.

FIX: Show the login function in v2/app/server.py: a bound username parameter, input validation and password-hash verification. This code is already implemented; do not imply that the complete security stack is being written during the take.

AFTER: Show the recorded local V01 WAF 403 and the direct application test that rejects injected login. A V2 POST requires its own fresh pre-login session, a valid hidden CSRF token and the correct Origin. A tokenless 403 is not SQLi-fix evidence. Use the prepared verifier evidence for this part if reproducing the request manually is inconvenient.

Say: "The original query lets the input change the SQL condition. V2 uses parameterized queries and separate password verification. The WAF adds filtering; the direct tests prove the application fix independently."

Render note: if showing the public V1 403, label it PLATFORM FILTERING. It does not demonstrate a V1 source-code fix. Do not attempt to disable or bypass the provider's protection.

## V02 - Stored XSS | 00:55-01:40
Sign in as Alice and open V1 ticket 1001. Post this harmless comment and reopen the ticket:
```html
<svg onload="this.outerHTML='<p>XSS executed</p>'"></svg>
```
BEFORE: The comment changes into XSS executed. Capture the conversation and URL. No external request or cookie theft is involved.

FIX: Show HTML-context output encoding for comments in v2/app/server.py and the CSP in the gateway. AFTER: submit the same comment through Alice's legitimate V2 comment form. The WAF returns 403; a normal comment must still succeed. The direct origin test separately proves the stored text is encoded rather than executed.

Say: "V1 stores the browser code and runs it when the ticket is viewed. V2 encodes displayed comments, adds CSP, and blocks this payload at the WAF. Normal comments still work."

Handoff | 01:40-01:45: "Member two will show record permissions and session security."
'''),
('Member 2 | 01:45-03:30 | Access and sessions', r'''
## V03 - Broken object access control | 01:45-02:30
Start in a separate Alice session on each version. Open Alice's ticket 1001, then change only the ticket identifier:
```text
/ticket?id=1002
```
BEFORE: V1 shows Bob's confidential payroll ticket while the header still identifies Alice. Keep both identities visible in the screenshot. Do not use an administrator session for this proof.

FIX: Show ticket_for in v2/app/server.py. It checks the ticket owner or administrator role on both reads and comment writes. AFTER: V2 denies Alice access to ticket 1002. Then open ticket 1001 successfully to show normal employee access was preserved.

Say: "Being signed in is not enough. V1 checks the login but misses permission on the chosen record. V2 checks ownership before reading or changing a ticket."

## V04 - Forged identity cookie | 02:30-03:15
As Alice in V1, open /admin and show the denial. In DevTools, open Application or Storage -> Cookies for the V1 origin. Change only user_id from 2 to 1, then reopen /admin.

BEFORE: Administration opens without the administrator password. Only this fictional V1 cookie is safe to show. Restore user_id=2 or sign out immediately after the scene.

FIX: Show new_session, prepare, finish and logout in v2/app/server.py. Explain random session tokens stored by hash, rotation, expiry, invalidation and salted password hashes. Show cookie FLAGS with the value hidden: Secure, HttpOnly and SameSite=Strict.

AFTER: A forged V1 cookie alone must not authenticate to V2. This local request sends only the known dummy identity, not a real V2 session:
```sh
curl -sS --cacert v2/state/tls/ca.crt \
  -H 'Cookie: user_id=1' -o /dev/null \
  -w '%{http_code}\n' https://127.0.0.1:8443/admin
```
Expected: 401. In a genuine Alice V2 browser session, /admin returns 403. These are different boundaries: 401 means no valid session; 403 means a valid user lacks permission. Never replace or disclose a real V2 session token for the demonstration.

Say: "V1 trusts an editable integer as identity. V2 validates an unpredictable server-side session and separately checks the account's permissions."

Handoff | 03:15-03:30: "Authentication establishes the user; authorization decides what that user may access. Next are forged requests and file access."
'''),
('Member 3 | 03:30-05:15 | CSRF and traversal', r'''
## V05 - Cross-site request forgery | 03:30-04:15
Use the LOCAL two-origin browser demonstration. Sign Alice in at http://127.0.0.1:8080, then open http://127.0.0.1:8091/csrf.html in another tab in the same browser context. Record the account's initial email privately or keep it visible in the account tab.

BEFORE: Click Confirm contact details on the separate form. Return to V1 /account and show alice.updated@example.test. The two ports are different origins on the same site. Do not describe this local example as a cross-site cookie bypass.

FIX: Show prepare in v2/app/server.py. Every state-changing form requires an exact allowed Origin and the session-bound CSRF token. SameSite=Strict adds another protection.

AFTER: Use the local verifier's authenticated tokenless request and 403 evidence, followed by the unchanged-email check. The verifier deliberately supplies a valid authenticated cookie, so it proves server rejection even when cookie delivery is assumed. Do not claim the unchanged demo form targets V2: its saved action is V1 only.

Say: "The outside form changes V1 because the endpoint trusts the session without checking request intent. V2 requires both the correct Origin and a matching session-bound token."

## V06 - Path traversal | 04:15-05:00
Show the normal handbook download, then change the V1 URL to:
```text
/download?file=../private/legacy-config.txt
```
BEFORE: V1 returns a private dummy configuration fixture. This exercise is constrained to the fixtures directory; it does not read the machine's real secrets or demonstrate arbitrary host-file access.

FIX: Show download in v2/app/server.py. An exact allowlisted identifier selects a fixed file; the request does not become a filesystem path. Authentication is required.

AFTER: Sign in to V2 as Alice and repeat the filename. Expect 403 from the WAF or 404 from the application allowlist. Then download employee-handbook.txt successfully. Direct application tests prove the allowlist independently of the WAF.

Say: "The original endpoint lets the filename escape the public download directory. V2 maps an approved name to a fixed file, while the WAF adds another filter."

Handoff | 05:00-05:15: "The CSRF control validates a state change; the download allowlist restricts file selection. Member four will cover configuration and resource controls."
'''),
('Member 4 | 05:15-07:00 | Configuration and limits', r'''
## V07 - Exposed debug and missing headers | 05:15-05:55
Open /debug anonymously on V1. Briefly show the fictional account details and internal path. On V2, the same route returns 404 without account data. Inspect Network -> response headers on normal pages and error responses.

FIX: Show the removed debug route, generic error handler and finish in v2/app/server.py, plus the gateway's security headers. On Render, public HTTPS is supplied by the platform; the local stack terminates TLS in its own Nginx gateway.

For a local header-only display without printing the debug response body:
```sh
curl -sS -D - -o /dev/null http://127.0.0.1:8080/debug
curl -sS --cacert v2/state/tls/ca.crt -D - -o /dev/null \
  https://127.0.0.1:8443/debug
```
Expect CSP, nosniff and frame restrictions in V2. Header names are case-insensitive. Never show V2 credential files, environment values, private keys or cookie/token values.

Say: "V1 exposes unnecessary diagnostics. V2 removes the endpoint, uses generic errors and adds browser security policies, including on error responses."

## V08 - Repeated expensive requests | 05:55-06:40
LOCALHOST ONLY. Keep the full bounded 40-request, four-worker test off Render. Use the saved comparison for the seven-minute recording, or run these scripts before the take and show their actual result files:
```sh
python3 scripts/probe_baseline.py
# Allow at least 60 seconds between complete V2 quota runs.
python3 v2/scripts/verify_stack.py
```
The baseline script changes Alice's fictional email and adds a harmless XSS comment. The V2 verifier creates one normal verification comment. These are test mutations, not read-only checks.

BEFORE: The captured 15 October local run accepted 40 of 40 reports. FIX: show Nginx request/connection limits, report quotas, cache and bounded workers. AFTER: the saved V2 run produced 5 HTTP 200 and 35 HTTP 429 responses. Those are historical observed counts, not a promise for a new run. Display the counts actually produced; warm quotas can change them.

Say: "The local batch shows admission control. V1 accepts the repeated work; V2 limits requests and caches permitted reports. Faster rejection is not proof of complete DoS or DDoS protection."

## Closing | 06:40-07:00
Say: "The local comparison covers eight findings. Nineteen direct application tests and seventeen local deployed-stack checks passed in the saved verification. Application fixes, WAF rules and traffic controls work together while normal employee actions remain available."

If using the hybrid recording, add: "The public demos have platform constraints, including SQLi filtering and disposable databases. The full controlled experiment remains local."
'''),
('Evidence, rehearsal and troubleshooting', r'''
## Keep the evidence sets distinct
Local final security capture: 15 October 2026. All eight original findings observed; 19 direct application tests and 17 local deployed-stack checks passed. The saved report comparison is 40/0 before and 5/35 after (HTTP 200/429), using 40 requests and four workers.

Render deployment capture: 17 October 2026. Both sites were live; 25 bounded HTTP checks passed and one V1 SQLi scene was platform-filtered. These are different checks from the 17 local integration checks. Real hosted V2 audit logs included OWASP CRS 4.30.0 rule 941100 for XSS. Do not label all HTTP 403 responses as WAF blocks without audit evidence.

## Useful files and commands
Spoken script: submission/TEAM_SCRIPT.md; shareable exports are output/pdf/CFLIA_Team_Script.pdf and output/documents/CFLIA_Team_Script.docx. The full script assigns exactly two findings per speaker.

Local comparison: submission/evidence/comparison.json. Saved HTTP screenshots and browser captures: output/playwright/final/. Local final result: v2/output/verification-20261015T070630Z/results.json. Hosted results and screenshots: output/render-deployment/.

```sh
docker compose -f v2/compose.yaml exec -T app \
  python -m unittest discover -s tests -v
# Bounded hosted checks; includes harmless V1 test mutations:
python3 deploy/render/verify_hosted.py
```
The hosted script sends only one V1 report request and performs no load test. Do not redirect either local load script to a hosted service. Render permits testing owned services but prohibits DoS testing of customer environments. Reference: https://render.com/docs/penetration-testing

## Before pressing Record
1. Wake both hosted services if used; confirm local health and valid V2 sign-in.
2. Verify the identity before each scene; restore Alice after any forged-admin proof.
3. Prepare each payload and the relevant V2 function in a readable editor.
4. Keep one normal positive control for each feature; a denial alone is incomplete evidence.
5. Hide notifications, unrelated tabs, passwords, private keys and real session tokens.
6. Rehearse handoffs at 01:45, 03:30, 05:15 and 07:00. Leave brief readable holds.
7. Label saved evidence with its date and environment. Never present old output as a fresh live run.

## If a scene fails
SQLi blocked on Render: use the local V1 scene and disclose the platform filter. V2 POST rejected unexpectedly: refresh its form/session and check Origin plus CSRF token. 429 during rehearsal: wait at least 60 seconds. Local HTTPS warning: complete the exception manually in the dedicated browser. Hosted cold start: wake the site before recording. A changed account or missing comment after sleep: the free database reset; sign in again and repeat only your intended test.

After recording, remove only your own demo records if needed; preserve unrelated data. Watch the exported seven-minute video end to end. The saved silent walkthrough is source footage, not a completed narrated team recording.
''')]

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='GuideTitle',fontName='Helvetica-Bold',fontSize=19,leading=23,textColor=colors.HexColor('#173d34'),spaceAfter=12))
styles.add(ParagraphStyle(name='GuideH',fontName='Helvetica-Bold',fontSize=11,leading=14,textColor=colors.HexColor('#173d34'),spaceBefore=9,spaceAfter=5,keepWithNext=True))
styles.add(ParagraphStyle(name='GuideBody',fontName='Helvetica',fontSize=9.2,leading=12.6,spaceAfter=7))
styles.add(ParagraphStyle(name='GuideCode',fontName='Courier',fontSize=8,leading=10.3,backColor=colors.HexColor('#eef3f0'),borderPadding=7,spaceBefore=4,spaceAfter=9))
flow=[]
md=['# LegacyDesk demonstration guide','','Prepared 18 October 2026. Companion to the existing four-person Team Script.','']
for idx,(title,content) in enumerate(PAGES):
    if idx:flow.append(PageBreak())
    display_title = escape(title)
    if title.startswith('Member '):
        speaker, topic = title.rsplit(' | ', 1)
        display_title = escape(speaker) + '<br/><font size="14">' + escape(topic) + '</font>'
    flow.append(Paragraph(display_title,styles['GuideTitle']))
    md += ['## '+title,'',content.strip(),'']
    in_code=False; code=[]; para=[]
    def flush():
        if para:
            flow.append(Paragraph(escape(' '.join(para)),styles['GuideBody']));para.clear()
    for line in content.strip().splitlines()+['']:
        if line.startswith('```'):
            flush()
            if in_code:
                flow.append(Preformatted('\n'.join(code),styles['GuideCode']));code=[]
            in_code=not in_code;continue
        if in_code:code.append(line);continue
        if line.startswith('## '):flush();flow.append(Paragraph(escape(line[3:]),styles['GuideH']))
        elif re.match(r'\d+\. ',line):
            flush();flow.append(Paragraph(escape(line),styles['GuideBody']))
        elif not line.strip():flush()
        else:para.append(line)

def footer(c,d):
    c.setStrokeColor(colors.HexColor('#c9d8cf'));c.line(42,40,553,40)
    c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#52675d'))
    c.drawString(42,27,'LEGACYDESK  |  Demonstration guide  |  18 October 2026')
    c.drawRightString(553,27,str(d.page))

out=ROOT/'output/pdf/CFLIA_Demonstration_Guide.pdf';out.parent.mkdir(parents=True,exist_ok=True)
SimpleDocTemplate(str(out),pagesize=(595.28,841.89),rightMargin=42,leftMargin=42,topMargin=37,bottomMargin=52,title='LegacyDesk Demonstration Guide',author='LegacyDesk project team').build(flow,onFirstPage=footer,onLaterPages=footer)
(ROOT/'submission/DEMONSTRATION_GUIDE.md').write_text('\n'.join(md)+'\n')
print(out)
