# Forward CLI options verbatim; resolve dependencies relative to this plugin.
$ErrorActionPreference = 'Stop'
$requirements = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\requirements.lock'))
if (!(Test-Path -LiteralPath $requirements)) { throw 'Plugin requirements.lock is missing. Install the complete erp-dev-tools package.' }
& uv run --no-project --with-requirements $requirements python (Join-Path $PSScriptRoot 'run_api_requests.py') @args
exit $LASTEXITCODE
