#!/bin/bash
# Genereer (of vernieuw) LAN-TLS-certificaten voor Caddy + mkcert.
# Gebruik: bash ~/setup-local-tls.sh
set -euo pipefail

LAN_IP="10.0.40.12"
HOST="ubuntu-sever-laptop"
DOMAIN="netwerkengineer.com"
CERT_DIR="/var/www/html/private-certs"

mkdir -p ~/bin ~/.mkcert "$CERT_DIR"
if [ ! -x ~/bin/mkcert ]; then
  curl -fsSL "https://dl.filippo.io/mkcert/latest?for=linux/amd64" -o ~/bin/mkcert
  chmod +x ~/bin/mkcert
fi

export CAROOT=~/.mkcert
~/bin/mkcert -cert-file "$CERT_DIR/netwerkengineer.pem" \
  -key-file "$CERT_DIR/netwerkengineer-key.pem" \
  "$DOMAIN" "www.$DOMAIN" "$LAN_IP" "$HOST"

chmod 755 "$CERT_DIR"
chmod 644 "$CERT_DIR/netwerkengineer.pem"
chmod 640 "$CERT_DIR/netwerkengineer-key.pem"
chgrp caddy "$CERT_DIR/netwerkengineer-key.pem"

cp ~/.mkcert/rootCA.pem ~/lan-rootCA.pem
chmod 644 ~/lan-rootCA.pem

echo ""
echo "Certificaten staan in $CERT_DIR"
echo "Root CA voor laptops: ~/lan-rootCA.pem"
echo "Herlaad Caddy: sudo systemctl reload caddy"