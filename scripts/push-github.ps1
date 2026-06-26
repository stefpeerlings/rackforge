# Eenmalig: maak private GitHub-repo en push
# Vereist: gh auth login
param(
    [string]$RepoName = "rackforge",
    [ValidateSet("private", "public")]
    [string]$Visibility = "private"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$git = "C:\Program Files\Git\bin\git.exe"
$gh = "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe"
if (-not (Test-Path $gh)) { $gh = "C:\Program Files\GitHub CLI\gh.exe" }

Push-Location $Root
try {
    & $gh auth status 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "not logged in" }
} catch {
    Write-Host "Niet ingelogd bij GitHub. Run eerst:" -ForegroundColor Yellow
    Write-Host "  gh auth login" -ForegroundColor Cyan
    exit 1
}

$ghUser = (& $gh api user -q .login).Trim()

if (-not (Test-Path ".git")) {
    & $git init -b main
}

& $git add -A
$status = & $git status --porcelain
if ($status) {
    & $git commit -m "Initial commit: RackForge site + API"
}

$repoSlug = "${ghUser}/${RepoName}"
$view = & $gh repo view $repoSlug 2>&1
if ($LASTEXITCODE -ne 0) {
    & $gh repo create $RepoName --$Visibility --source=. --remote=origin `
        --description "RackForge website and admin API"
} else {
    $remote = & $git remote get-url origin 2>$null
    if (-not $remote) {
        & $git remote add origin "https://github.com/${repoSlug}.git"
    }
}

& $git push -u origin main
Write-Host "Klaar: https://github.com/${repoSlug} ($Visibility)" -ForegroundColor Green
} finally {
    Pop-Location
}