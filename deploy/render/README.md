# Render free demonstration deployments

## Current Render-only recording (2026-10-18)

Use [the Render-only guide](../../submission/RENDER_ONLY_DEMONSTRATION_GUIDE.md)
for the current browser-only presentation. The separate external form and
downloadable guide are at https://legacydesk-csrf-demo.onrender.com. Its Render
static-site ID is `srv-dbabemgm7kps73872ltg`; it deploys independently of the two
portal services. V1 accepted its external account-update form in a browser;
V2 rejected the form and retained its existing account email after refresh.

The user excluded V08 entirely. This presentation covers V02-V07; V01 remains
a previously platform-filtered observation. Historical local instructions and
results below are not part of this Render-only recording.

## Live services (verified 2026-10-17)

| Version | Public URL | Render service |
|---|---|---|
| V1 intentionally vulnerable | https://legacydesk-v1-demo.onrender.com | `srv-db9ohtqjnfac73d2ekl0` |
| V2 patched with WAF | https://legacydesk-v2-demo.onrender.com | `srv-db9oi73ncjis73a3m9r0` |

Both services deployed commit `8330f02c79299a5a16f9cb63c7fc78d33415abf3`
from branch `deploy/render-free-demos`, in separate Render projects, on Free
compute in Singapore. Automatic deployment is disabled. The user explicitly
approved publication of V1's intentional vulnerabilities and generation of
V2's initial credentials in Render.

V1 accepts its original fictional accounts, including `alice` / `alice123`.
V2 uses three distinct 32-character passwords generated in Render. Retrieve
them in the V2 service's **Environment** page; they are not in Git, image layers,
logs or this document. Existing local credentials were not uploaded.

**Hosted limitation:** Cloudflare blocks the standard SQL-injection login payload
at its edge with HTTP 403 before it reaches V1. This is a platform mitigation;
the unchanged V1 application is still vulnerable in the independently verified
local container. Do not claim that this payload succeeds on the public URL.
Render's public TLS and edge protections also differ from the local baseline.
Keep the local stacks for a controlled demonstration of every original finding.

Bounded live HTTP checks: **25 passed, one platform-filtered**. Browser checks
confirmed successful sign-in on both versions, V1 access to Bob's ticket as
Alice versus V2 denial, execution of the harmless stored XSS marker on V1,
successful normal comments on V2, and rejection of the XSS comment on V2.
Hosted V2 audit logs recorded CRS 4.30.0 rule IDs 941100, 941120, 941160 and
949110. No hosted load test was performed. Detailed redacted evidence lives
under the repository's local `output/render-deployment/` directory.

`python3 deploy/render/verify_hosted.py` repeats the bounded HTTP checks. It
does not need V2 passwords, saves no cookies/tokens or response bodies, and
writes only a harmless V1 comment and a fictional account email update.

These deployment overlays leave the original local V1 and V2 stacks unchanged.
Use the repository root as the Docker build context and select
`deploy/render/Dockerfile.v1` or `deploy/render/Dockerfile.v2` in two separate
Render Free web services. Set the health check path to `/health`.

V1 packages the original application behind a basic Nginx proxy. Its intentional
SQL injection, stored XSS, IDOR, forged identity cookies, CSRF, fixture-bounded
traversal, debug output and unbounded report work remain. Render adds public
HTTPS and platform protection. The hosted identity cookie explicitly uses
`SameSite=None; Secure` so the tokenless update can be demonstrated cross-site;
its unsigned identity and lack of HttpOnly remain intentional.

V2 packages the existing Flask application and the pinned ModSecurity/OWASP CRS
image in one container, retaining blocking mode, secure headers, quotas,
ownership, CSRF and session controls. Render terminates public TLS. Gunicorn
listens only on loopback. The local TLS certificate and keys are not uploaded.
One Gunicorn worker with two threads fits the free memory budget more closely
than the original separate containers. Container-network separation and local
Compose resource caps are not reproduced inside this combined container.

V2 requires three distinct strong Render secret environment variables:
`PORTAL_ALICE_PASSWORD`, `PORTAL_BOB_PASSWORD`, `PORTAL_ADMIN_PASSWORD` (at least
20 characters each). Render supplies `RENDER_EXTERNAL_URL`; for local container
checks set `PORTAL_PUBLIC_URL=https://localhost`. Passwords must not be committed
or placed in image layers. Existing local credentials are not uploaded.

The gateway replaces forwarding headers. IP quotas conservatively use its peer
address; users behind the same Render edge peer can share those quotas. User
quotas remain separate. Do not claim globally distributed per-client rate limits.

**SQLite state is disposable.** Render Free loses local files on sleep, restart
and redeployment. Each version seeds its own database; records, sessions and
quota/cache state reset together. The user explicitly accepted these resets.
The original persistent local databases are not copied into the images.

Render Free services share 750 running hours per workspace per month and sleep
after inactivity. Two continuously running services would exceed that allowance.
These are occasional demonstration services, not permanent production hosting.

Only bounded functional/security checks belong on the hosted services. Keep
the V08 load probe local: Render prohibits DoS testing of customer environments.

References checked 2026-10-17:
- https://render.com/docs/free
- https://render.com/docs/docker
- https://render.com/docs/penetration-testing

The live status and URLs above were recorded after Render reported successful
deployments and direct HTTPS/browser checks completed.

## Local package verification

On 2026-10-17, both images built and ran with a 512 MB memory cap. The bounded
`python3 deploy/render/verify_local.py` run passed 23/23 checks, including V1
flaw preservation, V2 legitimate sign-in, secure cookies, denial of IDOR/CSRF/
traversal and real CRS SQLi/XSS blocks. It sends only one V1 report request.
The existing direct application suite passed all 19 tests inside the new V2
image. Nginx configuration validation passed; ModSecurity loaded 856 rules.
Observed rule IDs included 941100 (XSS), 942100 (SQLi), and 930110/930120
(traversal). Approximate idle memory after checks was 32 MB (V1) and 77 MB (V2).
These results were obtained on local ARM64 Docker, not Render's live AMD64
runtime. The pinned WAF manifest includes both architectures.
