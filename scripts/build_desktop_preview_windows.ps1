param(
  [string]$PreviewDir = "dist\scbkr-windows-desktop-preview"
)

$ErrorActionPreference = "Stop"

if (-not $IsWindows) {
  throw "P14-C desktop preview packaging requires Windows. Run this script on windows-latest or a Windows machine."
}

Write-Host "Building SCBKR Windows desktop preview package..."

npm --prefix apps/web install
npm --prefix apps/web run build

powershell -ExecutionPolicy Bypass -File scripts/build_api_sidecar_windows.ps1

npm --prefix apps/desktop install --package-lock=false
npm --prefix apps/desktop run check:skeleton

Push-Location apps/desktop
try {
  npm run tauri:build:preview
} finally {
  Pop-Location
}

New-Item -ItemType Directory -Force -Path $PreviewDir | Out-Null
Copy-Item -Force "dist\windows-preview\sidecar\scbkr-api.exe" $PreviewDir
Copy-Item -Recurse -Force "apps\web\dist" (Join-Path $PreviewDir "web-dist")
@"
SCBKR Windows Desktop Preview Package

Unsigned preview package. Not a final production installer.
No model is bundled.
No API key is bundled.
Sandbox Mode works without a model or API key.
LM Studio local endpoint can be connected manually at http://127.0.0.1:1234/v1.
User data is stored under the desktop app data directory via SCBKR_DATA_DIR.
"@ | Set-Content -Encoding UTF8 (Join-Path $PreviewDir "README_PREVIEW.md")
"0.14.0-p14c-preview" | Set-Content -Encoding UTF8 (Join-Path $PreviewDir "VERSION")

Write-Host "Preview package staged at $PreviewDir"
