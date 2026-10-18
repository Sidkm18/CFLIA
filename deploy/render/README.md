# Render deployment

Create two Render web services using the repository root as the Docker build context.

| Version | Dockerfile | Health check |
|---|---|---|
| Original portal | `deploy/render/Dockerfile.v1` | `/health` |
| Hardened portal | `deploy/render/Dockerfile.v2` | `/health` |

For V2, set distinct secret values of at least 20 characters for `PORTAL_ALICE_PASSWORD`, `PORTAL_BOB_PASSWORD`, and `PORTAL_ADMIN_PASSWORD`. Render supplies `RENDER_EXTERNAL_URL`. For local container use, set `PORTAL_PUBLIC_URL` to the exact HTTPS origin instead.

Render terminates HTTPS. The V2 package runs Gunicorn, Nginx, and ModSecurity/OWASP CRS together. SQLite files live inside each service and may reset on sleep, restart, or redeployment.

The optional [external contact form](demo-site/README.md) runs as a separate static site.

V1 also includes a [four-passphrase flag challenge](CHALLENGE.md) at `/challenge`.
The V1 image enables it automatically; V2 is unchanged.
