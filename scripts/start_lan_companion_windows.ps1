param(
  [int]$Port = 8787,
  [switch]$SmokeOnly
)
$ErrorActionPreference = "Stop"
$Token = [Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(24)).ToLowerInvariant()
$env:SCBKR_LAN_COMPANION_ENABLED = "1"
$env:SCBKR_API_HOST = "0.0.0.0"
$env:SCBKR_API_PORT = "$Port"
$env:SCBKR_COMPANION_TOKEN = $Token
$RepoWebDist = Join-Path (Get-Location) "apps\web\dist"
$ReleaseWebDist = Join-Path (Get-Location) "web-dist"
if (Test-Path (Join-Path $RepoWebDist "index.html")) { $env:SCBKR_WEB_DIST_DIR = $RepoWebDist }
elseif (Test-Path (Join-Path $ReleaseWebDist "index.html")) { $env:SCBKR_WEB_DIST_DIR = $ReleaseWebDist }
$Ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1 -ExpandProperty IPAddress)
if (-not $Ip) { $Ip = "192.168.x.x" }
Write-Host "SCBKR LAN Companion Mode"
Write-Host "Use only on trusted Wi-Fi. Do not share this URL publicly."
Write-Host "Phone is only an operation entry; owner signature, review, second confirmation, and Data Center gates still apply."
Write-Host "URL: http://$Ip`:$Port/?companion_token=$Token"
if ($SmokeOnly) { return }
if (Test-Path ".\scbkr-api.exe") { & ".\scbkr-api.exe" } else { python -m apps.api.sidecar }
