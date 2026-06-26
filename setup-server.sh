#!/bin/bash
# Eenmalig op de server uitvoeren (vraagt je sudo-wachtwoord lokaal op de server).
# Gebruik: bash setup-server.sh
set -euo pipefail

echo "=== Stef's Lab — server setup ==="

# 1) Website deploy zonder sudo
if ! getent group caddy >/dev/null; then
  echo "Groep caddy niet gevonden."
  exit 1
fi
sudo usermod -aG caddy stef
sudo chown -R caddy:caddy /var/www/html
sudo chmod -R g+rwX /var/www/html
echo "OK: stef kan nu schrijven naar /var/www/html (groep caddy)"

# 2) Caddyfile + reload zonder wachtwoord
sudo tee /etc/sudoers.d/stef-caddy >/dev/null <<'EOF'
# Deploy Caddy config + reload (geen wachtwoord)
stef ALL=(ALL) NOPASSWD: /bin/cp /home/stef/Caddyfile.new /etc/caddy/Caddyfile
stef ALL=(ALL) NOPASSWD: /bin/systemctl reload caddy
stef ALL=(ALL) NOPASSWD: /bin/systemctl status caddy
EOF
sudo chmod 440 /etc/sudoers.d/stef-caddy
sudo visudo -cf /etc/sudoers.d/stef-caddy
echo "OK: passwordless sudo voor Caddy deploy"

# 3) Pas Caddyfile aan als die nog 10.0.40.11 heeft
if [ -f /home/stef/Caddyfile.new ]; then
  if grep -q '10.0.40.11' /etc/caddy/Caddyfile 2>/dev/null; then
    sudo cp /home/stef/Caddyfile.new /etc/caddy/Caddyfile
    sudo systemctl reload caddy
    echo "OK: Caddyfile bijgewerkt naar 10.0.40.12"
  fi
fi

# 4) SSH: alleen keys (optioneel maar aanbevolen)
SSHD_DROPIN="/etc/ssh/sshd_config.d/99-stef-keyonly.conf"
if [ ! -f "$SSHD_DROPIN" ]; then
  sudo tee "$SSHD_DROPIN" >/dev/null <<'EOF'
# Alleen key-login voor SSH (wachtwoord uit)
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
EOF
  sudo systemctl reload ssh || sudo systemctl reload sshd
  echo "OK: SSH wachtwoord-login uitgeschakeld (key-login blijft werken)"
else
  echo "SKIP: SSH key-only config bestaat al"
fi

echo ""
echo "Klaar. Log uit en opnieuw in (of: newgrp caddy) zodat groep caddy actief is."
echo "Test vanaf Windows: ssh caddy-server 'touch /var/www/html/.write-test && rm /var/www/html/.write-test'"