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

## About

Planning where physical equipment goes in a rack is normally done in a spreadsheet, a diagram
tool, or in someone's head. RackForge replaces that with a purpose-built planner: drag equipment
onto a virtual rack, and it tracks U-space and power draw for you as you go, so you know before
you touch a screwdriver whether a device actually fits and whether the rack's power budget still
holds up.

It's built for anyone who manages physical racks and wants a shared, always-up-to-date source of
truth instead of a stale diagram — homelab owners, small IT teams, and MSPs managing racks for
multiple clients. Accounts can own several racks, share a rack with a colleague as a viewer or
editor, and every change is automatically snapshotted so a bad edit is one click away from being
undone.

The whole thing is one Python process (standard library only — no pip/npm dependency tree to
audit or break) backed by SQLite, with an admin panel for managing users, sessions, and licensing
built in. It serves its own frontend and speaks HTTPS out of the box (a self-signed certificate,
generated automatically via the `openssl` CLI — no separate reverse proxy to configure). That
means it runs on practically anything with Python 3 installed: a Docker container, a bare LXC, a
spare laptop — no database server, no build step, no external services required to get it running.

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

## Installation

Two supported paths, pick whichever fits your setup:

- **[Docker](#quick-start-docker)** — the fastest way to get RackForge running on any Linux
  host or LXC that has Docker installed. Updating means `git pull` + `docker compose up -d --build`.
  Recommended for most people.
- **[Proxmox LXC / bare-metal on Debian or Ubuntu](#bare-metal-install-debianubuntu)** — installs
  directly onto the host as a systemd user service. No Docker, no reverse proxy to configure.

Both paths end up in the same place: `server.py` listening on port **8080**, serving both the
frontend and the API/admin panel over HTTPS (self-signed by default), and a bootstrap `admin`
account you log into to configure everything else (license key, SMTP, Google OAuth) from the
admin panel — no config file editing needed after the initial setup.

## Quick start (Docker)

Requires Docker + the Compose plugin (`docker compose version`) on the target host.

```bash
apt-get update && apt-get install -y git   # skip if git is already installed
git clone https://github.com/stefpeerlings/rackforge.git
cd rackforge
cp api/rackforge.env.example api/rackforge.env   # set RACKFORGE_ADMIN_PASSWORD
docker compose up -d --build
```

`api/rackforge.env` holds the app's secrets (admin password, and optionally SMTP/Google
OAuth/license key/TLS — see the comments in the example file). It's never committed to git.

This starts a single container: the Python API (zero pip dependencies; only the `openssl` CLI is
added, for license-key verification and generating a self-signed TLS certificate), with a named
volume for `plans.db`, avatars, and the generated certificate — so it doesn't regenerate on every
restart.

Open `https://<host>:8080/` — the browser will warn about the self-signed certificate once,
that's expected; click through. Want a real, trusted certificate instead? Mount it into `/data`
and point `RACKFORGE_TLS_CERT`/`RACKFORGE_TLS_KEY` at it (see `api/rackforge.env.example`).
Already fronting this with your own reverse proxy/TLS terminator? Set `RACKFORGE_TLS=0` for
plain HTTP.

Log in at `/admin` (user **`admin`**, password from `rackforge.env`) to paste a license key
under **License** — it takes effect immediately, no restart needed.
`api/issue_license.py` (the vendor-only key-signing tool) is deliberately excluded from the image.

Note that `/admin` (the operator panel) and the planner itself are separate account systems:
visit `/main` and sign up for a regular account to actually start planning racks — the `admin`
login is only for managing the instance (users, sessions, audit log, license).

Rebuild after a `git pull`:

```bash
docker compose up -d --build
```

## Bare-metal install (Debian/Ubuntu)

Works on a plain Debian or Ubuntu server, a Proxmox LXC, or anything similar.

```bash
apt-get update && apt-get install -y git \
  && git clone https://github.com/stefpeerlings/rackforge.git rackforge-src \
  && cd rackforge-src && bash install.sh
```

That's it — clone and full restore in one line. (Not root? Prefix the `apt-get` commands with
`sudo`.)

> **Note:** clone into a directory name other than `rackforge` (e.g. `rackforge-src` as above).
> `API_DIR` defaults to `~/rackforge` (see `rackforge-api.user.service`), so a checkout in that
> exact directory collides with the restore step.

The script:

1. Copies the static site into `~/rackforge/static`
2. Places the API files in `~/rackforge`
3. Creates config templates in `~/.config/rackforge/`
4. Starts the `rackforge-api` user service — `server.py` binds `0.0.0.0:8080` and serves
   everything itself, generating a self-signed TLS certificate on first run

At the end it prints the URL to open, e.g. `https://10.0.10.35:8080/` — the browser will warn
about the self-signed certificate once, that's expected.

### Configuration

Copy the `.example` files and fill in secrets:

| File | Purpose |
|---|---|
| `~/.config/rackforge/admin.env` | Admin password (`RACKFORGE_ADMIN_PASSWORD`) |
| `~/.config/rackforge/smtp.env` | Email (password reset, verification) |
| `~/.config/rackforge/google.env` | Google OAuth (optional) |

Templates live in `api/*.env.example`. TLS behavior (self-signed by default, or your own
cert/key, or disabled entirely if you're fronting it yourself) is controlled by
`RACKFORGE_TLS`/`RACKFORGE_TLS_CERT`/`RACKFORGE_TLS_KEY` — set them in `admin.env`.

Bootstrap admin: username **`admin`** with the password from `admin.env` (Owner role) — this logs
into `/admin`, the operator panel (users, sessions, audit log, license), which is separate from
regular planner accounts. Visit `/main` and sign up normally to start planning racks.

### Database

The SQLite database (`plans.db`) is **not** in git. To migrate, copy it manually:

```bash
scp user@old-server:~/rackforge/plans.db ~/rackforge/plans.db
systemctl --user restart rackforge-api
```

### Requirements

- A Debian or Ubuntu server/LXC
- Python 3
- systemd (user service for the API)

### Useful commands

```bash
# API status
systemctl --user status rackforge-api
journalctl --user -u rackforge-api -f

# Health check
curl -sk https://127.0.0.1:8080/api/health
```

## Fronting it with your own reverse proxy (optional)

If you want a real public domain with a trusted (non-self-signed) certificate — e.g. via Let's
Encrypt — put any reverse proxy in front (Caddy, nginx, Cloudflare Tunnel, …) and set
`RACKFORGE_TLS=0` so RackForge serves plain HTTP for the proxy to terminate TLS in front of.
The repo includes a `Caddyfile` and a handful of personal deploy scripts (`setup-server.sh`,
`deploy.ps1`, `scripts/setup-local-tls.sh`, …) used for exactly that on the maintainer's own
production server — treat them as a worked example, not a required step.

## Project structure

```
├── api/                  # Python API + admin panel (serves the frontend too)
│   ├── server.py
│   ├── admin_panel.py
│   ├── license.py        # Tier/license verification
│   └── *.env.example
├── css/ js/ icons/       # Frontend assets
├── *.html                # Pages
├── docker-compose.yml    # Docker deploy (single container)
├── deploy.ps1            # Windows deploy (maintainer's own server)
├── Caddyfile             # Optional reverse proxy, for a real public domain
├── rackforge-api.user.service
├── install.sh            # Entry point (calls the restore script)
└── scripts/
    └── restore-ubuntu.sh # Restore onto a fresh server
```

## Contributing

Issues and pull requests are welcome. Please don't commit `.env` files, `plans.db`, avatars,
passwords, or `deploy.local.sh`/`deploy.local.ps1` — see `.gitignore`.
