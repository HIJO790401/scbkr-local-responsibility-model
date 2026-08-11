param(
  [string]$SidecarPath = "dist\windows-runtime\sidecar\scbkr-api.exe",
  [string]$BaseUrl = "http://127.0.0.1:8787",
  [int]$TimeoutSeconds = 90,
  [switch]$OpenReport
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$report = Join-Path $repo "apps\web\playwright-report\index.html"
$sidecar = Join-Path $repo $SidecarPath
$dataDir = Join-Path $repo "test-results\ui-acceptance-runtime"
. (Join-Path $PSScriptRoot "windows_sidecar_process.ps1")

if (-not (Test-Path -LiteralPath $sidecar)) {
  throw "Packaged API sidecar was not found: $sidecar"
}

$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$uri = [Uri]$BaseUrl
$env:SCBKR_API_HOST = $uri.Host
$env:SCBKR_API_PORT = [string]$uri.Port
$env:SCBKR_DESKTOP_RUNTIME = "ui-acceptance"
$env:SCBKR_DATA_DIR = $dataDir
$env:SCBKR_UI_EXTERNAL_SERVER = "1"
$env:SCBKR_UI_BASE_URL = $BaseUrl

$sidecarStartedAt = Get-Date
$process = Start-Process -FilePath $sidecar -PassThru -WindowStyle Hidden
try {
  $healthUrl = "$BaseUrl/health"
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $health = $null
  do {
    Start-Sleep -Milliseconds 400
    if ($process.HasExited) {
      throw "Packaged sidecar exited before UI acceptance. ExitCode=$($process.ExitCode)"
    }
    try {
      $health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2
    } catch {
      $health = $null
    }
  } while ($health.ok -ne $true -and (Get-Date) -lt $deadline)

  if ($health.ok -ne $true) {
    throw "Timed out waiting for packaged product: $healthUrl"
  }

  Push-Location $repo
  try {
    & $npm --prefix apps/web run test:ui -- --reporter=line
    if ($LASTEXITCODE -ne 0) {
      throw "UI acceptance failed with exit code $LASTEXITCODE."
    }
  } finally {
    Pop-Location
  }
} finally {
  if ($process) {
    Stop-SCBKRSidecarRun `
      -RootProcessId $process.Id `
      -ExpectedExecutablePath $sidecar `
      -StartedAt $sidecarStartedAt
  }
  Remove-Item Env:SCBKR_UI_EXTERNAL_SERVER -ErrorAction SilentlyContinue
  Remove-Item Env:SCBKR_UI_BASE_URL -ErrorAction SilentlyContinue
}

if ($OpenReport -and (Test-Path -LiteralPath $report)) {
  Start-Process $report
}

Write-Host "Packaged desktop and mobile UI acceptance passed." -ForegroundColor Green
