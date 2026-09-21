Set-StrictMode -Version Latest

function Get-ErpDevToolsConfigPath {
    $override = [Environment]::GetEnvironmentVariable('ERP_DEV_TOOLS_CONFIG', 'Process')
    if (![string]::IsNullOrWhiteSpace($override)) {
        return [IO.Path]::GetFullPath($override)
    }
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw 'LOCALAPPDATA is unavailable. Set ERP_DEV_TOOLS_CONFIG to profiles.json.'
    }
    return Join-Path $env:LOCALAPPDATA 'Visma\Codex\erp-dev-tools\profiles.json'
}

function Get-ErpDevToolsProfile {
    param(
        [Parameter(Mandatory)][ValidateSet('local', 'internal')][string] $Name,
        [switch] $Optional
    )

    $path = Get-ErpDevToolsConfigPath
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) {
        if ($Optional) { return [pscustomobject]@{} }
        throw "ERP development profile was not found at '$path'. Run scripts\Initialize-ErpDevTools.ps1 from the plugin source or set ERP_DEV_TOOLS_CONFIG."
    }

    try { $configuration = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json }
    catch { throw "Unable to read ERP development profile '$path': $($_.Exception.Message)" }
    if ($configuration.version -ne 1 -or $null -eq $configuration.profiles) {
        throw "ERP development profile '$path' must have version 1 and a profiles object."
    }
    $property = $configuration.profiles.PSObject.Properties | Where-Object Name -eq $Name | Select-Object -First 1
    if ($null -eq $property -or $null -eq $property.Value) {
        if ($Optional) { return [pscustomobject]@{} }
        throw "ERP development profile '$Name' is missing in '$path'."
    }
    return $property.Value
}

function Get-ErpDevToolsProfileValue {
    param(
        [Parameter(Mandatory)] $Profile,
        [Parameter(Mandatory)][string] $Name,
        [switch] $Required,
        [string] $ProfileName
    )

    $property = $Profile.PSObject.Properties | Where-Object Name -eq $Name | Select-Object -First 1
    $value = if ($null -eq $property -or $null -eq $property.Value) { '' } else { ([string]$property.Value).Trim() }
    if ($value.StartsWith('<') -and $value.EndsWith('>')) { $value = '' }
    if ($Required -and [string]::IsNullOrWhiteSpace($value)) {
        throw "ERP development profile '$ProfileName' is missing '$Name'. Update '$(Get-ErpDevToolsConfigPath)'."
    }
    return $value
}
