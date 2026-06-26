#!/bin/bash
# RackForge — herstel op een verse Ubuntu-server vanaf GitHub
# Gebruik:
#   git clone git@github.com:JOUW_USER/rackforge.git ~/rackforge-src
#   cd ~/rackforge-src && bash scripts/restore-ubuntu.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_ROOT="${WEB_ROOT:-/var/www/html}"
API_DIR="${API_DIR:-$HOME/rackforge}"
CONFIG_DIR="${CONFIG_DIR:-$HOME/.config/rackforge}"
USER_NAME="${USER_NAME:-$(whoami)}"

echo "=== RackForge restore ==="
echo "Repo:     $REPO_ROOT"
echo "Website:  $WEB_ROOT"
echo "API:      $API_DIR"
echo ""

mkdir -p "$API_DIR" "$API_DIR/avatars" "$API_DIR/icons" "$CONFIG_DIR"

echo "-> Statische site"
if [ -w "$WEB_ROOT" ]; then
  for f in index.html login.html main.html settings.html verify-email.html reset-password.html privacy.html terms.html; do
    [ -f "$REPO_ROOT/$f" ] && cp "$REPO_ROOT/$f" "$WEB_ROOT/"
  done
  for d in css js icons; do
    rm -rf "$WEB_ROOT/$d"
    cp -a "$REPO_ROOT/$d" "$WEB_ROOT/"
  done
else
  echo "   Geen schrijfrecht op $WEB_ROOT — kopieer handmatig of run setup-server.sh"
fi

echo "-> API"
for f in server.py admin_panel.py email_templates.py google_oauth.py; do
  cp "$REPO_ROOT/api/$f" "$API_DIR/$f"
done
chmod 755 "$API_DIR/server.py"
[ -f "$REPO_ROOT/icons/rackforge-avatar.png" ] && cp "$REPO_ROOT/icons/rackforge-avatar.png" "$API_DIR/icons/"

echo "-> Config templates"
for example in admin.env.example smtp.env.example google.env.example; do
  src="$REPO_ROOT/api/$example"
  dst="$CONFIG_DIR/${example%.example}"
  if [ -f "$src" ] && [ ! -f "$dst" ]; then
    cp "$src" "$dst"
    chmod 600 "$dst"
    echo "   Aangemaakt: $dst (vul secrets in)"
  fi
done

echo "-> systemd user service"
mkdir -p "$HOME/.config/systemd/user"
cp "$REPO_ROOT/rackforge-api.user.service" "$HOME/.config/systemd/user/rackforge-api.service"
systemctl --user daemon-reload
systemctl --user enable rackforge-api
systemctl --user restart rackforge-api
sleep 2
curl -sf "http://127.0.0.1:8080/api/health" >/dev/null && echo "   API health OK" || echo "   API start controleren: journalctl --user -u rackforge-api -n 30"

if [ -f "$REPO_ROOT/Caddyfile" ] && [ -f "$HOME/Caddyfile.new" ] || command -v caddy >/dev/null 2>&1; then
  cp "$REPO_ROOT/Caddyfile" "$HOME/Caddyfile.new"
  echo "-> Caddyfile gekopieerd naar ~/Caddyfile.new"
  echo "   Daarna: sudo cp ~/Caddyfile.new /etc/caddy/Caddyfile && sudo systemctl reload caddy"
fi

echo ""
echo "Klaar. Vergeet niet:"
echo "  1. $CONFIG_DIR/admin.env — admin-wachtwoord"
echo "  2. $CONFIG_DIR/smtp.env — e-mail (optioneel)"
echo "  3. $CONFIG_DIR/google.env — Google login (optioneel)"
echo "  4. Database backup terugzetten naar $API_DIR/plans.db (indien van toepassing)"