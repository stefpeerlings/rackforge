# RackForge

RackForge is een rack-planning webapp met SQLite-API, admin-panel en Caddy reverse proxy.

- **Frontend:** statische HTML/JS/CSS (`/main`, `/login`, …)
- **API:** Python (`server.py`) op `127.0.0.1:8080`
- **Admin:** `/admin` — databasebeheer, gebruikers, exports

**Repo:** https://github.com/stefpeerlings/rackforge (private)

## Vereisten

- Ubuntu-server met Caddy
- Python 3
- systemd (user service voor de API)

## Installatie in één commando (Ubuntu)

```bash
git clone https://github.com/stefpeerlings/rackforge.git && cd rackforge && bash install.sh
```

Dat is alles: clone + volledige restore in één regel.

Het script:

1. Kopieert de site naar `/var/www/html` (als schrijfbaar)
2. Zet API-bestanden in `~/rackforge`
3. Maakt config-templates aan in `~/.config/rackforge/`
4. Start de `rackforge-api` user-service

### Configuratie (handmatig)

Kopieer de `.example`-bestanden en vul secrets in:

| Bestand | Doel |
|---------|------|
| `~/.config/rackforge/admin.env` | Admin-wachtwoord (`RACKFORGE_ADMIN_PASSWORD`) |
| `~/.config/rackforge/smtp.env` | E-mail (wachtwoord-reset, verificatie) |
| `~/.config/rackforge/google.env` | Google OAuth (optioneel) |

Voorbeelden staan in `api/*.env.example`.

Bootstrap-admin: gebruikersnaam **`admin`** met het wachtwoord uit `admin.env` (rol Owner).

### Database

De SQLite-database (`plans.db`) staat **niet** in git. Bij migratie handmatig kopiëren:

```bash
# Van oude server
scp user@oude-server:~/rackforge/plans.db ~/rackforge/plans.db
systemctl --user restart rackforge-api
```

Backup op de server (git bundle):

```bash
git clone ~/rackforge-backup.bundle rackforge-restore
```

## Deploy vanaf Windows

```powershell
cd C:\Users\stef\caddy-site
.\deploy.ps1
```

Deployt site + API naar `caddy-server` (`10.0.40.12`) en herstart de API.

Eenmalige server-setup:

```bash
bash setup-server.sh    # rechten /var/www/html, Caddy sudo
bash setup-deploy.sh    # deploy-rechten
bash setup-api.sh       # alternatief: system-wide API service
```

## Projectstructuur

```
├── api/                  # Python API + admin panel
│   ├── server.py
│   ├── admin_panel.py
│   └── *.env.example
├── css/ js/ icons/       # Frontend assets
├── *.html                # Pagina's
├── Caddyfile             # Reverse proxy (/api, /admin → :8080)
├── deploy.ps1            # Windows deploy
├── rackforge-api.user.service
├── install.sh              # Entry point (roept restore aan)
└── scripts/
    ├── restore-ubuntu.sh # Herstel op nieuwe server
    └── push-github.ps1     # Push naar GitHub
```

## Caddy

`/api/*` en `/admin/*` worden doorgestuurd naar de API op poort **8080**. Statische pagina's worden vanuit `/var/www/html` geserveerd.

Na wijziging:

```bash
sudo cp ~/Caddyfile.new /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## Nuttige commando's

```bash
# API status
systemctl --user status rackforge-api
journalctl --user -u rackforge-api -f

# Health check
curl http://127.0.0.1:8080/api/health
```

## Git

Private repo: https://github.com/stefpeerlings/rackforge

```bash
git add -A && git commit -m "Beschrijving" && git push
```

**Niet committen:** `.env`, `plans.db`, avatars, wachtwoorden (zie `.gitignore`).