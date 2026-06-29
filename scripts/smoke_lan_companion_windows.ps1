$ErrorActionPreference = "Stop"
$Sidecar = Get-Content apps\api\sidecar.py -Raw
if ($Sidecar -notmatch 'SCBKR_LAN_COMPANION_ENABLED') { throw "LAN enable guard missing" }
if ($Sidecar -notmatch 'SCBKR_COMPANION_TOKEN') { throw "companion token guard missing" }
$Main = Get-Content apps\api\main.py -Raw
if ($Main -notmatch '_is_public_companion_asset_path') { throw "public LAN asset helper missing" }
if ($Main -notmatch '/assets/') { throw "LAN asset public path missing" }
if ($Main -notmatch 'X-SCBKR-Companion-Token') { throw "API token header guard missing" }
if ($Main -notmatch 'mount_web_dist_if_available') { throw "web UI static serving missing" }
$Web = Get-Content apps\web\src\App.tsx -Raw
if ($Web -match 'window.location.port === "8787"') { throw "frontend LAN origin must not be restricted to port 8787" }
if ($Web -notmatch 'window.location.origin') { throw "frontend LAN origin default missing" }
if ($Web -notmatch 'DEFAULT_API_BASE_URL = "http://127.0.0.1:8787"') { throw "desktop default API base missing" }
Write-Host "LAN Companion smoke checks passed. For live HTTP checks run start_lan_companion_windows.ps1 and test with/without X-SCBKR-Companion-Token."
