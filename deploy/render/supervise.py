"""Run the app and its gateway together on Render's single public port."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

children = []
stopping = False


def stop(signum, _frame):
    global stopping
    stopping = True
    for child in children:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)


def main():
    port = int(os.environ.get("PORT", "10000"))
    if not 1024 <= port <= 65535:
        raise ValueError("PORT must be an unprivileged TCP port")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    if os.environ["LAB_VERSION"] == "1":
        config = Path("/opt/render-lab/nginx-v1.conf").read_text()
        Path("/tmp/render-nginx.conf").write_text(config.replace("__PORT__", str(port)))
        commands = [[sys.executable, "-u", "app/server.py"],
                    ["nginx", "-c", "/tmp/render-nginx.conf", "-g", "daemon off;"]]
    else:
        commands = [["gunicorn", "--bind=127.0.0.1:8000", "--workers=1", "--threads=2",
                     "--timeout=15", "--backlog=64", "--limit-request-line=2048",
                     "--limit-request-fields=50", "--limit-request-field_size=4096",
                     "--max-requests=1000", "--max-requests-jitter=100", "--umask=0o077",
                     "--no-control-socket", "--preload", "render_wsgi:application"],
                    ["/docker-entrypoint.sh", "nginx", "-g", "daemon off;"]]
    try:
        for command in commands:
            children.append(subprocess.Popen(command, start_new_session=True))
        while not stopping and all(child.poll() is None for child in children):
            time.sleep(0.25)
        failed = any(child.poll() not in (None, 0) for child in children)
    finally:
        stop(signal.SIGTERM, None)
        for child in children:
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
