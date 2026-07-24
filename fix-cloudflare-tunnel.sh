#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$SCRIPT_DIR/deploy.local.sh" ] && source "$SCRIPT_DIR/deploy.local.sh"

TUNNEL_ID="${CF_TUNNEL_ID:?Zet CF_TUNNEL_ID in deploy.local.sh (zie deploy.local.sh.example)}"
DOMAIN="${CF_TUNNEL_DOMAIN:?Zet CF_TUNNEL_DOMAIN in deploy.local.sh (zie deploy.local.sh.example)}"
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