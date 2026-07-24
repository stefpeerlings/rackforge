FROM python:3.12-slim

# license.py shells out to the `openssl` CLI to verify Ed25519-signed license
# keys (no pip dependency) — must be present in the image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 rackforge \
    && mkdir -p /data \
    && chown rackforge:rackforge /data

WORKDIR /app
COPY server.py admin_panel.py email_templates.py google_oauth.py license.py ./

ENV RACKFORGE_HOST=0.0.0.0 \
    RACKFORGE_PORT=8080 \
    RACKFORGE_DB=/data/plans.db \
    RACKFORGE_AVATAR_DIR=/data/avatars

EXPOSE 8080
VOLUME ["/data"]

USER rackforge

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python3 -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8080/api/health', timeout=2)" || exit 1

CMD ["python3", "server.py"]
