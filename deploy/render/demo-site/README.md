# External contact form

Deploy this directory as a Render static site:

- Branch: `deploy/render-free-demos`
- Build command: `true`
- Publish directory: `deploy/render/demo-site`

The hostname must differ from the two portal origins. The forms in `index.html` use the existing portal URLs; update their links and form actions if the portal hostnames change.

Sign in to the selected portal in the same browser before submitting an email change. Each button sends one form submission. The original portal accepts the update; V2 checks CSRF tokens, Origin, and its session cookie policy.
