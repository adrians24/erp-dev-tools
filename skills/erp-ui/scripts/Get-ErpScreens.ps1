[CmdletBinding()]
param([string] $Search)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ErpUi.Common.ps1')

$catalog = Get-ErpScreenCatalog
$screens = @($catalog.PSObject.Properties | ForEach-Object {
    [pscustomobject]@{
        alias = $_.Name
        screenId = $_.Value.screenId
        title = $_.Value.title
        keyHints = @($_.Value.keyHints)
    }
})

if (-not [string]::IsNullOrWhiteSpace($Search)) {
    $screens = @($screens | Where-Object {
        $_.alias -like "*$Search*" -or
        $_.screenId -like "*$Search*" -or
        $_.title -like "*$Search*"
    })
}

$screens | Sort-Object alias | ConvertTo-Json -Depth 4
