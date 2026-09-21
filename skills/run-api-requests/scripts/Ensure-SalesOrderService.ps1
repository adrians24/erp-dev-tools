[CmdletBinding()]
param(
    [ValidateSet('local', 'internal')][string] $Environment = 'local',
    [string] $ServerUrl,
    [string] $SalesOrderRepository,
    [ValidateRange(5, 600)][int] $TimeoutSeconds = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$pluginRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
. (Join-Path $pluginRoot 'scripts\ErpDevTools.Profile.ps1')

function Get-SalesOrderHealthStatus {
    param([Parameter(Mandatory)][string] $Url)

    $status = & curl.exe -k -s -o NUL -w '%{http_code}' --connect-timeout 2 --max-time 5 $Url 2> $null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($status)) { return '000' }
    return ([string]$status).Trim()
}

function Test-SalesOrderPortListener {
    param([Parameter(Mandatory)][int] $Port)

    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    return $listeners.Port -contains $Port
}

function Stop-SalesOrderProcessTree {
    param([Parameter(Mandatory)][System.Diagnostics.Process] $Process)

    $Process.Refresh()
    if ($Process.HasExited) { return }
    $taskKill = Get-Command taskkill.exe -ErrorAction SilentlyContinue
    if ($null -ne $taskKill) {
        & $taskKill.Source /PID $Process.Id /T /F 2> $null | Out-Null
        if ($LASTEXITCODE -eq 0) { return }
    }
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
}

$selectedProfile = Get-ErpDevToolsProfile -Name $Environment
$localProfile = if ($Environment -eq 'local') { $selectedProfile } else { Get-ErpDevToolsProfile -Name local }

$resolvedServerUrl = $ServerUrl
if ([string]::IsNullOrWhiteSpace($resolvedServerUrl)) { $resolvedServerUrl = [Environment]::GetEnvironmentVariable('VISMA_SALESORDER_SERVER_URL', 'Process') }
if ([string]::IsNullOrWhiteSpace($resolvedServerUrl)) { $resolvedServerUrl = Get-ErpDevToolsProfileValue -Profile $selectedProfile -Name 'salesOrderServerUrl' }
if ([string]::IsNullOrWhiteSpace($resolvedServerUrl)) { $resolvedServerUrl = 'https://localhost:5001' }

try { $serverUri = [Uri]::new($resolvedServerUrl) }
catch { throw "Invalid Sales Order Service URL '$resolvedServerUrl'." }
if (!$serverUri.IsLoopback) {
    throw "Automatic Sales Order Service startup is limited to loopback URLs. '$resolvedServerUrl' must be started by its owning environment."
}

$healthUrl = $resolvedServerUrl.TrimEnd('/') + '/health'
$initialHealth = Get-SalesOrderHealthStatus -Url $healthUrl
if ($initialHealth -eq '200') {
    [pscustomobject]@{ ok = $true; status = 'already-running'; serverUrl = $resolvedServerUrl; healthUrl = $healthUrl; processId = $null } | ConvertTo-Json -Compress
    exit 0
}

$resolvedRepository = $SalesOrderRepository
if ([string]::IsNullOrWhiteSpace($resolvedRepository)) { $resolvedRepository = [Environment]::GetEnvironmentVariable('VISMA_SALESORDER_REPOSITORY', 'Process') }
if ([string]::IsNullOrWhiteSpace($resolvedRepository)) { $resolvedRepository = Get-ErpDevToolsProfileValue -Profile $selectedProfile -Name 'salesOrderRepository' }
if ([string]::IsNullOrWhiteSpace($resolvedRepository)) { $resolvedRepository = Get-ErpDevToolsProfileValue -Profile $localProfile -Name 'salesOrderRepository' -Required -ProfileName local }
$resolvedRepository = [IO.Path]::GetFullPath($resolvedRepository)

$salesOrderSource = Join-Path $resolvedRepository 'src'
$salesOrderProject = Join-Path $salesOrderSource 'services\sales-order\sales-order.api\sales-order.api.csproj'
if (!(Test-Path -LiteralPath $salesOrderProject -PathType Leaf)) {
    throw "Sales Order Service project was not found at '$salesOrderProject'. Update 'salesOrderRepository' in '$(Get-ErpDevToolsConfigPath)' or set VISMA_SALESORDER_REPOSITORY."
}

$mutexName = Get-ErpDevToolsProfileValue -Profile $localProfile -Name 'environmentMutexName' -Required -ProfileName local
$mutex = [System.Threading.Mutex]::new($false, $mutexName)
$acquired = $false
$startedProcess = $null
try {
    try { $acquired = $mutex.WaitOne([TimeSpan]::FromSeconds($TimeoutSeconds)) }
    catch [System.Threading.AbandonedMutexException] { $acquired = $true }
    if (!$acquired) { throw "Timed out after $TimeoutSeconds seconds waiting for the shared ERP environment lock '$mutexName'." }

    $health = Get-SalesOrderHealthStatus -Url $healthUrl
    if ($health -eq '200') {
        [pscustomobject]@{ ok = $true; status = 'started-by-another-agent'; serverUrl = $resolvedServerUrl; healthUrl = $healthUrl; processId = $null } | ConvertTo-Json -Compress
        exit 0
    }
    if (Test-SalesOrderPortListener -Port $serverUri.Port) {
        throw "Port $($serverUri.Port) is occupied but '$healthUrl' returned HTTP $health. Refusing to replace or kill the existing listener."
    }

    $logDirectory = Join-Path $env:LOCALAPPDATA 'Visma\Codex\erp-dev-tools\logs'
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
    $stdoutLog = Join-Path $logDirectory "sales-order-$runId.log"
    $stderrLog = Join-Path $logDirectory "sales-order-$runId.err.log"

    $previousAspNetEnvironment = [Environment]::GetEnvironmentVariable('ASPNETCORE_ENVIRONMENT', 'Process')
    $previousPriceLibrary = [Environment]::GetEnvironmentVariable('PRICE_AND_DISCOUNT_LIBRARY_ENABLED', 'Process')
    try {
        [Environment]::SetEnvironmentVariable('ASPNETCORE_ENVIRONMENT', 'Development', 'Process')
        [Environment]::SetEnvironmentVariable('PRICE_AND_DISCOUNT_LIBRARY_ENABLED', 'true', 'Process')
        $projectArgument = '"' + $salesOrderProject + '"'
        $startedProcess = Start-Process -FilePath 'dotnet' -ArgumentList @(
            'run', '--no-launch-profile', '--project', $projectArgument,
            '--', '--urls', $resolvedServerUrl
        ) -WorkingDirectory $salesOrderSource -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
    }
    finally {
        [Environment]::SetEnvironmentVariable('ASPNETCORE_ENVIRONMENT', $previousAspNetEnvironment, 'Process')
        [Environment]::SetEnvironmentVariable('PRICE_AND_DISCOUNT_LIBRARY_ENABLED', $previousPriceLibrary, 'Process')
    }

    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $startedProcess.Refresh()
        if ($startedProcess.HasExited) {
            throw "Sales Order Service exited with code $($startedProcess.ExitCode) before becoming healthy. Logs: '$stdoutLog', '$stderrLog'."
        }
        if ((Get-SalesOrderHealthStatus -Url $healthUrl) -eq '200') {
            [pscustomobject]@{
                ok = $true
                status = 'started'
                serverUrl = $resolvedServerUrl
                healthUrl = $healthUrl
                processId = $startedProcess.Id
                stdoutLog = $stdoutLog
                stderrLog = $stderrLog
            } | ConvertTo-Json -Compress
            exit 0
        }
        Start-Sleep -Milliseconds 500
    }

    throw "Sales Order Service did not become healthy within $TimeoutSeconds seconds. Logs: '$stdoutLog', '$stderrLog'."
}
catch {
    if ($null -ne $startedProcess) { Stop-SalesOrderProcessTree -Process $startedProcess }
    throw
}
finally {
    if ($acquired) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
