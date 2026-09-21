[CmdletBinding()]
param(
    [ValidateSet('local', 'internal')]
    [string]$Environment = 'local'
)

$credentialManagerScript = Join-Path $PSScriptRoot 'CredentialManager.ps1'
. $credentialManagerScript

$configuration = switch ($Environment) {
    'local' {
        [pscustomobject]@{
            Target              = 'Codex.SqlServer.local'
            UserVariable        = 'VISMA_SQL_LOCAL_USER'
            PasswordVariable    = 'VISMA_SQL_LOCAL_PASSWORD'
        }
    }
    'internal' {
        [pscustomobject]@{
            Target              = 'Codex.SqlServer.internal'
            UserVariable        = 'VISMA_SQL_INTERNAL_USER'
            PasswordVariable    = 'VISMA_SQL_INTERNAL_PASSWORD'
        }
    }
}

$environmentUser = [Environment]::GetEnvironmentVariable($configuration.UserVariable)
$environmentPassword = [Environment]::GetEnvironmentVariable($configuration.PasswordVariable)
if ($environmentUser -or $environmentPassword) {
    if ([string]::IsNullOrWhiteSpace($environmentUser) -or [string]::IsNullOrWhiteSpace($environmentPassword)) {
        throw "Incomplete SQL environment override. Set both $($configuration.UserVariable) and $($configuration.PasswordVariable), or remove both to use Windows Credential Manager."
    }

    $securePassword = ConvertTo-SecureString $environmentPassword -AsPlainText -Force
    $credential = New-Object Management.Automation.PSCredential($environmentUser, $securePassword)
    return [pscustomobject]@{
        Environment = $Environment
        Target      = $configuration.Target
        Source      = 'environment'
        UserName    = $credential.UserName
        Password    = $credential.Password
    }
}

$storedCredential = Get-CodexStoredCredential -Target $configuration.Target
if ($null -eq $storedCredential) {
    throw "SQL credential '$($configuration.Target)' was not found in Windows Credential Manager. Run Set-SqlServerCredential.ps1 -Environment $Environment interactively."
}

[pscustomobject]@{
    Environment = $Environment
    Target      = $configuration.Target
    Source      = 'windows-credential-manager'
    UserName    = $storedCredential.UserName
    Password    = $storedCredential.Password
}
