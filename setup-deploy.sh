#!/bin/bash
# Eenmalig op de server — daarna kan deploy.ps1 alles zelf doen.
# Gebruik: bash ~/setup-deploy.sh
set -euo pipefail

echo "=== Deploy setup (eenmalig) ==="

if ! getent group caddy >/dev/null; then
  echo "Groep caddy niet gevonden."
  exit 1
fi

sudo usermod -aG caddy stef

# Volledige webroot schrijfbaar voor groep caddy (+ setgid op mappen)
sudo mkdir -p /var/www/html/{css,js,icons}
sudo chown -R caddy:caddy /var/www/html
sudo chmod -R g+rwX /var/www/html
sudo find /var/www/html -type d -exec chmod g+s {} \;

echo "OK: /var/www/html schrijfbaar voor stef (groep caddy)"

# Caddy deploy zonder wachtwoord
sudo tee /etc/sudoers.d/stef-caddy >/dev/null <<'EOF'
stef ALL=(ALL) NOPASSWD: /bin/cp /home/stef/Caddyfile.new /etc/caddy/Caddyfile
stef ALL=(ALL) NOPASSWD: /bin/systemctl reload caddy
stef ALL=(ALL) NOPASSWD: /bin/systemctl status caddy
EOF
sudo chmod 440 /etc/sudoers.d/stef-caddy
sudo visudo -cf /etc/sudoers.d/stef-caddy
echo "OK: passwordless sudo voor Caddy"

# Test als stef (zonder nieuwe login-sessie kan groep nog ontbreken)
if sudo -u stef test -w /var/www/html/index.html 2>/dev/null || test -w /var/www/html/index.html; then
  echo "OK: schrijftest geslaagd"
else
  echo "TIP: log uit en opnieuw in (of: newgrp caddy) en run:"
  echo "  touch /var/www/html/.test && rm /var/www/html/.test"
fi

echo ""
echo "Klaar. Vanaf Windows: cd caddy-site && .\\deploy.ps1"