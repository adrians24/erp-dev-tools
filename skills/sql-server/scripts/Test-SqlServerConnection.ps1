[CmdletBinding()]
param(
    [ValidateSet('local', 'internal')]
    [string]$Environment = 'local',

    [string]$Database,

    [switch]$ListDatabases
)

$invokeScript = Join-Path $PSScriptRoot 'Invoke-SqlServerQuery.ps1'

if ($ListDatabases) {
    & $invokeScript -Environment $Environment -Database $Database -ListDatabases -HideHeaders
    exit $LASTEXITCODE
}

$query = 'SELECT @@SERVERNAME AS ServerName, DB_NAME() AS DatabaseName, SYSTEM_USER AS LoginName'
& $invokeScript -Environment $Environment -Database $Database -Query $query
exit $LASTEXITCODE
