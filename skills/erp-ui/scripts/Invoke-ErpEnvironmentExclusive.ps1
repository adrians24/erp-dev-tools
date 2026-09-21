[CmdletBinding(DefaultParameterSetName = 'Script')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Script')]
    [string] $ScriptPath,

    [Parameter(ParameterSetName = 'Script')]
    [string[]] $ArgumentList = @(),

    [Parameter(Mandatory, ParameterSetName = 'Block')]
    [scriptblock] $ScriptBlock,

    [ValidateRange(1, 7200)]
    [int] $LockTimeoutSeconds = 3600
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ErpUi.Common.ps1')

if ($PSCmdlet.ParameterSetName -eq 'Script') {
    $resolvedScript = (Resolve-Path -LiteralPath $ScriptPath).Path
    if ([System.IO.Path]::GetExtension($resolvedScript) -ine '.ps1') {
        throw "Exclusive ERP tasks must be PowerShell scripts: $resolvedScript"
    }
}

Write-Verbose "Waiting for shared environment mutex '$script:ErpEnvironmentMutexName'."
$lease = Enter-ErpEnvironmentLock -TimeoutSeconds $LockTimeoutSeconds
try {
    Write-Verbose "Acquired shared environment mutex '$($lease.Name)'."
    if ($PSCmdlet.ParameterSetName -eq 'Script') {
        & $resolvedScript @ArgumentList
    }
    else {
        & $ScriptBlock
    }
}
finally {
    Exit-ErpEnvironmentLock -Lease $lease
    Write-Verbose "Released shared environment mutex '$script:ErpEnvironmentMutexName'."
}
