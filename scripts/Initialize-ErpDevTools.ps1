[CmdletBinding(SupportsShouldProcess)]
param(
    [string] $Destination,
    [switch] $Force,
    [switch] $AsJson
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ErpDevTools.Profile.ps1')

$template = Join-Path (Split-Path -Parent $PSScriptRoot) 'config\profiles.example.json'
if (!$Destination) { $Destination = Get-ErpDevToolsConfigPath }
$Destination = [IO.Path]::GetFullPath($Destination)
if ((Test-Path -LiteralPath $Destination) -and !$Force) {
    throw "Configuration already exists at '$Destination'. Use -Force only when replacement is intended."
}

if ($PSCmdlet.ShouldProcess($Destination, 'Create ERP development profile from the safe template')) {
    $null = New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force
    Copy-Item -LiteralPath $template -Destination $Destination -Force:$Force
}

$result = [pscustomobject]@{
    path = $Destination
    created = Test-Path -LiteralPath $Destination -PathType Leaf
    containsSecrets = $false
    nextStep = 'Replace placeholder values, then run scripts\Test-Setup.ps1 -CheckConfiguration.'
}
if ($AsJson) { $result | ConvertTo-Json -Depth 3 } else { $result }
