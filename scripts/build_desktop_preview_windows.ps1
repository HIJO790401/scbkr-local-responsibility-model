param(
  [string]$PreviewDir = "dist\scbkr-windows-desktop-preview"
)

$ErrorActionPreference = "Stop"

function Test-IsWindows {
  if ($env:OS -eq "Windows_NT") {
    return $true
  }
  if ($env:SYSTEMROOT) {
    return $true
  }
  try {
    return [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
      [System.Runtime.InteropServices.OSPlatform]::Windows
    )
  } catch {
    return $false
  }
}

if (-not (Test-IsWindows)) {
  throw "P14-C desktop preview packaging requires Windows. Run this script on windows-latest or a Windows machine."
}

Write-Host "Building SCBKR Windows desktop preview package..."

npm --prefix apps/web install
npm --prefix apps/web run build

powershell -ExecutionPolicy Bypass -File scripts/build_api_sidecar_windows.ps1

$StagedSidecar = "apps\desktop\src-tauri\sidecar\scbkr-api-x86_64-pc-windows-msvc.exe"
if (-not (Test-Path $StagedSidecar)) {
  throw "Tauri sidecar staging file missing before build: $StagedSidecar"
}

npm --prefix apps/desktop install --package-lock=false
npm --prefix apps/desktop run check:skeleton

python scripts/generate_tauri_preview_icon.py

$TauriIcon = "apps\desktop\src-tauri\icons\icon.ico"
$TauriIconError = "P14-C Tauri Windows icon missing or invalid: apps\desktop\src-tauri\icons\icon.ico"
if (-not (Test-Path $TauriIcon)) {
  throw $TauriIconError
}
$TauriIconItem = Get-Item $TauriIcon
if ($TauriIconItem.Length -le 0) {
  throw $TauriIconError
}
$TauriIconHeader = [System.IO.File]::ReadAllBytes($TauriIcon)[0..3]
$ExpectedTauriIconHeader = @(0, 0, 1, 0)
for ($Index = 0; $Index -lt 4; $Index++) {
  if ($TauriIconHeader[$Index] -ne $ExpectedTauriIconHeader[$Index]) {
    throw $TauriIconError
  }
}

Push-Location apps/desktop
try {
  npm run tauri:build:preview
} finally {
  Pop-Location
}

$NsisInstallers = @(Get-ChildItem -Path "apps\desktop\src-tauri\target\release\bundle\nsis" -Filter "*.exe" -File -ErrorAction SilentlyContinue)
$DesktopExecutables = @(Get-ChildItem -Path "apps\desktop\src-tauri\target\release" -Filter "*.exe" -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "scbkr-api-x86_64-pc-windows-msvc.exe" })
$DesktopOutputs = @($NsisInstallers + $DesktopExecutables)
if ($DesktopOutputs.Count -eq 0) {
  throw "Tauri build completed but no desktop executable or NSIS installer was found under apps\desktop\src-tauri\target\release."
}

New-Item -ItemType Directory -Force -Path $PreviewDir | Out-Null
$DesktopDir = Join-Path $PreviewDir "desktop"
New-Item -ItemType Directory -Force -Path $DesktopDir | Out-Null
foreach ($Output in $DesktopOutputs) {
  Copy-Item -Force $Output.FullName $DesktopDir
}
Copy-Item -Force "dist\windows-preview\sidecar\scbkr-api.exe" $PreviewDir
Copy-Item -Force $StagedSidecar $PreviewDir
Copy-Item -Recurse -Force "apps\web\dist" (Join-Path $PreviewDir "web-dist")
@"
SCBKR Windows Desktop Preview Package

Unsigned preview package. Not a production installer and not a formal production release.
No model is bundled.
No API key is bundled.
Sandbox Mode can run without a model or API key.
LM Studio local endpoint is optional and can be connected manually at http://127.0.0.1:1234/v1.
User data is stored under the desktop app data directory via SCBKR_DATA_DIR.
No code signing is performed.
No auto-update is enabled.
"@ | Set-Content -Encoding UTF8 (Join-Path $PreviewDir "README_PREVIEW.md")
"0.14.0-p14c-preview" | Set-Content -Encoding UTF8 (Join-Path $PreviewDir "VERSION")

Write-Host "Preview package staged at $PreviewDir"
