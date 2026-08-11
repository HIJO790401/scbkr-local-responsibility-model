function Stop-SCBKRSidecarRun {
  param(
    [Parameter(Mandatory = $true)]
    [int]$RootProcessId,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedExecutablePath,
    [Parameter(Mandatory = $true)]
    [datetime]$StartedAt
  )

  $expectedPath = [System.IO.Path]::GetFullPath($ExpectedExecutablePath)
  $processName = [System.IO.Path]::GetFileNameWithoutExtension($expectedPath)
  $startedCutoff = $StartedAt.AddSeconds(-2)
  $deadline = (Get-Date).AddSeconds(5)

  do {
    $matchingIds = @()
    foreach ($candidate in @(Get-Process -Name $processName -ErrorAction SilentlyContinue)) {
      try {
        $candidatePath = [System.IO.Path]::GetFullPath($candidate.Path)
        if (
          $candidatePath -eq $expectedPath -and
          ($candidate.Id -eq $RootProcessId -or $candidate.StartTime -ge $startedCutoff)
        ) {
          $matchingIds += $candidate.Id
        }
      } catch {
        # The process may exit while its properties are being inspected.
      }
    }

    $matchingIds = @($matchingIds | Sort-Object -Unique)
    if ($matchingIds.Count -eq 0) {
      return
    }

    Stop-Process -Id $matchingIds -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 150
  } while ((Get-Date) -lt $deadline)

  throw "Unable to stop the packaged SCBKR sidecar process tree."
}
