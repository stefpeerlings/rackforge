#!/bin/bash
# Eenmalig op de server: SQLite API + systemd service + Caddy proxy
set -euo pipefail

API_DIR="/home/stef/rackforge"
SERVICE="/etc/systemd/system/rackforge-api.service"
SUDOERS="/etc/sudoers.d/stef-caddy"

echo "=== RackForge API setup ==="

mkdir -p "$API_DIR"
chmod 755 "$API_DIR"

if [ -f "$HOME/caddy-site/api/server.py" ]; then
  cp "$HOME/caddy-site/api/server.py" "$API_DIR/server.py"
elif [ -f "./api/server.py" ]; then
  cp "./api/server.py" "$API_DIR/server.py"
fi
chmod 755 "$API_DIR/server.py"

sudo tee "$SERVICE" >/dev/null <<EOF
[Unit]
Description=RackForge API (SQLite)
After=network.target

[Service]
Type=simple
User=stef
Group=stef
WorkingDirectory=$API_DIR
Environment=RACKFORGE_DB=$API_DIR/plans.db
Environment=RACKFORGE_HOST=127.0.0.1
Environment=RACKFORGE_PORT=8080
ExecStart=/usr/bin/python3 $API_DIR/server.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable rackforge-api
sudo systemctl restart rackforge-api

if [ -f "$SUDOERS" ] && ! grep -q rackforge-api "$SUDOERS"; then
  sudo tee -a "$SUDOERS" >/dev/null <<'EOF'
stef ALL=(ALL) NOPASSWD: /bin/systemctl restart rackforge-api
stef ALL=(ALL) NOPASSWD: /bin/systemctl status rackforge-api
EOF
  sudo chmod 440 "$SUDOERS"
  sudo visudo -cf "$SUDOERS"
fi

echo "OK: rackforge-api service"
sudo systemctl --no-pager status rackforge-api | head -5
curl -sf http://127.0.0.1:8080/api/health && echo "" && echo "OK: health check"