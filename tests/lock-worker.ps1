param($Common, $MutexName, $Probe, $Id, $Fail)
$ErrorActionPreference = 'Stop'
. $Common
$script:ErpEnvironmentMutexName = $MutexName
[IO.File]::WriteAllText((Join-Path $Probe "ready-$Id"), 'ready')
$timer = [Diagnostics.Stopwatch]::StartNew()
while (!(Test-Path -LiteralPath (Join-Path $Probe 'start'))) {
    if ($timer.Elapsed.TotalSeconds -gt 15) { throw 'Start barrier timed out.' }
    Start-Sleep -Milliseconds 25
}
$lease = Enter-ErpEnvironmentLock -TimeoutSeconds 10
try {
    [IO.File]::AppendAllText((Join-Path $Probe 'events.txt'), "enter:$Id`n")
    Start-Sleep -Milliseconds 80
    if ($Fail -eq 'yes') { throw 'Intentional package lock failure' }
    [IO.File]::AppendAllText((Join-Path $Probe 'events.txt'), "exit:$Id`n")
}
finally { Exit-ErpEnvironmentLock -Lease $lease }
