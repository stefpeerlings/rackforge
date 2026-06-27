#!/bin/bash
# Eenmalig op de server (sudo-wachtwoord nodig):
#   bash ~/apply-dns-fix.sh
set -euo pipefail

LAN_IP="10.0.40.12"
LAN_IF="${LAN_IF:-ens33}"
DOMAIN="netwerkengineer.com"

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

server=10.0.40.254
no-resolv
cache-size=1000
EOF

sudo systemctl restart dnsmasq
echo "dnsmasq herstart — test: nslookup ${DOMAIN} ${LAN_IP}"
nslookup "${DOMAIN}" "${LAN_IP}" | tail -5