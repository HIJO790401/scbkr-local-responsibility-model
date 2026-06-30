param(
  [string]$ApiBase = "http://127.0.0.1:8787",
  [switch]$Strict
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Results = [System.Collections.Generic.List[object]]::new()

function Add-Result {
  param([string]$Id, [bool]$Ready, [string]$Detail, [string]$Kind = "engineering")
  $Results.Add([pscustomobject]@{
    id = $Id
    ready = $Ready
    kind = $Kind
    detail = $Detail
  })
}

function Test-RepoPath {
  param([string]$Id, [string]$RelativePath)
  $FullPath = Join-Path $RepoRoot $RelativePath
  Add-Result -Id $Id -Ready (Test-Path $FullPath) -Detail $RelativePath
}

Push-Location $RepoRoot
try {
  Test-RepoPath -Id "launch_backend" -RelativePath "core\launch\readiness.py"
  Test-RepoPath -Id "rule_state_runtime" -RelativePath "core\rule_state\runtime.py"
  Test-RepoPath -Id "web_runtime" -RelativePath "core\tools\web_runtime.py"
  Test-RepoPath -Id "launch_guide" -RelativePath "docs\SCBKR_2_1_LAUNCH_SETUP.md"
  Test-RepoPath -Id "web_build" -RelativePath "apps\web\dist\index.html"

  $ManifestPath = Join-Path $RepoRoot "config\product_manifest.json"
  $Manifest = [System.IO.File]::ReadAllText($ManifestPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
  Add-Result -Id "manifest_version" -Ready ($Manifest.version -eq "2.1.0") -Detail "product_manifest=$($Manifest.version)"

  try {
    $Health = Invoke-RestMethod -Uri "$ApiBase/health" -TimeoutSec 3
    Add-Result -Id "api" -Ready ($Health.ok -eq $true) -Detail "$ApiBase/health"
  } catch {
    Add-Result -Id "api" -Ready $false -Detail "API not reachable at $ApiBase"
  }

  try {
    $Launch = Invoke-RestMethod -Uri "$ApiBase/api/launch/readiness" -TimeoutSec 3
    foreach ($Check in $Launch.checks) {
      Add-Result -Id "external_$($Check.id)" -Ready ([bool]$Check.ready) -Detail "owner configuration: $($Check.id)" -Kind "external"
    }
  } catch {
    Add-Result -Id "external_readiness" -Ready $false -Detail "Launch readiness endpoint unavailable" -Kind "external"
  }
} finally {
  Pop-Location
}

$Results | Format-Table id, ready, kind, detail -AutoSize

$EngineeringFailures = @($Results | Where-Object { $_.kind -eq "engineering" -and -not $_.ready })
$EngineeringReady = @($Results | Where-Object { $_.kind -eq "engineering" -and $_.ready })
$ExternalPending = @($Results | Where-Object { $_.kind -eq "external" -and -not $_.ready })

Write-Host ""
Write-Host "Engineering checks: $($EngineeringReady.Count) ready, $($EngineeringFailures.Count) failed"
Write-Host "External owner items pending: $($ExternalPending.Count)"

if ($Strict -and $EngineeringFailures.Count -gt 0) {
  exit 1
}
