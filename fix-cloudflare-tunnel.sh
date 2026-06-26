#!/bin/bash
set -euo pipefail

TUNNEL_ID="468025c7-e709-4846-8cbc-a919aaf05deb"
DOMAIN="home-labe.com"
CNAME_TARGET="${TUNNEL_ID}.cfargotunnel.com"

echo "=== Cloudflare Tunnel DNS fix ==="

if [ ! -f "$HOME/.cloudflared/cert.pem" ]; then
  echo "ERROR: cert.pem ontbreekt. Eerst: cloudflared tunnel login"
  exit 1
fi

echo "DNS routes aanmaken (met overschrijven)..."
cloudflared tunnel route dns -f "$TUNNEL_ID" "www.${DOMAIN}"
cloudflared tunnel route dns -f "$TUNNEL_ID" "${DOMAIN}"

echo ""
echo "Klaar! DNS zou nu moeten wijzen naar: ${CNAME_TARGET}"
echo "Test: curl -sI https://www.${DOMAIN}/ | head -5"