#!/bin/bash
# Genereer (of vernieuw) LAN-TLS-certificaten voor Caddy + mkcert.
# Gebruik: bash ~/setup-local-tls.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$SCRIPT_DIR/../deploy.local.sh" ] && source "$SCRIPT_DIR/../deploy.local.sh"

LAN_IP="${DEPLOY_HOST:?Zet DEPLOY_HOST in deploy.local.sh (zie deploy.local.sh.example)}"
DOMAIN="${DEPLOY_DOMAIN:?Zet DEPLOY_DOMAIN in deploy.local.sh (zie deploy.local.sh.example)}"
CERT_DIR="/var/www/html/private-certs"

mkdir -p ~/bin ~/.mkcert "$CERT_DIR"
if [ ! -x ~/bin/mkcert ]; then
  curl -fsSL "https://dl.filippo.io/mkcert/latest?for=linux/amd64" -o ~/bin/mkcert
  chmod +x ~/bin/mkcert
fi

export CAROOT=~/.mkcert
~/bin/mkcert -cert-file "$CERT_DIR/lan.pem" \
  -key-file "$CERT_DIR/lan-key.pem" \
  "$DOMAIN" "www.$DOMAIN" "$LAN_IP"

chmod 755 "$CERT_DIR"
chmod 644 "$CERT_DIR/lan.pem"
chmod 640 "$CERT_DIR/lan-key.pem"
chgrp caddy "$CERT_DIR/lan-key.pem"

cp ~/.mkcert/rootCA.pem ~/lan-rootCA.pem
chmod 644 ~/lan-rootCA.pem

echo ""
echo "Certificaten staan in $CERT_DIR"
echo "Root CA voor laptops: ~/lan-rootCA.pem"
echo "Herlaad Caddy: sudo systemctl reload caddy"
