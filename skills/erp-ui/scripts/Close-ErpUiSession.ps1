[CmdletBinding()]
param([string] $Session)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ErpUi.Common.ps1')

$resolvedSession = Resolve-ErpUiSessionName -Session $Session
$wasOpen = Test-ErpUiSession -Session $resolvedSession
if ($wasOpen) {
    $null = Invoke-ErpPlaywright -Session $resolvedSession -Arguments @('close')
}

[pscustomobject]@{
    session = $resolvedSession
    wasOpen = $wasOpen
    closed = $true
} | ConvertTo-Json
