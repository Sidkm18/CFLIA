# Recreate LegacyDesk / CFLIA

Archive prepared on 7 November 2026. This checkout combines the published application and deployment code with the local coursework reports, evidence, guides and document builders. Captures describe their original October runs; archiving them does not establish current hosted service health.

## Start from a fresh clone

Requires Git, Docker with Compose v2, Python 3 and OpenSSL. Docker must be running. The hardened service downloads its pinned dependencies and WAF image during the build.

```sh
git clone https://github.com/Sidkm18/CFLIA.git
cd CFLIA
docker compose up -d --build
python3 v2/scripts/setup.py
docker compose -f v2/compose.yaml up -d --build
```

- Vulnerable portal: http://127.0.0.1:8080 — fictional accounts `alice` / `alice123`, `bob` / `bob123`, `admin` / `admin`.
- External CSRF form: http://127.0.0.1:8091/csrf.html.
- Hardened portal: https://127.0.0.1:8443 — newly generated passwords in `v2/state/credentials.json`. The browser needs a localhost certificate exception. See [v2/README.md](v2/README.md).

Application fixtures recreate the fictional data when the database is initialized. Local database contents, active sessions, passwords, `.env`, TLS private keys and Docker volumes are intentionally excluded. `setup.py` creates fresh secrets and TLS material; a new clone does not restore old sessions or edited database records. Do not copy credentials out of historical HTTP examples for the hardened service.

## Verify the rebuilt lab

```sh
docker compose -f v2/compose.yaml exec -T app python -m unittest discover -s tests -v
python3 v2/scripts/verify_stack.py
```

The integration verifier writes a normal comment and sends a bounded request batch. Wait at least 60 seconds between full runs. See [v2/docs/RETEST_GUIDE.md](v2/docs/RETEST_GUIDE.md), [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md), [docs/V08_ONLY_DEMO.md](docs/V08_ONLY_DEMO.md) and [docs/V08_CAPACITY_DEMO.md](docs/V08_CAPACITY_DEMO.md) for demonstration procedures and limits.

## Files preserved

| Path | Contents |
|---|---|
| `app/`, `infra/`, `compose.yaml`, `Dockerfile` | Vulnerable portal, fictional fixtures and local gateway |
| `v2/` | Hardened portal, templates, pinned dependencies, tests, WAF/gateway configuration and setup scripts |
| `deploy/render/` | Render Dockerfiles, gateway configuration, verification scripts, deployment instructions and external form site |
| `demos/`, `scripts/`, `docs/` | Demonstration code, evidence collectors and technical documentation |
| `submission/` | Report/script Markdown, recording guides, document builders and supporting evidence |
| `output/documents/`, `output/pdf/` | Recovered Word/PDF report exports and team script |
| `output/`, `v2/output/` | Saved screenshots, HTTP results, runtime metadata |

The main and editable report exports were recovered byte-for-byte from `tmp/report-screenshots-20261018T150134253075Z/`, the latest complete report backup found. The team-script exports were recovered from local Git history. The Word/PDF files are archived without changes. Use `ARCHIVE_SHA256SUMS` to verify the archived bytes. Some older text guides describe earlier revisions; use the included exports for the archived report layout.

## Full historical backup

The cleaned main branch retains the source, final documents and referenced evidence. Repeated test captures, the duplicate baseline source ZIP and historical report QA records remain available in [archive/full-backup-2026-11-07](https://github.com/Sidkm18/CFLIA/tree/archive/full-backup-2026-11-07).

To extract the original vulnerable-stage ZIP from that backup:

```sh
git show archive/full-backup-2026-11-07:output/legacydesk-vulnerable-baseline.zip > ../legacydesk-vulnerable-baseline.zip
```

Separate local-main, Render-demo and passphrase-challenge histories are also preserved under the repository's `archive/` tags.

## Documents and hosting

Use [submission/README.md](submission/README.md) for document builders. Rebuilding Word files requires `python-docx` and Pillow; scripts may also need local fonts and an external PDF conversion/rendering tool. Existing exports can be read without rebuilding. Temporary preview pages, browser caches and Office lock files are omitted.

Render recreation is documented in [deploy/render/README.md](deploy/render/README.md) and [deploy/render/demo-site/README.md](deploy/render/demo-site/README.md). Recreate hosting secrets through the provider; historical URLs and screenshots are evidence, not a guarantee that hosted services are still available. The deployment files are included on `main` in this archive.

To stop both local stacks without deleting their volumes:

```sh
docker compose down
docker compose -f v2/compose.yaml down
```

Container tags and host tooling may change over time. Recorded image metadata and the pinned v2 requirements are preserved, but a fresh full-stack rebuild should be verified on the target machine.
