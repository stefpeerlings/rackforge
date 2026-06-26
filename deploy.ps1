# Volledige deploy caddy-site -> stef@10.0.40.12:/var/www/html
# Gebruik: .\deploy.ps1

param(
    [string]$ServerHost = "10.0.40.12",
    [string]$User = "stef",
    [string]$RemotePath = "/var/www/html",
    [string]$IdentityFile = "$env:USERPROFILE\.ssh\caddy-server",
    [switch]$SkipCaddy
)

$ErrorActionPreference = "Stop"
$LocalPath = $PSScriptRoot

$sshArgs = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=15")
$scpArgs = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=15")
if ($IdentityFile) {
    $sshArgs += "-i", $IdentityFile, "-o", "IdentitiesOnly=yes"
    $scpArgs += "-i", $IdentityFile, "-o", "IdentitiesOnly=yes"
}

$remote = "${User}@${ServerHost}"

function Deploy-Dir([string]$Name) {
    $src = Join-Path $LocalPath $Name
    if (-not (Test-Path $src)) {
        Write-Host "OVERSLAAN (niet gevonden): $Name" -ForegroundColor Yellow
        return
    }
    $tarLocal = Join-Path $env:TEMP "caddy-deploy-$Name.tar"
    if (Test-Path $tarLocal) { Remove-Item $tarLocal -Force }
    & tar -cf $tarLocal -C $LocalPath $Name
    $tarRemote = "/tmp/caddy-deploy-$Name.tar"
    & scp @scpArgs $tarLocal "${remote}:${tarRemote}"
    $unpack = "mkdir -p ${RemotePath}/$Name; find ${RemotePath}/$Name -mindepth 1 -delete 2>/dev/null; tar -xf ${tarRemote} -C ${RemotePath} --no-same-owner --no-same-permissions 2>/dev/null; rm -f ${tarRemote}"
    & ssh @sshArgs $remote $unpack
    Remove-Item $tarLocal -Force
}

Write-Host "Deployen van $LocalPath naar ${remote}:${RemotePath}/" -ForegroundColor Cyan

foreach ($html in @("index.html", "login.html", "main.html", "settings.html", "verify-email.html", "reset-password.html", "privacy.html", "terms.html")) {
    Write-Host "  -> $html" -ForegroundColor DarkGray
    & scp @scpArgs (Join-Path $LocalPath $html) "${remote}:${RemotePath}/"
}

foreach ($dir in @("css", "js", "icons")) {
    Write-Host "  -> $dir/" -ForegroundColor DarkGray
    Deploy-Dir $dir
}

$apiLocal = Join-Path $LocalPath "api\server.py"
if (Test-Path $apiLocal) {
    Write-Host "  -> api/server.py" -ForegroundColor DarkGray
    & ssh @sshArgs $remote "mkdir -p /home/stef/rackforge /home/stef/rackforge/avatars"
    & scp @scpArgs $apiLocal "${remote}:/home/stef/rackforge/server.py"
    $emailTpl = Join-Path $LocalPath "api\email_templates.py"
    if (Test-Path $emailTpl) {
        & scp @scpArgs $emailTpl "${remote}:/home/stef/rackforge/email_templates.py"
    }
    $googleOauth = Join-Path $LocalPath "api\google_oauth.py"
    if (Test-Path $googleOauth) {
        & scp @scpArgs $googleOauth "${remote}:/home/stef/rackforge/google_oauth.py"
    }
    $adminPanel = Join-Path $LocalPath "api\admin_panel.py"
    if (Test-Path $adminPanel) {
        & scp @scpArgs $adminPanel "${remote}:/home/stef/rackforge/admin_panel.py"
    }
    $adminSetupSh = Join-Path $LocalPath "api\setup-admin-env.sh"
    if (Test-Path $adminSetupSh) {
        & scp @scpArgs $adminSetupSh "${remote}:/tmp/setup-admin-env.sh"
        & ssh @sshArgs $remote "bash /tmp/setup-admin-env.sh"
    }
    $logoPng = Join-Path $LocalPath "icons\rackforge-avatar.png"
    if (Test-Path $logoPng) {
        & ssh @sshArgs $remote "mkdir -p /home/stef/rackforge/icons"
        & scp @scpArgs $logoPng "${remote}:/home/stef/rackforge/icons/rackforge-avatar.png"
    }
    $serviceLocal = Join-Path $LocalPath "rackforge-api.user.service"
    if (Test-Path $serviceLocal) {
        & scp @scpArgs $serviceLocal "${remote}:/home/stef/rackforge-api.user.service"
    }
    $apiCmd = "mkdir -p ~/.config/systemd/user; cp /home/stef/rackforge-api.user.service ~/.config/systemd/user/rackforge-api.service 2>/dev/null || true; chmod +x /home/stef/rackforge/server.py; rm -rf /home/stef/rackforge/__pycache__; systemctl --user daemon-reload; systemctl --user enable rackforge-api 2>/dev/null || true; systemctl --user restart rackforge-api; sleep 1; curl -sf http://127.0.0.1:8080/api/health >/dev/null && echo API_OK || echo API_START_FAILED"
    & ssh @sshArgs $remote $apiCmd
}

if (-not $SkipCaddy) {
    $caddyLocal = Join-Path $LocalPath "Caddyfile"
    if (Test-Path $caddyLocal) {
        Write-Host "  -> Caddyfile" -ForegroundColor DarkGray
        & scp @scpArgs $caddyLocal "${remote}:/home/stef/Caddyfile.new"
        $caddyCmd = "sudo -n cp /home/stef/Caddyfile.new /etc/caddy/Caddyfile; sudo -n systemctl reload caddy"
        & ssh @sshArgs $remote $caddyCmd
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Caddy reload mislukt - run eenmalig: bash ~/setup-deploy.sh" -ForegroundColor Yellow
        }
        else {
            Write-Host "  Caddy herladen OK" -ForegroundColor DarkGray
        }
    }
}

$verifyCmd = "test -w ${RemotePath}/index.html; echo DEPLOY_WRITE_OK"
& ssh @sshArgs $remote $verifyCmd
if ($LASTEXITCODE -ne 0) {
    Write-Host "Schrijftest mislukt - run eenmalig: bash ~/setup-deploy.sh" -ForegroundColor Red
    exit 1
}

Write-Host "Klaar! https://www.home-labe.com/" -ForegroundColor Green