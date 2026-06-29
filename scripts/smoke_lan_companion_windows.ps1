$ErrorActionPreference = "Stop"
$Sidecar = Get-Content apps\api\sidecar.py -Raw
if ($Sidecar -notmatch 'SCBKR_LAN_COMPANION_ENABLED') { throw "LAN enable guard missing" }
if ($Sidecar -notmatch 'SCBKR_COMPANION_TOKEN') { throw "companion token guard missing" }
$Main = Get-Content apps\api\main.py -Raw
if ($Main -notmatch '_is_public_companion_asset_path') { throw "public LAN asset helper missing" }
if ($Main -notmatch '/assets/') { throw "LAN asset public path missing" }
if ($Main -notmatch 'X-SCBKR-Companion-Token') { throw "API token header guard missing" }
if ($Main -notmatch 'mount_web_dist_if_available') { throw "web UI static serving missing" }
if (-not (Test-Path apps\web\src\apiBase.ts)) { throw "frontend API base matrix helper missing" }
$ApiBase = Get-Content apps\web\src\apiBase.ts -Raw
if ($ApiBase -notmatch 'resolveApiBaseUrl') { throw "frontend API base resolver missing" }
if ($ApiBase -notmatch 'isTauriDesktopHostname') { throw "Tauri desktop hostname helper missing" }
if ($ApiBase -notmatch 'tauri\.localhost') { throw "Tauri desktop hostname contract missing" }
if ($ApiBase -notmatch 'isLoopbackHostname') { throw "frontend loopback helper missing" }
if ($ApiBase -notmatch 'hasCompanionToken') { throw "frontend companion token URL helper missing" }
if ($ApiBase -notmatch 'DEFAULT_API_BASE_URL = "http://127.0.0.1:8787"') { throw "desktop default API base missing" }
$Web = Get-Content apps\web\src\App.tsx -Raw
if ($Web -notmatch 'from "\./apiBase"') { throw "App.tsx must import apiBase helper" }
if ($Web -notmatch 'resolveApiBaseUrl') { throw "App.tsx must import/use resolveApiBaseUrl" }
if ($Web -notmatch 'X-SCBKR-Companion-Token') { throw "companion token request header missing" }
if ($Web -match '/\^https\?:\$/.test\(window.location.protocol\)\) return window.location.origin;') { throw "frontend API base must not return page origin for every http/https page" }
if ($Web -match 'window.location.port === "8787"') { throw "frontend LAN origin must not be restricted to port 8787" }
if ($Web -match 'localhost:5500/health|localhost:5173/api|localhost:5500/api|localhost:5173/health') { throw "localhost dev/preview must not be API origin" }
$Matrix = Get-Content scripts\check_api_base_matrix.mjs -Raw
if ($Matrix -notmatch 'CASE 11' -or $Matrix -notmatch 'CASE 12' -or $Matrix -notmatch 'tauri\.localhost') { throw "API base matrix must include tauri.localhost cases" }
Write-Host "LAN Companion smoke checks passed. For live HTTP checks run start_lan_companion_windows.ps1 and test with/without X-SCBKR-Companion-Token."
