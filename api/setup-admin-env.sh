#!/bin/bash
set -e
mkdir -p ~/.config/rackforge
ENV=~/.config/rackforge/admin.env
if [ -f "$ENV" ]; then
  PASS_LEN="$(grep -E '^RACKFORGE_ADMIN_PASSWORD=.' "$ENV" | wc -c || true)"
  if [ "$PASS_LEN" -gt 30 ]; then
    echo "ADMIN_PASSWORD_EXISTS"
    exit 0
  fi
fi
PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
printf 'RACKFORGE_ADMIN_PASSWORD=%s\n' "$PASS" > "$ENV"
chmod 600 "$ENV"
echo "ADMIN_PASSWORD_CREATED:$PASS"