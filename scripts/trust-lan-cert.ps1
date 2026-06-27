# Eenmalig als Administrator — vertrouw het lokale RackForge-certificaat in Chrome/Edge.
$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Start dit script als Administrator." -ForegroundColor Red
    exit 1
}

$caPath = Join-Path $PSScriptRoot "lan-rootCA.pem"
if (-not (Test-Path $caPath)) {
    Write-Host "CA-bestand niet gevonden: $caPath" -ForegroundColor Red
    Write-Host "Download eerst van de server: scp stef@10.0.40.12:~/.mkcert/rootCA.pem scripts/lan-rootCA.pem"
    exit 1
}

Import-Certificate -CertStoreLocation Cert:\LocalMachine\Root -FilePath $caPath | Out-Null
Write-Host "Lokaal CA-certificaat geinstalleerd in Vertrouwde basiscertificeringsinstanties." -ForegroundColor Green

ipconfig /flushdns | Out-Null
Clear-DnsClientCache -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Sluit Chrome volledig af en open opnieuw: https://netwerkengineer.com/" -ForegroundColor Cyan
Write-Host "Werkt het nog niet? Ga naar chrome://net-internals/#hsts en verwijder netwerkengineer.com" -ForegroundColor DarkGray