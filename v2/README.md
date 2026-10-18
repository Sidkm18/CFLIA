# LegacyDesk v2

Flask portal with server-side sessions, CSRF and ownership checks, HTTPS, request limits, and a ModSecurity WAF using OWASP CRS.

From this directory:

```sh
python3 scripts/setup.py
docker compose up -d --build
```

Open https://127.0.0.1:8443. Setup generates passwords for `alice`, `bob`, and `admin` in ignored `state/credentials.json`, writes `.env`, and creates the local TLS certificate. Accept the browser's certificate exception for localhost.

HTTP on port 8082 redirects to HTTPS. The app and WAF have no published origin ports. Records are stored in a separate Docker volume from the original portal.

To stop:

```sh
docker compose down
```
