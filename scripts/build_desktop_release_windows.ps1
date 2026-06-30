param(
  [string]$PreviewDir = "dist\scbkr-windows-desktop-rc"
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
  throw "P14-C desktop release candidate packaging requires Windows. Run this script on windows-latest or a Windows machine."
}

Write-Host "Building SCBKR Windows desktop release candidate package..."

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
  npm run tauri:build:rc
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
$SidecarExe = "dist\windows-preview\sidecar\scbkr-api.exe"
if (-not (Test-Path $SidecarExe)) {
  throw "P14-C sidecar executable missing: $SidecarExe"
}
Copy-Item -Force $SidecarExe $PreviewDir
Copy-Item -Force $StagedSidecar $PreviewDir
Copy-Item -Recurse -Force "apps\web\dist" (Join-Path $PreviewDir "web-dist")
@"
SCBKR Windows Desktop Release Candidate

This is a release candidate package. Code signing may be configured by the distributor.

What is included / not included:
- Includes the SCBKR desktop preview app or NSIS preview installer.
- Includes the local scbkr-api.exe sidecar.
- Does not include any bundled model. No bundled model is shipped in this artifact.
- Does not include any bundled API key. No bundled API key is shipped in this artifact.
- Does not include code signing.
- Does not include auto-update.

Windows Defender / SmartScreen may warn because this is an unsigned preview. That warning is expected for this release candidate package and does not mean this is the future formally signed release.

Sandbox Mode is the main P14-C Final test path. It can test the full workflow without a model, without an API key, without LM Studio, without Ollama, and without any external model service. Local model connection is a later model-settings-page feature and is not the main goal of this P14-C Final preview.

After opening the app, you should see Health online. The runtime should show P14-C Windows Desktop Preview. The API sidecar binds to 127.0.0.1:8787.

Sandbox testing order:
1. Open the App.
2. Confirm Health online.
3. Confirm Mode sandbox.
4. Create a task.
5. Generate SCBKR.
6. Confirm the responsibility chain.
7. Enable model_generate.
8. Start generation.
9. Pass review.
10. Generate a storage request.
11. Confirm the storage plan.
12. Confirm SCBKR completion.

Expected Sandbox output:
- sandbox=true
- external_call_performed=false
- model_provider=sandbox_mock_model

If the API is offline, confirm that the desktop release candidate package launched the scbkr-api.exe sidecar. Normal users should not need to run Python, Node, npm, uvicorn, PowerShell, LM Studio, Ollama, or provide an API key for Sandbox Mode.
"@ | Set-Content -Encoding UTF8 (Join-Path $PreviewDir "README_PREVIEW.md")
"2.0.0" | Set-Content -Encoding UTF8 (Join-Path $PreviewDir "VERSION")
@{
  version = "2.0.0"
  desktop_stage = "P15-S-1.0-final-rc"
  built_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  api_base_url = "http://127.0.0.1:8787"
  default_bind_host = "127.0.0.1"
  lan_companion_supported = $true
  lan_companion_default_enabled = $false
  lan_companion_requires_token = $true
  four_store_targets = @("vector", "corpus", "logic", "memory")
  exports_storage_target = $false
  sidecar = "scbkr-api.exe"
  production_release = $false
  code_signed = $false
  auto_update = $false
  bundled_model = $false
  bundled_api_key = $false
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $PreviewDir "BUILD_METADATA.json")

foreach ($RequiredFile in @("README_PREVIEW.md", "VERSION", "BUILD_METADATA.json", "scbkr-api.exe")) {
  if (-not (Test-Path (Join-Path $PreviewDir $RequiredFile))) {
    throw "P14-C release candidate artifact missing required file: $RequiredFile"
  }
}
if ((Get-ChildItem -Path $DesktopDir -Filter "*.exe" -File -ErrorAction SilentlyContinue).Count -eq 0) {
  throw "P14-C release candidate artifact missing desktop executable or NSIS preview installer in desktop directory."
}

Write-Host "Preview package staged at $PreviewDir"
