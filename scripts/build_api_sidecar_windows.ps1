param(
  [string]$Python = "python",
  [string]$OutDir = "dist\windows-preview\sidecar"
)

$ErrorActionPreference = "Stop"

if (-not $IsWindows) {
  throw "P14-C API sidecar onefile build requires Windows. This script is a Windows preview packaging script."
}

Write-Host "Building SCBKR FastAPI sidecar preview executable..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -e . pyinstaller

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
& $Python -m PyInstaller `
  --onefile `
  --name scbkr-api `
  --distpath $OutDir `
  --workpath "build\pyinstaller" `
  --specpath "build\pyinstaller" `
  apps\api\sidecar.py

$Exe = Join-Path $OutDir "scbkr-api.exe"
if (-not (Test-Path $Exe)) {
  throw "Expected sidecar executable was not produced: $Exe"
}
Write-Host "Sidecar built: $Exe"
