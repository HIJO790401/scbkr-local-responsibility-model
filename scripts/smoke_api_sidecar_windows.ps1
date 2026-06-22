param(
  [string]$ExePath = "dist\windows-preview\sidecar\scbkr-api.exe",
  [string]$HealthUrl = "http://127.0.0.1:8787/health",
  [int]$TimeoutSeconds = 30
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
  throw "P14-C sidecar smoke test requires Windows because it launches scbkr-api.exe."
}
if (-not (Test-Path $ExePath)) {
  throw "Sidecar executable not found for smoke test: $ExePath"
}

$env:SCBKR_API_HOST = "127.0.0.1"
$env:SCBKR_API_PORT = "8787"
$env:SCBKR_DESKTOP_PREVIEW = "1"
$env:SCBKR_DATA_DIR = Join-Path $env:TEMP "scbkr-sidecar-smoke-data"

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
        Write-Host "Sidecar smoke test passed: $HealthUrl"
        exit 0
      }
    } catch {
      if ((Get-Date) -gt $deadline) { throw }
    }
  } while ((Get-Date) -lt $deadline)
  throw "Timed out waiting for sidecar /health: $HealthUrl"
} finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit()
  }
}
