param(
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$npm = "C:\Program Files\nodejs\npm.cmd"
$uiUrl = "http://127.0.0.1:5500"
$apiUrl = "http://127.0.0.1:8787/health"

function Test-ScbkrUrl([string]$url) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2
    return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
  } catch {
    return $false
  }
}

if (-not (Test-Path -LiteralPath $python)) {
  throw "Python 3.12 not found: $python"
}

if (-not (Test-Path -LiteralPath $npm)) {
  throw "Node.js/npm not found: $npm"
}

if (-not (Test-ScbkrUrl $apiUrl)) {
  Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8787") `
    -WorkingDirectory $repo `
    -WindowStyle Hidden
}

if (-not (Test-ScbkrUrl $uiUrl)) {
  Start-Process -FilePath $npm `
    -ArgumentList @("--prefix", "apps/web", "run", "dev") `
    -WorkingDirectory $repo `
    -WindowStyle Hidden
}

$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
  if ((Test-ScbkrUrl $apiUrl) -and (Test-ScbkrUrl $uiUrl)) {
    $ready = $true
    break
  }
  Start-Sleep -Milliseconds 500
}

if (-not $ready) {
  throw "SCBKR UI or API did not become ready."
}

Write-Host "SCBKR API: online" -ForegroundColor Green
Write-Host "SCBKR UI:  $uiUrl" -ForegroundColor Green

if (-not $NoBrowser) {
  Start-Process $uiUrl
}
