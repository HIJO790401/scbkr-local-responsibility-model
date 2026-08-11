param(
  [string]$ReleaseDir = "dist\scbkr-windows-desktop-rc",
  [switch]$Offline,
  [switch]$SkipPythonDependencyInstall
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
  throw "The SCBKR desktop release candidate build requires Windows. Run it on windows-latest or a Windows machine."
}

Write-Host "Building SCBKR Windows desktop release candidate package..."

$RepoRoot = (Resolve-Path -LiteralPath ".").Path
$DistRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "dist"))
$ReleaseRoot = if ([System.IO.Path]::IsPathRooted($ReleaseDir)) {
  [System.IO.Path]::GetFullPath($ReleaseDir)
} else {
  [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $ReleaseDir))
}
$DistPrefix = $DistRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not $ReleaseRoot.StartsWith($DistPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "ReleaseDir must resolve inside the repository dist directory: $ReleaseRoot"
}
if (Test-Path -LiteralPath $ReleaseRoot) {
  Remove-Item -LiteralPath $ReleaseRoot -Recurse -Force
}
$ReleaseDir = $ReleaseRoot

if (-not (Test-Path "apps\web\node_modules\vite\bin\vite.js")) {
  $NpmArgs = @("--prefix", "apps/web", "ci")
  if ($Offline) { $NpmArgs += "--offline" }
  & npm @NpmArgs
  if ($LASTEXITCODE -ne 0) { throw "Unable to install Web UI dependencies." }
}
npm --prefix apps/web run build
if ($LASTEXITCODE -ne 0) { throw "SCBKR Web UI build failed." }

$SidecarArgs = @("-ExecutionPolicy", "Bypass", "-File", "scripts/build_api_sidecar_windows.ps1")
if ($SkipPythonDependencyInstall) { $SidecarArgs += "-SkipDependencyInstall" }
& powershell @SidecarArgs
if ($LASTEXITCODE -ne 0) { throw "SCBKR API sidecar build failed." }

$StagedSidecar = "apps\desktop\src-tauri\sidecar\scbkr-api-x86_64-pc-windows-msvc.exe"
if (-not (Test-Path $StagedSidecar)) {
  throw "Tauri sidecar staging file missing before build: $StagedSidecar"
}

if (-not (Test-Path "apps\desktop\node_modules\@tauri-apps\cli\tauri.js")) {
  $NpmArgs = @("--prefix", "apps/desktop", "ci")
  if ($Offline) { $NpmArgs += "--offline" }
  & npm @NpmArgs
  if ($LASTEXITCODE -ne 0) { throw "Unable to install desktop dependencies." }
}
npm --prefix apps/desktop run check:release
if ($LASTEXITCODE -ne 0) { throw "SCBKR desktop release contract failed." }

python scripts/generate_tauri_preview_icon.py

$TauriIcon = "apps\desktop\src-tauri\icons\icon.ico"
$TauriIconError = "SCBKR Tauri Windows icon missing or invalid: apps\desktop\src-tauri\icons\icon.ico"
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

$PriorDesktopExe = "apps\desktop\src-tauri\target\release\scbkr_desktop.exe"
if (Test-Path -LiteralPath $PriorDesktopExe) {
  Remove-Item -LiteralPath $PriorDesktopExe -Force
}
$PriorNsisInstallers = @(Get-ChildItem -Path "apps\desktop\src-tauri\target\release\bundle\nsis" -Filter "*.exe" -File -ErrorAction SilentlyContinue)
foreach ($PriorInstaller in $PriorNsisInstallers) {
  Remove-Item -LiteralPath $PriorInstaller.FullName -Force
}

$TauriBuildStartedAt = Get-Date
$TauriExitCode = 0
Push-Location apps/desktop
try {
  npm run tauri:build:rc
  $TauriExitCode = $LASTEXITCODE
} finally {
  Pop-Location
}
if ($TauriExitCode -ne 0) {
  throw "SCBKR Tauri desktop build failed with exit code $TauriExitCode. No previous executable may be staged as the new release."
}

$NsisInstallers = @(Get-ChildItem -Path "apps\desktop\src-tauri\target\release\bundle\nsis" -Filter "*.exe" -File -ErrorAction SilentlyContinue)
$DesktopExecutables = @(Get-Item -LiteralPath "apps\desktop\src-tauri\target\release\scbkr_desktop.exe" -ErrorAction SilentlyContinue)
$DesktopOutputs = @($NsisInstallers + $DesktopExecutables)
if ($DesktopOutputs.Count -eq 0) {
  throw "Tauri build completed but no desktop executable or NSIS installer was found under apps\desktop\src-tauri\target\release."
}
if (@($DesktopOutputs | Where-Object { $_.LastWriteTime -lt $TauriBuildStartedAt.AddSeconds(-2) }).Count -gt 0) {
  throw "Tauri build returned stale desktop output. Refusing to stage a previous release artifact."
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$DesktopDir = Join-Path $ReleaseDir "desktop"
New-Item -ItemType Directory -Force -Path $DesktopDir | Out-Null
foreach ($Output in $DesktopOutputs) {
  Copy-Item -Force $Output.FullName $DesktopDir
}
$SidecarExe = "dist\windows-runtime\sidecar\scbkr-api.exe"
if (-not (Test-Path $SidecarExe)) {
  throw "SCBKR sidecar executable missing: $SidecarExe"
}
Copy-Item -Force $SidecarExe $ReleaseDir
Copy-Item -Force $StagedSidecar $ReleaseDir
$WebDistDir = Join-Path $ReleaseDir "web-dist"
New-Item -ItemType Directory -Force -Path $WebDistDir | Out-Null
Copy-Item -Recurse -Force "apps\web\dist\*" $WebDistDir
@"
SCBKR Windows Desktop Release Candidate

This is a release candidate package. Code signing may be configured by the distributor.

What is included / not included:
- Includes the SCBKR desktop executable and NSIS release candidate installer.
- Includes the local scbkr-api.exe sidecar.
- Does not include any bundled model. No bundled model is shipped in this artifact.
- Does not include any bundled API key. No bundled API key is shipped in this artifact.
- Does not include code signing.
- Does not include auto-update.

Windows Defender / SmartScreen may warn because this release candidate is not code-signed. Code signing is still required before Microsoft Store submission.

SCBKR FREE is a model-assisted local rule operating system. Connect LM Studio, Ollama, or an OpenAI-compatible endpoint before asking SCBKR to author a rulebook. A disconnected or invalid model is reported as unavailable; the product does not replace model authorship with a hidden rule template.

After opening the app, you should see the local Runtime online and SCBKR 2.3 FREE. The API sidecar binds to 127.0.0.1:8787 by default.

Product verification order:
1. Open the App.
2. Confirm Health online.
3. Open Model Settings and connect a supported model endpoint.
4. Run the model connection test.
5. Ask in natural language to create a reusable rule.
6. Review and edit the model-authored S/C/B/K/R confirmation form.
7. Confirm that the model cannot sign, store, or activate the rule.
8. Apply the user signature and complete owner review.
9. Confirm storage into LOGIC, CORPUS, MEMORY, and VECTOR.
10. Ask a follow-up question and confirm the signed rule is matched.
11. Confirm the answer used current_rule_package instead of chat history.
12. Inspect the token and context audit shown in the interface.

Expected product output:
- draft_source=model_assisted_rulebook
- model_used=true
- model_schema_valid=true
- validator_passed=true
- requires_user_signature=true
- model_signature_allowed=false
- token measurement basis is shown in the interface

If the API is offline, confirm that the desktop release candidate package launched the scbkr-api.exe sidecar. Normal users do not need Python, Node, npm, uvicorn, or PowerShell. They do need access to a supported local or cloud model endpoint for real model-assisted rulebook authoring.
"@ | Set-Content -Encoding UTF8 (Join-Path $ReleaseDir "README_RELEASE.md")
"2.3.0" | Set-Content -Encoding UTF8 (Join-Path $ReleaseDir "VERSION")
@{
  version = "2.3.0"
  desktop_stage = "SCBKR-2.3-free-store-candidate"
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
  model_assisted_rulebook_required = $true
  token_meter_included = $true
  public_edition = "FREE"
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $ReleaseDir "BUILD_METADATA.json")

foreach ($RequiredFile in @("README_RELEASE.md", "VERSION", "BUILD_METADATA.json", "scbkr-api.exe")) {
  if (-not (Test-Path (Join-Path $ReleaseDir $RequiredFile))) {
    throw "SCBKR release candidate artifact missing required file: $RequiredFile"
  }
}
if ((Get-ChildItem -Path $DesktopDir -Filter "*.exe" -File -ErrorAction SilentlyContinue).Count -eq 0) {
  throw "SCBKR release candidate artifact missing desktop executable or NSIS installer in desktop directory."
}

Write-Host "Release candidate package staged at $ReleaseDir"
