FROM python:3.12-slim
WORKDIR /srv/legacydesk
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home portal && mkdir -p state && chown portal:portal state
COPY app app
USER portal
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORTAL_STATE=/srv/legacydesk/state
EXPOSE 8000
CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=2", "--threads=2", "--backlog=64", "--limit-request-line=2048", "--limit-request-fields=50", "--limit-request-field_size=4096", "--timeout=15", "--graceful-timeout=5", "--max-requests=1000", "--max-requests-jitter=100", "--umask=0o077", "--no-control-socket", "--preload", "app.server:create_app()"]
