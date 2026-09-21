# Internal ADO.NET implementation. Use Invoke-SqlServerQuery.ps1 -AsJson.
param(
    [Parameter(Mandatory)] $Profile,
    [Parameter(Mandatory)][string] $Query,
    [int] $TimeoutSeconds = 120,
    [string] $OutputFile
)
$ErrorActionPreference = 'Stop'
$timer = [Diagnostics.Stopwatch]::StartNew()
$connection = $null
$command = $null
$reader = $null
$result = [ordered]@{
    ok = $false
    environment = $Profile.Environment
    server = $Profile.Server
    database = $Profile.Database
    resultSets = @()
    recordsAffected = $null
    elapsedSeconds = 0
    error = $null
}
try {
    # SQLCMD directives and GO require sqlcmd; do not partially execute such files.
    if ($Query -match '(?im)^\s*(GO(?:\s|$)|:[a-z]|!!)' -or $Query.Contains('$(')) {
        throw 'JSON mode accepts T-SQL batches, not GO or SQLCMD directives/variables. Use text mode for SQLCMD files.'
    }
    $builder = New-Object System.Data.SqlClient.SqlConnectionStringBuilder
    $builder['Data Source'] = $Profile.Server
    $builder['Initial Catalog'] = $Profile.Database
    $builder['TrustServerCertificate'] = $true
    $builder['Encrypt'] = $true
    $builder['Connect Timeout'] = 15
    $builder['Application Name'] = 'Codex.SqlServer.Query'
    $builder['Integrated Security'] = $Profile.Authentication -eq 'Integrated'
    $connection = New-Object System.Data.SqlClient.SqlConnection $builder.ConnectionString
    if (!$builder.IntegratedSecurity) {
        $credential = & (Join-Path $PSScriptRoot 'Get-SqlServerCredential.ps1') -Environment $Profile.Environment
        $credential.Password.MakeReadOnly()
        $connection.Credential = New-Object System.Data.SqlClient.SqlCredential($credential.UserName, $credential.Password)
    }
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandTimeout = $TimeoutSeconds
    $command.CommandText = $Query
    $reader = $command.ExecuteReader()
    $sets = New-Object 'System.Collections.Generic.List[object]'
    do {
        if ($reader.FieldCount -eq 0) { continue }
        $columns = @()
        for ($i = 0; $i -lt $reader.FieldCount; $i++) {
            $name = $reader.GetName($i)
            if (!$name) { $name = "Column$($i + 1)" }
            $baseName = $name
            $suffix = 2
            while ($columns -contains $name) { $name = "$baseName`_$suffix"; $suffix++ }
            $columns += $name
        }
        $rows = New-Object 'System.Collections.Generic.List[object]'
        while ($reader.Read()) {
            $row = [ordered]@{}
            for ($i = 0; $i -lt $reader.FieldCount; $i++) {
                $value = if ($reader.IsDBNull($i)) { $null } else { $reader.GetValue($i) }
                if ($value -is [DateTime] -or $value -is [DateTimeOffset]) { $value = $value.ToString('o') }
                elseif ($value -is [byte[]]) { $value = [Convert]::ToBase64String($value) }
                $row[$columns[$i]] = $value
            }
            $rows.Add([pscustomobject]$row)
        }
        $sets.Add([pscustomobject]@{ columns = $columns; rows = $rows.ToArray(); rowCount = $rows.Count })
    } while ($reader.NextResult())
    $result.resultSets = $sets.ToArray()
    $result.recordsAffected = $reader.RecordsAffected
    $result.ok = $true
}
catch { $result.error = $_.Exception.Message }
finally {
    if ($reader) { $reader.Dispose() }
    if ($command) { $command.Dispose() }
    if ($connection) { $connection.Dispose() }
}
$result.elapsedSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
$json = ConvertTo-Json -InputObject $result -Depth 20
if ($OutputFile) { [IO.File]::WriteAllText([IO.Path]::GetFullPath($OutputFile), $json, (New-Object Text.UTF8Encoding($false))) }
else { Write-Output $json }
if (!$result.ok) { exit 1 }
exit 0
