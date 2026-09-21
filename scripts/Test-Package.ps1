[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot
$requirements = Join-Path $packageRoot 'requirements.lock'
$previousBytecode = $env:PYTHONDONTWRITEBYTECODE
$previousConfiguration = $env:ERP_DEV_TOOLS_CONFIG
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:ERP_DEV_TOOLS_CONFIG = Join-Path $packageRoot 'tests\profiles.test.json'
    foreach ($file in Get-ChildItem -LiteralPath $packageRoot -Filter *.ps1 -File -Recurse) {
        $tokens = $null; $parseErrors = $null
        $null = [Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors)
        if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
    }
    & uv run --no-project --with-requirements $requirements python -m unittest discover -s (Join-Path $packageRoot 'tests') -p 'test_*.py' -v
    if ($LASTEXITCODE -ne 0) { throw 'Package behavior tests failed.' }
    & uv run --no-project --with-requirements $requirements python (Join-Path $packageRoot 'skills\run-api-requests\scripts\test_batch.py')
    if ($LASTEXITCODE -ne 0) { throw 'API batch tests failed.' }
    & pwsh -NoProfile -File (Join-Path $packageRoot 'tests\Test-EnvironmentLock.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Environment lock tests failed.' }
    Write-Output 'Package validation passed. No live ERP or SQL operations were executed.'
}
finally {
    $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
    $env:ERP_DEV_TOOLS_CONFIG = $previousConfiguration
}
