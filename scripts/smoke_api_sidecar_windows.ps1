param(
  [string]$ExePath = "dist\windows-runtime\sidecar\scbkr-api.exe",
  [string]$HealthUrl = "http://127.0.0.1:8787/health",
  [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "windows_sidecar_process.ps1")

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
  throw "The packaged sidecar smoke test requires Windows because it launches scbkr-api.exe."
}
if (-not (Test-Path $ExePath)) {
  throw "Sidecar executable not found for smoke test: $ExePath"
}

$env:SCBKR_API_HOST = "127.0.0.1"
$env:SCBKR_API_PORT = "8787"
$env:SCBKR_DESKTOP_RUNTIME = "release-candidate"
$env:SCBKR_DATA_DIR = Join-Path $env:TEMP "scbkr-sidecar-smoke-data"

$sidecarStartedAt = Get-Date
$process = Start-Process -FilePath $ExePath -PassThru -WindowStyle Hidden
try {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    Start-Sleep -Milliseconds 500
    if ($process.HasExited) {
      throw "Sidecar exited before /health became reachable. ExitCode=$($process.ExitCode)"
    }
    try {
      $response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2
      if ($response.ok -eq $true) {
        break
      }
    } catch {
      if ((Get-Date) -gt $deadline) { throw }
    }
  } while ((Get-Date) -lt $deadline)
  if ($response.ok -ne $true) {
    throw "Timed out waiting for sidecar /health: $HealthUrl"
  }

  $baseUri = ([Uri]$HealthUrl).GetLeftPart([System.UriPartial]::Authority)
  $manifest = Invoke-RestMethod -Uri "$baseUri/api/product/manifest?locale=en" -Method Get -TimeoutSec 5
  if ($manifest.product_id -ne "scbkr" -or $manifest.locale -ne "en") {
    throw "Packaged product manifest is missing or invalid."
  }

  $about = Invoke-RestMethod -Uri "$baseUri/api/product/about?topic=identity&locale=en" -Method Get -TimeoutSec 5
  if ($about.source -ne "product_manifest" -or $about.reply -notmatch "SCBKR") {
    throw "Packaged bilingual product identity is unavailable."
  }

  $chatBody = @{
    message = "Who are you? Explain the five SCBKR dimensions."
    locale = "en"
    chat_history = @()
  } | ConvertTo-Json -Depth 4
  $chat = Invoke-RestMethod -Uri "$baseUri/api/chat/general" -Method Post -ContentType "application/json; charset=utf-8" -Body $chatBody -TimeoutSec 10
  if ($chat.reply_source -notlike "product_manifest:*" -or $chat.reply -notmatch "SCBKR") {
    throw "Packaged general chat identity route is unavailable."
  }

  Write-Host "Sidecar smoke test passed: health, packaged manifest, bilingual identity, and chat route."
} finally {
  if ($process) {
    Stop-SCBKRSidecarRun `
      -RootProcessId $process.Id `
      -ExpectedExecutablePath $ExePath `
      -StartedAt $sidecarStartedAt
  }
}
