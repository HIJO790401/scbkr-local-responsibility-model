$ErrorActionPreference = "Stop"
$Sidecar = Get-Content apps\api\sidecar.py -Raw
if ($Sidecar -notmatch 'SCBKR_LAN_COMPANION_ENABLED') { throw "LAN enable guard missing" }
if ($Sidecar -notmatch 'SCBKR_COMPANION_TOKEN') { throw "companion token guard missing" }
$Main = Get-Content apps\api\main.py -Raw
if ($Main -notmatch 'X-SCBKR-Companion-Token') { throw "API token header guard missing" }
if ($Main -notmatch 'mount_web_dist_if_available') { throw "web UI static serving missing" }
$Web = Get-Content apps\web\src\App.tsx -Raw
if ($Web -notmatch 'window.location.origin') { throw "frontend LAN origin default missing" }
if ($Web -notmatch '127.0.0.1:8787') { throw "desktop default API base missing" }
Write-Host "LAN Companion smoke checks passed. For live HTTP checks run start_lan_companion_windows.ps1 and test with/without X-SCBKR-Companion-Token."
