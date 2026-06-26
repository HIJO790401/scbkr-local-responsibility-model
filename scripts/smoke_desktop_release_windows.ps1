param(
  [string]$ReleaseDir = "dist\scbkr-windows-desktop-rc",
  [string]$ApiBaseUrl = "http://127.0.0.1:8787"
)

$ErrorActionPreference = "Stop"
$OwnerSignature = "smoke-owner-signature"

function Test-IsWindows {
  if ($env:OS -eq "Windows_NT") { return $true }
  if ($env:SYSTEMROOT) { return $true }
  try { return [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows) } catch { return $false }
}
if (-not (Test-IsWindows)) { throw "SCBKR desktop release candidate smoke requires Windows because it launches or checks scbkr-api.exe." }

function Invoke-Json($Method, $Path, $Body = $null) {
  $Params = @{ Method = $Method; Uri = "$ApiBaseUrl$Path"; ContentType = "application/json" }
  if ($null -ne $Body) { $Params.Body = ($Body | ConvertTo-Json -Depth 20) }
  return Invoke-RestMethod @Params
}

$Sidecar = Join-Path $ReleaseDir "scbkr-api.exe"
$Started = $null
try {
  try { Invoke-Json GET "/health" | Out-Null } catch {
    if (-not (Test-Path $Sidecar)) { throw "Sidecar is not running and not found at $Sidecar" }
    $Started = Start-Process -FilePath $Sidecar -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
  }

  $Health = Invoke-Json GET "/health"
  if (-not ($Health.ok -eq $true -or $Health.service -eq "scbkr-api")) { throw "Health did not report alive" }
  $Status = Invoke-Json GET "/api/desktop/status"
  if ($Status.release_candidate_stage -ne "P15-Q-release-candidate") { throw "Unexpected release_candidate_stage: $($Status.release_candidate_stage)" }

  Invoke-Json POST "/api/settings/model" @{ mode = "sandbox" } | Out-Null
  $ModelTest = Invoke-Json POST "/api/model/test"
  if ($ModelTest.external_call_performed -ne $false) { throw "Sandbox model test performed an external call" }

  $Task = Invoke-Json POST "/api/tasks/create" @{ raw_input = "P15-Q release candidate smoke task"; task_type = "workflow" }
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/scbkr"
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/confirm" @{ confirmed_by = "user"; confirmation_statement = "P15-Q smoke confirms SCBKR."; signature = $OwnerSignature }
  if ($Task.confirmed -ne $true) { throw "task confirmed was not true" }
  if ($Task.scbkr.signature_status -ne "owner_signed") { throw "signature_status was not owner_signed" }

  Invoke-Json POST "/api/settings/permissions" @{ model_generate = $true } | Out-Null
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/generate"
  if ($Task.generation_result.external_call_performed -ne $false) { throw "generation performed an external call" }
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/review" @{ review_decision = "pass"; review_message = "release smoke pass" }
  if ($Task.review_passed -ne $true) { throw "review_passed was not true" }

  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/storage-request" @{ signature = $OwnerSignature; selected_targets = @("corpus", "logic", "exports") }
  try {
    Invoke-Json POST "/api/tasks/$($Task.task_id)/storage-confirm" @{ storage_confirmed = $true; confirmed_by = "user"; signature = $OwnerSignature; selected_targets = @("corpus", "logic", "exports") } | Out-Null
    throw "storage-confirm without second_confirm unexpectedly succeeded"
  } catch {
    if ($_.Exception.Message -like "*unexpectedly succeeded*") { throw }
  }
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/storage-confirm" @{ storage_confirmed = $true; second_confirm = $true; confirmed_by = "user"; signature = $OwnerSignature; selected_targets = @("corpus", "logic", "exports") }
  if ($Task.storage_confirmed -ne $true) { throw "storage_confirmed was not true" }
  if ($Task.physical_write_performed -ne $true -and -not $Task.storage_result) { throw "storage physical write was not observed" }

  $Data = Invoke-Json GET "/api/data-center/storage"
  if (($Data.items | Measure-Object).Count -lt 1) { throw "Data Center storage section did not return written data" }

  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/complete" @{ confirmed_by = "user" }
  if ($Task.status -ne "completed") { throw "Task did not complete" }
  Write-Host "SCBKR desktop release candidate smoke passed. task_id=$($Task.task_id)"
} finally {
  if ($Started -and -not $Started.HasExited) { Stop-Process -Id $Started.Id -Force }
}
