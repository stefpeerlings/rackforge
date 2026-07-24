#!/bin/bash
# RackForge — herstel op een verse Ubuntu-server vanaf GitHub
# Gebruik (één regel):
#   git clone https://github.com/stefpeerlings/rackforge.git rackforge-src && cd rackforge-src && bash install.sh
# (niet clonen naar "rackforge" zelf — dat botst met de API_DIR-default $HOME/rackforge)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="${API_DIR:-$HOME/rackforge}"
CONFIG_DIR="${CONFIG_DIR:-$HOME/.config/rackforge}"
USER_NAME="${USER_NAME:-$(whoami)}"
# Bare LXCs are often root-only with no sudo binary — don't require it if
# we're already root.
if [ "$(id -u)" = "0" ]; then
  SUDO=""
else
  SUDO="sudo"
fi

echo "=== RackForge restore ==="
echo "Repo:     $REPO_ROOT"
echo "API:      $API_DIR"
echo ""

mkdir -p "$API_DIR" "$API_DIR/avatars" "$API_DIR/icons" "$API_DIR/static" "$CONFIG_DIR"

echo "-> Statische site"
for f in index.html login.html main.html settings.html verify-email.html reset-password.html privacy.html terms.html; do
  [ -f "$REPO_ROOT/$f" ] && cp "$REPO_ROOT/$f" "$API_DIR/static/"
done
for d in css js icons; do
  rm -rf "$API_DIR/static/$d"
  cp -a "$REPO_ROOT/$d" "$API_DIR/static/"
done

echo "-> API"
for f in server.py admin_panel.py email_templates.py google_oauth.py license.py; do
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

# `systemctl --user` needs a running user session bus. A real SSH/console
# login sets this up automatically (via pam_systemd); a root shell opened
# directly in a container (pct exec/enter, docker exec, ...) usually
# doesn't. Fix it up manually in that case instead of failing.
FIXED_USER_SESSION=0
if [ -z "${XDG_RUNTIME_DIR:-}" ] || ! systemctl --user status >/dev/null 2>&1; then
  echo "   Geen actieve systemd user-sessie — deze opzetten..."
  FIXED_USER_SESSION=1
  $SUDO loginctl enable-linger "$USER_NAME" 2>/dev/null || true
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
  mkdir -p "$XDG_RUNTIME_DIR"
  $SUDO systemctl start "user@$(id -u).service" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    systemctl --user status >/dev/null 2>&1 && break
    sleep 1
  done
fi

systemctl --user daemon-reload
systemctl --user enable rackforge-api
systemctl --user restart rackforge-api
sleep 2
# Use python3 (already a hard requirement for the app itself) instead of
# curl, which isn't preinstalled on minimal Ubuntu/LXC images.
python3 -c "
import ssl, urllib.request as u
u.urlopen('https://127.0.0.1:8080/api/health', timeout=5, context=ssl._create_unverified_context())
" >/dev/null 2>&1 && echo "   API health OK" || echo "   API start controleren: journalctl --user -u rackforge-api -n 30"

if [ "$FIXED_USER_SESSION" = "1" ]; then
  echo ""
  echo "Let op: dit was een console-sessie zonder login-bus. Zet dit in ~/.bashrc"
  echo "zodat systemctl --user ook in nieuwe sessies blijft werken:"
  echo "  export XDG_RUNTIME_DIR=/run/user/\$(id -u)"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "Klaar! Open https://${IP:-<dit-ip>}:8080/ in je browser."
echo "(Zelfondertekend certificaat — de browser waarschuwt eenmalig, dat hoort zo."
echo " Wil je een eigen/vertrouwd certificaat? Zet RACKFORGE_TLS_CERT en"
echo " RACKFORGE_TLS_KEY, of RACKFORGE_TLS=0 voor gewoon HTTP.)"
echo ""
echo "Vergeet niet:"
echo "  1. $CONFIG_DIR/admin.env — admin-wachtwoord"
echo "  2. $CONFIG_DIR/smtp.env — e-mail (optioneel)"
echo "  3. $CONFIG_DIR/google.env — Google login (optioneel)"
echo "  4. Database backup terugzetten naar $API_DIR/plans.db (indien van toepassing)"
