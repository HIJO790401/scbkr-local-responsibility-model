param(
  [string]$PreviewDir = "dist\scbkr-windows-desktop-preview",
  [string]$ApiBaseUrl = "http://127.0.0.1:8787"
)

$ErrorActionPreference = "Stop"

function Test-IsWindows {
  if ($env:OS -eq "Windows_NT") { return $true }
  if ($env:SYSTEMROOT) { return $true }
  try { return [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows) } catch { return $false }
}

if (-not (Test-IsWindows)) { throw "P14-C preview smoke requires Windows because it launches or checks scbkr-api.exe." }

function Invoke-Json($Method, $Path, $Body = $null) {
  $Params = @{ Method = $Method; Uri = "$ApiBaseUrl$Path"; ContentType = "application/json" }
  if ($null -ne $Body) { $Params.Body = ($Body | ConvertTo-Json -Depth 20) }
  return Invoke-RestMethod @Params
}

$Sidecar = Join-Path $PreviewDir "scbkr-api.exe"
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
  if ($Status.desktop_stage -ne "P14-C-preview") { throw "Unexpected desktop_stage: $($Status.desktop_stage)" }

  $Model = Invoke-Json POST "/api/settings/model" @{ mode = "sandbox" }
  $ModelTest = Invoke-Json POST "/api/model/test"
  if ($ModelTest.external_call_performed -ne $false) { throw "Sandbox model test performed an external call" }

  $Task = Invoke-Json POST "/api/tasks/create" @{ raw_input = "P14-C fresh unzip smoke task"; task_type = "workflow" }
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/scbkr"
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/confirm" @{ confirmed_by = "user"; confirmation_statement = "P14-C smoke confirms SCBKR."; signature = "smoke" }
  Invoke-Json POST "/api/settings/permissions" @{ model_generate = $true } | Out-Null
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/generate"
  if ($Task.generation_result.sandbox -ne $true) { throw "generation_result.sandbox was not true" }
  if ($Task.generation_result.external_call_performed -ne $false) { throw "generation_result.external_call_performed was not false" }
  if ($Task.generation_result.model_provider -ne "sandbox_mock_model") { throw "Unexpected provider" }
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/review" @{ review_decision = "pass"; review_message = "smoke pass" }
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/storage-request"
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/storage-confirm" @{ storage_confirmed = $true; confirmed_by = "user"; signature = "smoke-signature"; selected_targets = @("corpus", "logic", "exports") }
  $Task = Invoke-Json POST "/api/tasks/$($Task.task_id)/complete" @{ confirmed_by = "user" }
  if ($Task.status -ne "completed") { throw "Task did not complete" }

  $DataDir = $Status.data_dir
  if (-not $DataDir) { $DataDir = $env:SCBKR_DATA_DIR }
  if ($DataDir -and -not (Test-Path $DataDir)) { throw "data_dir not found: $DataDir" }
  Write-Host "P14-C preview smoke passed. task_id=$($Task.task_id)"
} finally {
  if ($Started -and -not $Started.HasExited) { Stop-Process -Id $Started.Id -Force }
}
