#!/usr/bin/env python3
"""Create v2-only passwords and TLS material without touching the original app."""
import json
import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
state = ROOT / "state"
state.mkdir(mode=0o700, exist_ok=True)
credentials = state / "credentials.json"
env_file = ROOT / ".env"
if not credentials.exists():
    values = {name: secrets.token_urlsafe(24) for name in ("admin", "alice", "bob")}
    credentials.write_text(json.dumps(values, indent=2) + "\n")
    credentials.chmod(0o600)
else:
    values = json.loads(credentials.read_text())
if not env_file.exists():
    env_file.write_text("\n".join("PORTAL_" + name.upper() + "_PASSWORD=" + value for name, value in values.items()) + "\n")
    env_file.chmod(0o600)
tls = state / "tls"
tls.mkdir(mode=0o700, exist_ok=True)
if not (tls / "ca.crt").exists():
    ca_config = tls / "ca.cnf"
    ca_config.write_text("""[req]
distinguished_name=dn
x509_extensions=ext
prompt=no
[dn]
CN=LegacyDesk Local CA
[ext]
basicConstraints=critical,CA:TRUE,pathlen:0
keyUsage=critical,keyCertSign,cRLSign
subjectKeyIdentifier=hash
""")
    subprocess.run(["openssl", "req", "-x509", "-nodes", "-newkey", "rsa:3072", "-sha256", "-days", "365",
                    "-keyout", str(tls / "ca.key"), "-out", str(tls / "ca.crt"), "-config", str(ca_config)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    (tls / "ca.key").chmod(0o600)
    config = tls / "openssl.cnf"
    config.write_text("""[req]
distinguished_name=dn
x509_extensions=ext
prompt=no
[dn]
CN=LegacyDesk Local
[ext]
subjectAltName=DNS:localhost,IP:127.0.0.1
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
""")
    subprocess.run(["openssl", "req", "-new", "-nodes", "-newkey", "rsa:3072", "-sha256",
                    "-keyout", str(tls / "server.key"), "-out", str(tls / "server.csr"), "-config", str(config)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    subprocess.run(["openssl", "x509", "-req", "-in", str(tls / "server.csr"), "-CA", str(tls / "ca.crt"),
                    "-CAkey", str(tls / "ca.key"), "-CAcreateserial", "-out", str(tls / "server.crt"),
                    "-days", "90", "-sha256", "-extfile", str(config), "-extensions", "ext"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    (tls / "server.key").chmod(0o600)
print("v2 prepared. Credentials: v2/state/credentials.json (not tracked).")
print("HTTPS: https://127.0.0.1:8443 — certificate signed by v2's local CA.")
