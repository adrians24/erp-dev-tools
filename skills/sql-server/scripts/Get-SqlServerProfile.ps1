[CmdletBinding()]
param(
    [ValidateSet('local', 'internal')]
    [string]$Environment = 'local',

    [string]$Database,

    [string]$CompanyId,

    [switch]$AsJson
)

$profileModule = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\scripts\ErpDevTools.Profile.ps1'))
. $profileModule
$machineProfile = Get-ErpDevToolsProfile -Name $Environment
$environmentPrefix = $Environment.ToUpperInvariant()
$serverOverride = [Environment]::GetEnvironmentVariable("VISMA_SQL_${environmentPrefix}_SERVER", 'Process')
$databaseOverride = [Environment]::GetEnvironmentVariable("VISMA_SQL_${environmentPrefix}_DATABASE", 'Process')
$configuredServer = if (![string]::IsNullOrWhiteSpace($serverOverride)) { $serverOverride } else { Get-ErpDevToolsProfileValue -Profile $machineProfile -Name sqlServer -Required -ProfileName $Environment }
$configuredDatabase = if (![string]::IsNullOrWhiteSpace($databaseOverride)) { $databaseOverride } else { Get-ErpDevToolsProfileValue -Profile $machineProfile -Name database -Required -ProfileName $Environment }
$configuredCompanyId = Get-ErpDevToolsProfileValue -Profile $machineProfile -Name companyId

switch ($Environment) {
    'local' {
        $profile = [pscustomobject]@{
            Environment      = 'local'
            Server           = $configuredServer
            DefaultDatabase  = $configuredDatabase
            Database         = if ($Database) { $Database } else { $configuredDatabase }
            Authentication   = 'Integrated'
            User             = [Security.Principal.WindowsIdentity]::GetCurrent().Name
            CredentialSource = 'windows-integrated'
            CredentialTarget = $null
            CompanyId        = if ($PSBoundParameters.ContainsKey('CompanyId')) { $CompanyId } else { $configuredCompanyId }
        }
    }
    'internal' {
        $credentialScript = Join-Path $PSScriptRoot 'Get-SqlServerCredential.ps1'
        $credential = & $credentialScript -Environment internal
        $profile = [pscustomobject]@{
            Environment      = 'internal'
            Server           = $configuredServer
            DefaultDatabase  = $configuredDatabase
            Database         = if ($Database) { $Database } else { $configuredDatabase }
            Authentication   = 'SqlPassword'
            User             = $credential.UserName
            CredentialSource = $credential.Source
            CredentialTarget = $credential.Target
            CompanyId        = if ($PSBoundParameters.ContainsKey('CompanyId')) { $CompanyId } else { $configuredCompanyId }
        }
    }
}

if ($AsJson) {
    $profile | ConvertTo-Json -Depth 3
    exit 0
}

$profile
