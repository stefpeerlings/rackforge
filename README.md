# RackForge

RackForge is een rack-planning webapp met SQLite-API, admin-panel en Caddy reverse proxy.

- **Frontend:** statische HTML/JS/CSS (`/main`, `/login`, …)
- **API:** Python (`server.py`) op `127.0.0.1:8080`
- **Admin:** `/admin` — databasebeheer, gebruikers, exports

**Repo:** https://github.com/stefpeerlings/rackforge

## Vereisten

- Ubuntu-server met Caddy
- Python 3
- systemd (user service voor de API)

## Deploy-config (eigen server)

De deploy-/beheerscripts in de repo-root en `scripts/` (Caddy, DNS, Cloudflare Tunnel, Windows-deploy)
hebben geen server-adres hardcoded — die lezen dat uit een lokaal, nooit-gecommit config-bestand:

```bash
cp deploy.local.sh.example deploy.local.sh   # Linux/macOS — invullen, dan: source deploy.local.sh
cp deploy.local.ps1.example deploy.local.ps1 # Windows — invullen
```

Zie de `.example`-bestanden voor de beschikbare variabelen (`DEPLOY_HOST`, `DEPLOY_DOMAIN`,
`LAN_CIDR`, `CF_TUNNEL_ID`, …).

## Installatie in één commando (Ubuntu)

```bash
git clone https://github.com/stefpeerlings/rackforge.git rackforge-src && cd rackforge-src && bash install.sh
```

Dat is alles: clone + volledige restore in één regel.

**Let op:** clone naar een andere mapnaam dan `rackforge` (bv. `rackforge-src` zoals hierboven) —
`API_DIR` valt standaard terug op `~/rackforge` (zie `rackforge-api.user.service`), dus een
checkout in exact die map botst met de restore (`cp` kopieert dan naar zichzelf).

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

## Docker (klant self-hosted)

Voor klanten die RackForge zelf willen draaien (eigen server/LXC met Docker),
in plaats van de handmatige Ubuntu-restore hierboven:

```bash
git clone https://github.com/stefpeerlings/rackforge.git
cd rackforge
cp .env.example .env                              # DOMAIN invullen
cp api/rackforge.env.example api/rackforge.env     # RACKFORGE_ADMIN_PASSWORD invullen
docker compose up -d --build
```

Dit start twee containers:

- **`api`** — de Python-API (zero pip-dependencies, alleen `openssl` CLI erbij voor licentie-verificatie), met een named volume voor `plans.db` + avatars.
- **`web`** — Caddy met de statische site erin gebakken, regelt automatisch een Let's Encrypt-certificaat voor `DOMAIN` (of gewoon platte HTTP als `DOMAIN=localhost` voor lokaal/LAN-testen — zet dan ook `RACKFORGE_SECURE_COOKIE=0` in `api/rackforge.env`, zie het voorbeeldbestand).

Licentie koppelen: log in op `/admin` (gebruiker **`admin`**, wachtwoord uit `rackforge.env`) en plak de key onder **Licentie** — direct actief, geen herstart nodig. `api/issue_license.py` (het vendor-only tool om keys te genereren) zit expres niet in het image.

Herbouwen na een `git pull`:

```bash
docker compose up -d --build
```

Logs / status:

```bash
docker compose ps
docker compose logs -f api
```

## Deploy vanaf Windows

```powershell
cd C:\pad\naar\rackforge
.\deploy.ps1
```

Deployt site + API naar de server uit `deploy.local.ps1` (`DEPLOY_HOST`) en herstart de API.

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

Repo: https://github.com/stefpeerlings/rackforge

```bash
git add -A && git commit -m "Beschrijving" && git push
```

**Niet committen:** `.env`, `plans.db`, avatars, wachtwoorden, `deploy.local.sh`/`deploy.local.ps1`
(zie `.gitignore`).