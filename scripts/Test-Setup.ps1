[CmdletBinding()]
param([switch] $CheckConfiguration)
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot
$checks = @()
foreach ($name in @('pwsh', 'git', 'python', 'uv', 'sqlcmd', 'playwright-cli')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    $checks += [pscustomobject]@{ name = $name; available = $null -ne $command }
}
$pythonEnvironment = $null
if (($checks | Where-Object name -eq 'uv').available) {
    $output = & uv run --no-project --with-requirements (Join-Path $packageRoot 'requirements.lock') python -c 'import json,sys,requests,pyodbc; print(json.dumps({"python":sys.version.split()[0],"supportedPython":sys.version_info >= (3,11),"requests":requests.__version__,"pyodbc":pyodbc.version,"sqlServerOdbcDriver":any("SQL Server" in d for d in pyodbc.drivers())}))'
    if ($LASTEXITCODE -ne 0) { throw 'Pinned Python dependency check failed.' }
    $pythonEnvironment = $output | ConvertFrom-Json
}
$toolsReady = @($checks | Where-Object { !$_.available }).Count -eq 0 -and $null -ne $pythonEnvironment -and $pythonEnvironment.supportedPython -and $pythonEnvironment.sqlServerOdbcDriver
$configuration = [pscustomobject]@{ checked = $false; present = $false; valid = $null; path = $null; profiles = @{} }
if ($CheckConfiguration) {
    . (Join-Path $PSScriptRoot 'ErpDevTools.Profile.ps1')
    $configuration.checked = $true
    $configuration.path = Get-ErpDevToolsConfigPath
    $configuration.present = Test-Path -LiteralPath $configuration.path -PathType Leaf
    $required = @{
        local = @('erpApiBaseUrl', 'erpUiBaseUrl', 'erpCompany', 'erpUser', 'environmentMutexName', 'companyId', 'salesOrderServerUrl', 'sqlServer', 'database')
        internal = @('tokenUrl', 'clientId', 'tenantId', 'companyId', 'erpUser', 'erpCompany', 'salesOrderServerUrl', 'sqlServer', 'database')
    }
    $valid = $configuration.present
    foreach ($profileName in @('local', 'internal')) {
        $fieldStatus = [ordered]@{}
        try { $profile = Get-ErpDevToolsProfile -Name $profileName }
        catch { $profile = [pscustomobject]@{}; $valid = $false }
        foreach ($field in $required[$profileName]) {
            $fieldStatus[$field] = ![string]::IsNullOrWhiteSpace((Get-ErpDevToolsProfileValue -Profile $profile -Name $field))
            if (!$fieldStatus[$field]) { $valid = $false }
        }
        $configuration.profiles[$profileName] = $fieldStatus
    }
    $configuration.valid = $valid
}
$ready = $toolsReady -and (!$CheckConfiguration -or $configuration.valid)
[pscustomobject]@{ toolsReady = $toolsReady; ready = $ready; tools = $checks; pythonEnvironment = $pythonEnvironment; configuration = $configuration; liveServicesChecked = $false; credentialsChecked = $false } | ConvertTo-Json -Depth 7
if (!$ready) { exit 1 }
