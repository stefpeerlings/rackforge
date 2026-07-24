<p align="center">
  <img src="icons/rackforge-avatar.svg" alt="RackForge" width="96">
</p>

<h1 align="center">RackForge</h1>
<p align="center"><strong>Plan, build, and manage your server racks — self-hosted, zero external dependencies.</strong></p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/backend-Python%203%20stdlib-3776AB?logo=python&logoColor=white">
  <img alt="Frontend" src="https://img.shields.io/badge/frontend-vanilla%20JS-F7DF1E?logo=javascript&logoColor=black">
  <img alt="Dependencies" src="https://img.shields.io/badge/dependencies-zero-success">
  <img alt="Deploy" src="https://img.shields.io/badge/deploy-Docker%20%7C%20bare--metal-2496ED?logo=docker&logoColor=white">
</p>

---

RackForge is a rack-planning web app: drag-and-drop equipment into virtual racks, track power
and U-space, and manage everything through a self-hosted API with a built-in admin panel. No
database server, no build step, no npm/pip dependency tree — a single Python process backed by
SQLite, fronted by Caddy.

## Features

- **Rack planning** — drag-and-drop equipment placement, U-space and power-budget tracking, custom equipment types
- **Multi-rack accounts** — save, switch between, and manage multiple racks per user
- **Version history** — automatic snapshots with one-click restore
- **Shared racks** — invite collaborators as viewer or editor
- **Export** — PNG and PDF rack diagrams
- **Admin panel** — user/session management, audit log, license management, CSV/JSON exports
- **Accounts** — email/password and Google OAuth, email verification, password reset
- **i18n** — Dutch and English out of the box

## Tiers

RackForge ships as one codebase with tier-gated limits, unlocked by a signed license key
(entered under **Admin → License**, no restart required):

| | Community | Pro | Enterprise |
|---|---|---|---|
| Racks per user | 1 | 5 | Unlimited |
| Custom equipment types | — | 10 | Unlimited |
| Version history | 3 snapshots | 20 snapshots | 100 snapshots |
| Shared collaborators per rack | — | 3 | Unlimited |
| Admin audit log | — | ✓ | ✓ |

The Community tier requires no license key and runs fully self-hosted, free.

## Quick start (Docker)

```bash
git clone https://github.com/stefpeerlings/rackforge.git
cd rackforge
cp .env.example .env                              # set DOMAIN
cp api/rackforge.env.example api/rackforge.env     # set RACKFORGE_ADMIN_PASSWORD
docker compose up -d --build
```

This starts two containers:

- **`api`** — the Python API (zero pip dependencies; only the `openssl` CLI is added, for
  license-key verification), with a named volume for `plans.db` and avatars.
- **`web`** — Caddy with the static site baked in. Automatically requests a Let's Encrypt
  certificate for `DOMAIN` (or plain HTTP if `DOMAIN=localhost`, for local/LAN testing — also
  set `RACKFORGE_SECURE_COOKIE=0` in `api/rackforge.env` in that case, see the example file).

Log in at `/admin` (user **`admin`**, password from `rackforge.env`) to paste a license key
under **License** — it takes effect immediately, no restart needed.
`api/issue_license.py` (the vendor-only key-signing tool) is deliberately excluded from the image.

Rebuild after a `git pull`:

```bash
docker compose up -d --build
```

## Bare-metal install (Ubuntu + Caddy)

```bash
git clone https://github.com/stefpeerlings/rackforge.git rackforge-src && cd rackforge-src && bash install.sh
```

That's it — clone and full restore in one line.

> **Note:** clone into a directory name other than `rackforge` (e.g. `rackforge-src` as above).
> `API_DIR` defaults to `~/rackforge` (see `rackforge-api.user.service`), so a checkout in that
> exact directory collides with the restore step.

The script:

1. Copies the static site to `/var/www/html` (if writable)
2. Places the API files in `~/rackforge`
3. Creates config templates in `~/.config/rackforge/`
4. Starts the `rackforge-api` user service

### Configuration

Copy the `.example` files and fill in secrets:

| File | Purpose |
|---|---|
| `~/.config/rackforge/admin.env` | Admin password (`RACKFORGE_ADMIN_PASSWORD`) |
| `~/.config/rackforge/smtp.env` | Email (password reset, verification) |
| `~/.config/rackforge/google.env` | Google OAuth (optional) |

Templates live in `api/*.env.example`.

Bootstrap admin: username **`admin`** with the password from `admin.env` (Owner role).

### Database

The SQLite database (`plans.db`) is **not** in git. To migrate, copy it manually:

```bash
scp user@old-server:~/rackforge/plans.db ~/rackforge/plans.db
systemctl --user restart rackforge-api
```

### Requirements

- Ubuntu server with Caddy
- Python 3
- systemd (user service for the API)

## Deploying to your own infrastructure

The deploy/ops scripts in the repo root and `scripts/` (Caddy, DNS, Cloudflare Tunnel, Windows
deploy) read your server details from a local, never-committed config file instead of having
them hardcoded:

```bash
cp deploy.local.sh.example deploy.local.sh     # Linux/macOS — fill in, then: source deploy.local.sh
cp deploy.local.ps1.example deploy.local.ps1   # Windows — fill in
```

See the `.example` files for available variables (`DEPLOY_HOST`, `DEPLOY_DOMAIN`, `LAN_CIDR`,
`CF_TUNNEL_ID`, …).

### Deploy from Windows

```powershell
cd C:\path\to\rackforge
.\deploy.ps1
```

Deploys the site + API to the server from `deploy.local.ps1` (`DEPLOY_HOST`) and restarts the API.

One-time server setup:

```bash
bash setup-server.sh    # /var/www/html permissions, passwordless Caddy sudo
bash setup-deploy.sh    # deploy permissions
bash setup-api.sh       # alternative: system-wide API service
```

### Caddy

`/api/*` and `/admin/*` are reverse-proxied to the API on port **8080**. Static pages are served
from `/var/www/html`.

After a config change:

```bash
sudo cp ~/Caddyfile.new /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

### Useful commands

```bash
# API status
systemctl --user status rackforge-api
journalctl --user -u rackforge-api -f

# Health check
curl http://127.0.0.1:8080/api/health
```

## Project structure

```
├── api/                  # Python API + admin panel
│   ├── server.py
│   ├── admin_panel.py
│   ├── license.py        # Tier/license verification
│   └── *.env.example
├── css/ js/ icons/       # Frontend assets
├── *.html                # Pages
├── Caddyfile             # Reverse proxy (/api, /admin -> :8080), bare-metal
├── docker/Caddyfile      # Reverse proxy, Docker
├── docker-compose.yml    # Docker deploy
├── deploy.ps1            # Windows deploy
├── rackforge-api.user.service
├── install.sh            # Entry point (calls the restore script)
└── scripts/
    └── restore-ubuntu.sh # Restore onto a fresh server
```

## Contributing

Issues and pull requests are welcome. Please don't commit `.env` files, `plans.db`, avatars,
passwords, or `deploy.local.sh`/`deploy.local.ps1` — see `.gitignore`.
