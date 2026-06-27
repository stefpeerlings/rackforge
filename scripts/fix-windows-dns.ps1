# Eenmalig als Administrator uitvoeren (rechtermuisknop → Run with PowerShell / Als administrator)
# Zorgt dat netwerkengineer.com lokaal naar 10.0.40.12 wijst.

$ErrorActionPreference = "Stop"
$ip = "10.0.40.12"
$domain = "netwerkengineer.com"
$wifi = "WiFi"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Start dit script als Administrator." -ForegroundColor Red
    exit 1
}

Write-Host "DNS op $wifi instellen..." -ForegroundColor Cyan
netsh interface ipv4 set dnsservers name="$wifi" static $ip validate=no | Out-Null
netsh interface ipv6 set dnsservers name="$wifi" static $ip validate=no | Out-Null

$hostsPath = "$env:windir\System32\drivers\etc\hosts"
$marker = "# RackForge LAN"
$entry = "$ip $domain www.$domain"
$hosts = Get-Content $hostsPath -ErrorAction SilentlyContinue
if ($hosts -notmatch [regex]::Escape($domain)) {
    Add-Content -Path $hostsPath -Value "`n$marker`n$entry"
    Write-Host "Hosts-bestand bijgewerkt." -ForegroundColor Green
} else {
    Write-Host "Hosts-bestand bevat $domain al." -ForegroundColor DarkGray
}

ipconfig /flushdns | Out-Null
Clear-DnsClientCache -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Test:" -ForegroundColor Cyan
Resolve-DnsName $domain -Type A -DnsOnly | Format-Table Name, IPAddress -AutoSize
Write-Host "Open: https://$domain/" -ForegroundColor Green