# Forward CLI options verbatim; use the same environment as the sibling API runner.
$ErrorActionPreference = 'Stop'
$requirements = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\requirements.lock'))
if (!(Test-Path -LiteralPath $requirements)) { throw 'Plugin requirements.lock is missing. Install the complete erp-dev-tools package.' }
& uv run --no-project --with-requirements $requirements python (Join-Path $PSScriptRoot 'sql_capture.py') @args
exit $LASTEXITCODE
