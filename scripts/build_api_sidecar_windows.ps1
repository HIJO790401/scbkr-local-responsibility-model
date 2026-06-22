param(
  [string]$Python = "python",
  [string]$OutDir = "dist\windows-preview\sidecar",
  [string]$TauriSidecarDir = "apps\desktop\src-tauri\sidecar",
  [string]$TargetTriple = "x86_64-pc-windows-msvc",
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
  throw "P14-C API sidecar onefile build requires Windows. This script is a Windows preview packaging script."
}

Write-Host "Building SCBKR FastAPI sidecar preview executable..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -e . pyinstaller

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
& $Python -m PyInstaller `
  --distpath $OutDir `
  --workpath "build\pyinstaller" `
  --noconfirm `
  scripts\scbkr_api_sidecar.spec

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
  powershell -ExecutionPolicy Bypass -File scripts\smoke_api_sidecar_windows.ps1 -ExePath $Exe
} else {
  Write-Warning "Skipping sidecar runtime smoke test because -SkipSmokeTest was supplied."
}
