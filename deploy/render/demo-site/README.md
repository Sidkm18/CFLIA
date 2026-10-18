# External CSRF form on Render

Deploy this directory as a free Render Static Site on the existing deployment
branch. Build command: `true`. Publish directory: `deploy/render/demo-site`.
The site must have its own hostname, distinct from both portal origins.

The two plain HTML forms submit one user-initiated POST each to the fixed,
owned V1/V2 `/account/email` endpoints. They contain no synchroniser token,
password, session identifier, background traffic, external script or analytics.
Each response opens in a separate tab so the original account tabs can be
refreshed to compare actual state.

Sign Alice in to both portals in the same browser profile before testing.
Use a new fictional email for every take. V1's hosted cookie explicitly uses
SameSite=None and Secure. V2 uses SameSite=Strict and rejects a foreign Origin
and missing CSRF token. Browser restrictions must be reported if they prevent
the V1 change; do not claim a redirect to sign-in demonstrates account mutation.

User selected a Render-only demonstration using real hosted checks, excluding
V08. No load test or overload simulation is included. SQLi at the hosted edge
remains a platform-filtered observation, not a successful V1 exploitation claim.
