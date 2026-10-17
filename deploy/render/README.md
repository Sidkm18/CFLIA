# Render free demonstration deployments

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

Deployment status and final URLs must be recorded only after Render confirms
successful builds and live HTTP/browser checks pass.

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
