[CmdletBinding()]
param(
    [ValidateSet('local', 'internal')]
    [string]$Environment = 'internal',

    [Management.Automation.PSCredential]$Credential
)

$credentialManagerScript = Join-Path $PSScriptRoot 'CredentialManager.ps1'
. $credentialManagerScript

$target = switch ($Environment) {
    'local' { 'Codex.SqlServer.local' }
    'internal' { 'Codex.SqlServer.internal' }
}

if ($null -eq $Credential) {
    $Credential = Get-Credential -Message "Enter the rotated SQL credential for $Environment. It will be stored as '$target' in Windows Credential Manager."
}
if ($null -eq $Credential) {
    throw 'Credential entry was cancelled.'
}

Set-CodexStoredCredential -Target $target -Credential $Credential

[pscustomobject]@{
    Environment = $Environment
    Target      = $target
    UserName    = $Credential.UserName
    Stored      = $true
}
