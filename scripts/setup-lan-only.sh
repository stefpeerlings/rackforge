#!/bin/bash
# Eenmalig op de server — RackForge alleen op het lokale netwerk.
# Gebruik: bash ~/setup-lan-only.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$SCRIPT_DIR/../deploy.local.sh" ] && source "$SCRIPT_DIR/../deploy.local.sh"

LAN_CIDR="${LAN_CIDR:?Zet LAN_CIDR in deploy.local.sh (zie deploy.local.sh.example)}"
LAN_IP="${DEPLOY_HOST:?Zet DEPLOY_HOST in deploy.local.sh (zie deploy.local.sh.example)}"
LAN_IF="${LAN_INTERFACE:-ens33}"
DOMAIN="${DEPLOY_DOMAIN:?Zet DEPLOY_DOMAIN in deploy.local.sh (zie deploy.local.sh.example)}"
LAN_DNS_SERVER="${LAN_DNS_SERVER:?Zet LAN_DNS_SERVER in deploy.local.sh (zie deploy.local.sh.example)}"

echo "=== RackForge LAN-only setup ==="

echo "1) Cloudflare-tunnel stoppen (geen toegang vanaf internet)..."
sudo systemctl stop cloudflared 2>/dev/null || true
sudo systemctl disable cloudflared 2>/dev/null || true
echo "   cloudflared uitgeschakeld"

echo "2) Lokale DNS (dnsmasq) — ${DOMAIN} → ${LAN_IP}..."
sudo apt-get install -y dnsmasq
sudo tee /etc/dnsmasq.d/rackforge-local.conf >/dev/null <<EOF
# RackForge — alleen binnen LAN
interface=${LAN_IF}
bind-interfaces
listen-address=${LAN_IP}
except-interface=lo

# Niet doorsturen naar Cloudflare (voorkomt IPv6 AAAA-lek)
local=/${DOMAIN}/
local=/www.${DOMAIN}/
address=/${DOMAIN}/${LAN_IP}
address=/www.${DOMAIN}/${LAN_IP}

# Overige queries doorsturen naar router
server=${LAN_DNS_SERVER}
no-resolv
cache-size=1000
EOF
sudo systemctl enable dnsmasq
sudo systemctl restart dnsmasq
echo "   dnsmasq actief op ${LAN_IP}:53"

echo "3) Firewall — web alleen vanaf ${LAN_CIDR}..."
if command -v ufw >/dev/null; then
  sudo ufw allow from "${LAN_CIDR}" to any port 80,443 proto tcp comment 'RackForge HTTP(S) LAN'
  sudo ufw allow from "${LAN_CIDR}" to any port 53 proto udp comment 'RackForge DNS LAN'
  sudo ufw deny 80/tcp comment 'Block HTTP WAN' 2>/dev/null || true
  sudo ufw deny 443/tcp comment 'Block HTTPS WAN' 2>/dev/null || true
  echo "   ufw-regels toegevoegd"
else
  echo "   ufw niet gevonden — zorg dat poort 80/443 niet naar buiten worden doorgestuurd op je router"
fi

echo ""
echo "Klaar!"
echo ""
echo "Laatste stap op je router (${LAN_DNS_SERVER}):"
echo "  DHCP DNS-server = ${LAN_IP}"
echo "  (of voeg handmatig een DNS-rewrite toe: ${DOMAIN} → ${LAN_IP})"
echo ""
echo "Open daarna op je LAN: https://${DOMAIN}/"
echo "Vanaf internet blijft de site onbereikbaar (tunnel uit, geen port-forward nodig)."
