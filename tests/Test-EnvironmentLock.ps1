[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$common = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\skills\erp-ui\scripts\ErpUi.Common.ps1'))
$probe = Join-Path ([IO.Path]::GetTempPath()) ('erp-lock-test-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $probe
$mutexName = 'Local\ErpDevToolsPackageTest_' + [guid]::NewGuid().ToString('N')
$worker = Join-Path $PSScriptRoot 'lock-worker.ps1'
$processes = [Collections.Generic.List[Diagnostics.Process]]::new()
function Start-Worker([string] $Id, [string] $Fail = 'no') {
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = (Get-Command pwsh).Source
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardError = $true
    foreach ($argument in @('-NoProfile', '-File', $worker, $common, $mutexName, $probe, $Id, $Fail)) { $info.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::Start($info)
    $processes.Add($process)
    return $process
}
try {
    $workers = @(foreach ($id in 1..3) { Start-Worker -Id "$id" })
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while (@(Get-ChildItem -LiteralPath $probe -Filter 'ready-*').Count -ne 3) {
        if ($timer.Elapsed.TotalSeconds -gt 15) { throw 'Workers did not reach the start barrier.' }
        Start-Sleep -Milliseconds 25
    }
    [IO.File]::WriteAllText((Join-Path $probe 'start'), 'start')
    foreach ($process in $workers) {
        if (!$process.WaitForExit(20000)) { throw 'Concurrent lock test timed out.' }
        if ($process.ExitCode -ne 0) { throw $process.StandardError.ReadToEnd() }
    }
    $events = @(Get-Content -LiteralPath (Join-Path $probe 'events.txt'))
    if ($events.Count -ne 6) { throw 'A lock worker did not complete.' }
    $owners = @()
    for ($index = 0; $index -lt 6; $index += 2) {
        $owner = $events[$index] -replace '^enter:', ''
        if ($events[$index] -ne "enter:$owner" -or $events[$index + 1] -ne "exit:$owner") { throw 'Concurrent processes overlapped inside the protected operation.' }
        $owners += $owner
    }
    if (@($owners | Sort-Object -Unique).Count -ne 3) { throw 'A process did not acquire the lock.' }
    $failure = Start-Worker -Id 'failure' -Fail 'yes'
    if (!$failure.WaitForExit(20000) -or $failure.ExitCode -eq 0) { throw 'Intentional failure was not observed.' }
    if ($failure.StandardError.ReadToEnd() -notmatch 'Intentional package lock failure') { throw 'Worker failed for an unexpected reason.' }
    $recovery = Start-Worker -Id 'recovery'
    if (!$recovery.WaitForExit(20000) -or $recovery.ExitCode -ne 0) { throw 'Lock was not available after the failing worker.' }
    Write-Output 'Passed three-process exclusion and lock release after an exception using an isolated test mutex.'
}
finally {
    foreach ($process in $processes) {
        if (!$process.HasExited) { $process.Kill($true); $process.WaitForExit() }
        $process.Dispose()
    }
    $resolvedProbe = [IO.Path]::GetFullPath($probe)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    if ((Split-Path -Parent $resolvedProbe) -eq $tempRoot -and (Split-Path -Leaf $resolvedProbe) -like 'erp-lock-test-*') {
        Remove-Item -LiteralPath $resolvedProbe -Recurse -Force
    }
}
