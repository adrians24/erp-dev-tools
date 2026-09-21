[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'Invoke-SqlServerQuery.ps1'
function Invoke-Probe([string[]] $ProbeArguments) {
    $output = @(& powershell -NoProfile -ExecutionPolicy Bypass -File $runner @ProbeArguments 2>&1)
    return @{ ExitCode = $LASTEXITCODE; Text = ($output -join "`n").Trim() }
}
$failure = Invoke-Probe @('-Query', ";THROW 51000, 'Intentional helper regression probe', 1;")
if ($failure.ExitCode -eq 0) { throw 'SQL error was reported as process success.' }
$long = Invoke-Probe @('-HideHeaders', '-Query', "SET NOCOUNT ON; SELECT CAST(REPLICATE(N'x',600) AS nvarchar(max));")
if ($long.ExitCode -ne 0 -or $long.Text.Trim().Length -ne 600) { throw 'Text output truncated a SQL value.' }
$result = Invoke-Probe @('-AsJson', '-Query', "SELECT CAST(REPLICATE(N'x',600) AS nvarchar(max)) AS LongValue, CAST(NULL AS int) AS Missing; SELECT 42 AS Answer;")
$json = $result.Text | ConvertFrom-Json
if ($result.ExitCode -ne 0 -or !$json.ok -or $json.resultSets.Count -ne 2 -or $json.resultSets[0].rows[0].LongValue.Length -ne 600 -or $null -ne $json.resultSets[0].rows[0].Missing -or $json.resultSets[1].rows[0].Answer -ne 42) { throw 'JSON result sets, nulls, or long values were not preserved.' }
$failure = Invoke-Probe @('-AsJson', '-Query', ";THROW 51000, 'Intentional JSON regression probe', 1;")
if ($failure.ExitCode -eq 0 -or ($failure.Text | ConvertFrom-Json).ok) { throw 'JSON mode hid a SQL failure.' }
Write-Output 'Passed SQL text/JSON failures, full values, multiple result sets, and null preservation. No data changed.'
