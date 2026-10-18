"""Render-specific host/origin and proxy settings; local v2 stays unchanged."""
import os
from urllib.parse import urlsplit

from werkzeug.middleware.proxy_fix import ProxyFix

from app.server import create_app

public_url = os.environ.get("RENDER_EXTERNAL_URL", os.environ.get("PORTAL_PUBLIC_URL", ""))
parsed = urlsplit(public_url)
if parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password:
    raise RuntimeError("Configure an exact HTTPS RENDER_EXTERNAL_URL or PORTAL_PUBLIC_URL")
origin = public_url.rstrip("/")
application = create_app({
    "ORIGINS": {origin},
    "TRUSTED_HOSTS": [parsed.hostname, "localhost", "127.0.0.1"],
})
# The sole local gateway REPLACES all client-supplied forwarding headers.
# Its peer address is used conservatively: Render edge peers can share quotas.
application.wsgi_app = ProxyFix(application.wsgi_app.app, x_for=1, x_proto=1)
