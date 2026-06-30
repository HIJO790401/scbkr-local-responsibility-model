$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$npm = "C:\Program Files\nodejs\npm.cmd"
$report = Join-Path $repo "apps\web\playwright-report\index.html"

& $npm --prefix apps/web run test:ui
$testExitCode = $LASTEXITCODE

if (Test-Path -LiteralPath $report) {
  Start-Process $report
}

if ($testExitCode -ne 0) {
  throw "UI acceptance failed. Opened the visual report for review."
}

Write-Host "Desktop and mobile UI acceptance passed." -ForegroundColor Green
