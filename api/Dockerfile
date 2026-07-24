# Build context is the repo root (see docker-compose.yml) so this can pick
# up the static frontend files alongside the Python API.
FROM python:3.12-slim

# license.py shells out to the `openssl` CLI to verify Ed25519-signed license
# keys, and server.py uses it to generate a self-signed TLS cert — both
# avoid a pip dependency.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 rackforge \
    && mkdir -p /data \
    && chown rackforge:rackforge /data

WORKDIR /app
COPY api/server.py api/admin_panel.py api/email_templates.py api/google_oauth.py api/license.py ./
COPY index.html login.html main.html settings.html privacy.html terms.html verify-email.html reset-password.html static/
COPY css/ static/css/
COPY js/ static/js/
COPY icons/ static/icons/

ENV RACKFORGE_HOST=0.0.0.0 \
    RACKFORGE_PORT=8080 \
    RACKFORGE_DB=/data/plans.db \
    RACKFORGE_AVATAR_DIR=/data/avatars \
    RACKFORGE_STATIC_DIR=/app/static

EXPOSE 8080
VOLUME ["/data"]

USER rackforge

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python3 -c "import ssl, urllib.request as u; u.urlopen('https://127.0.0.1:8080/api/health', timeout=2, context=ssl._create_unverified_context())" || exit 1

CMD ["python3", "server.py"]
