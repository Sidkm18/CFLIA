# Verified baseline behaviour

- Docker image builds and Compose configuration validation succeeded.
- Nginx configuration validation succeeded; the site is served through Nginx on `127.0.0.1:8080`.
- Python source compiles with the local Python runtime; containers run Python 3.12.
- The confirmed baseline collector observed all eight expected failures. Captures are linked from `BASELINE_REPORT.md`.
- Browser checks confirmed injected sign-in, stored XSS execution, Alice reading Bob's ticket, denied administrator access followed by forged-cookie success, and the separate-origin CSRF account change.
- Browser checks confirmed normal sign-in, ticket creation and saving a normal comment.
- HTTP checks confirmed normal subject search and legitimate handbook download. Escaping outside the entire fixture tree returned 404, preserving the disclosed lab containment boundary.
- Desktop screenshots were inspected. Mobile login, dashboard and ticket views were checked at 390 × 844; after correcting grid overflow, dashboard and ticket page width matched the 390 px viewport.
- Evidence screenshots are under `output/playwright/`; raw requests and baseline measurements are under `output/evidence/`.
- The fictional database is reset for handoff. Saved evidence and logs retain the earlier demonstrations.

Expected error responses (403 for Alice's admin request and 404 for out-of-fixture access) are part of these checks. This phase has no WAF, application hardening or post-hardening evidence. The final seven-minute video has not yet been produced.
