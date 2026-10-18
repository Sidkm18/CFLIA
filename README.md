# LegacyDesk

Employee support portal with a vulnerable Python version and a hardened Flask version. Both use fictional accounts and SQLite data.

## Run

Requires Docker Compose, Python 3, and OpenSSL.

```sh
docker compose up -d --build
python3 v2/scripts/setup.py
docker compose -f v2/compose.yaml up -d --build
```

| Website | Address | Sign-in |
|---|---|---|
| Original portal | http://127.0.0.1:8080 | `alice` / `alice123`, `bob` / `bob123`, `admin` / `admin` |
| Hardened portal | https://127.0.0.1:8443 | Passwords in ignored `v2/state/credentials.json` |
| External contact form | http://127.0.0.1:8091/csrf.html | Uses the original portal session |

V2 uses a local TLS certificate. Accept the browser's certificate exception for localhost. Its setup, gateway, WAF, and app are under [v2](v2/README.md).

## Stop

```sh
docker compose down
docker compose -f v2/compose.yaml down
```

The Render Dockerfiles and hosting configuration are on the [deployment branch](https://github.com/Sidkm18/CFLIA/tree/deploy/render-free-demos).
