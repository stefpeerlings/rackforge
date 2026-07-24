FROM caddy:2-alpine

COPY docker/Caddyfile /etc/caddy/Caddyfile
COPY index.html login.html main.html settings.html privacy.html terms.html verify-email.html reset-password.html /srv/
COPY css/ /srv/css/
COPY js/ /srv/js/
COPY icons/ /srv/icons/
