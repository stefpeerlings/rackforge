#!/bin/bash
# Eenmalig op de server (sudo-wachtwoord nodig):
#   bash ~/apply-dns-fix.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$SCRIPT_DIR/../deploy.local.sh" ] && source "$SCRIPT_DIR/../deploy.local.sh"

LAN_IP="${DEPLOY_HOST:?Zet DEPLOY_HOST in deploy.local.sh (zie deploy.local.sh.example)}"
LAN_IF="${LAN_INTERFACE:-ens33}"
DOMAIN="${DEPLOY_DOMAIN:?Zet DEPLOY_DOMAIN in deploy.local.sh (zie deploy.local.sh.example)}"
LAN_DNS_SERVER="${LAN_DNS_SERVER:?Zet LAN_DNS_SERVER in deploy.local.sh (zie deploy.local.sh.example)}"

sudo tee /etc/dnsmasq.d/rackforge-local.conf >/dev/null <<EOF
# RackForge — alleen binnen LAN
interface=${LAN_IF}
bind-interfaces
listen-address=${LAN_IP}
except-interface=lo

local=/${DOMAIN}/
local=/www.${DOMAIN}/
address=/${DOMAIN}/${LAN_IP}
address=/www.${DOMAIN}/${LAN_IP}

server=${LAN_DNS_SERVER}
no-resolv
cache-size=1000
EOF

sudo systemctl restart dnsmasq
echo "dnsmasq herstart — test: nslookup ${DOMAIN} ${LAN_IP}"
nslookup "${DOMAIN}" "${LAN_IP}" | tail -5
