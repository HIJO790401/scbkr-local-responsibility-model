param(
  [string]$Python = "python",
  [string]$OutDir = "dist\windows-runtime\sidecar",
  [string]$TauriSidecarDir = "apps\desktop\src-tauri\sidecar",
  [string]$TargetTriple = "x86_64-pc-windows-msvc",
  [switch]$SkipDependencyInstall,
  [switch]$SkipSmokeTest
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
  throw "The SCBKR API sidecar build requires Windows."
}

Write-Host "Building SCBKR FastAPI sidecar executable..."
& $Python -c "import fastapi, uvicorn, PyInstaller"
if ($LASTEXITCODE -ne 0) {
  if ($SkipDependencyInstall) {
    throw "FastAPI, Uvicorn, or PyInstaller is missing and -SkipDependencyInstall was supplied."
  }
  & $Python -m pip install --no-build-isolation -e . pyinstaller
  if ($LASTEXITCODE -ne 0) {
    throw "Unable to install the API sidecar build dependencies."
  }
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
& $Python -m PyInstaller `
  --distpath $OutDir `
  --workpath "build\pyinstaller" `
  --noconfirm `
  scripts\scbkr_api_sidecar.spec
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller failed to build the SCBKR API sidecar."
}

$Exe = Join-Path $OutDir "scbkr-api.exe"
if (-not (Test-Path $Exe)) {
  throw "Expected sidecar executable was not produced: $Exe"
}
Write-Host "Sidecar built: $Exe"

New-Item -ItemType Directory -Force -Path $TauriSidecarDir | Out-Null
$StagedSidecar = Join-Path $TauriSidecarDir "scbkr-api-$TargetTriple.exe"
Copy-Item -Force $Exe $StagedSidecar
if (-not (Test-Path $StagedSidecar)) {
  throw "Expected Tauri sidecar staging file was not produced: $StagedSidecar"
}
Write-Host "Tauri sidecar staged: $StagedSidecar"

if (-not $SkipSmokeTest) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File scripts\smoke_api_sidecar_windows.ps1 -ExePath $Exe -TimeoutSeconds 60
  if ($LASTEXITCODE -ne 0) {
    throw "Packaged API sidecar smoke test failed."
  }
} else {
  Write-Warning "Skipping sidecar runtime smoke test because -SkipSmokeTest was supplied."
}
