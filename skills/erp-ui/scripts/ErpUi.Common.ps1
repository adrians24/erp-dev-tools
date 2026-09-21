Set-StrictMode -Version Latest

$profileModule = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\scripts\ErpDevTools.Profile.ps1'))
. $profileModule
$localMachineProfile = Get-ErpDevToolsProfile -Name local -Optional
$script:ErpEnvironmentMutexName = [Environment]::GetEnvironmentVariable('ERP_DEV_TOOLS_MUTEX_NAME', 'Process')
if ([string]::IsNullOrWhiteSpace($script:ErpEnvironmentMutexName)) {
    $script:ErpEnvironmentMutexName = Get-ErpDevToolsProfileValue -Profile $localMachineProfile -Name environmentMutexName
}

function Assert-PlaywrightCli {
    if (-not (Get-Command playwright-cli -ErrorAction SilentlyContinue)) {
        throw 'playwright-cli is required. Install or expose it on PATH before using the ERP UI helpers.'
    }
}

function Get-ErpUiDefaultSessionName {
    $root = $null
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $candidate = @(& git rev-parse --show-toplevel 2>$null)
        if ($LASTEXITCODE -eq 0 -and $candidate.Count -gt 0) {
            $root = $candidate[0]
        }
    }

    if ([string]::IsNullOrWhiteSpace($root)) {
        $root = (Get-Location).Path
    }

    $normalized = [System.IO.Path]::GetFullPath($root).TrimEnd('\', '/').ToLowerInvariant()
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($normalized))
    }
    finally {
        $sha.Dispose()
    }

    $suffix = -join @($bytes[0..5] | ForEach-Object { $_.ToString('x2') })
    return "erp-$suffix"
}

function Resolve-ErpUiSessionName {
    param([string] $Session)

    if ([string]::IsNullOrWhiteSpace($Session)) {
        return Get-ErpUiDefaultSessionName
    }

    if ($Session -notmatch '^[A-Za-z0-9._-]+$') {
        throw "Invalid Playwright session '$Session'. Use letters, digits, dot, underscore, or hyphen."
    }

    return $Session
}

function Get-ErpScreenCatalog {
    $catalogPath = Join-Path $PSScriptRoot '..\references\screens.json'
    return Get-Content -LiteralPath $catalogPath -Raw | ConvertFrom-Json
}

function Resolve-ErpScreenDefinition {
    param(
        [string] $Screen,
        [string] $ScreenId
    )

    if (-not [string]::IsNullOrWhiteSpace($ScreenId)) {
        if ($ScreenId -notmatch '^[A-Z]{2}[0-9]{6}$') {
            throw "Invalid ERP screen ID '$ScreenId'. Expected a value such as SO301000."
        }

        return [pscustomobject]@{
            Alias = $null
            ScreenId = $ScreenId
            Title = $null
            KeyHints = @()
        }
    }

    $catalog = Get-ErpScreenCatalog
    $property = $catalog.PSObject.Properties | Where-Object { $_.Name -ieq $Screen } | Select-Object -First 1
    if ($null -eq $property) {
        $available = @($catalog.PSObject.Properties.Name | Sort-Object) -join ', '
        throw "Unknown ERP screen alias '$Screen'. Available aliases: $available. Use -ScreenId for an uncatalogued screen."
    }

    return [pscustomobject]@{
        Alias = $property.Name
        ScreenId = $property.Value.screenId
        Title = $property.Value.title
        KeyHints = @($property.Value.keyHints)
    }
}

function ConvertTo-ErpQueryString {
    param([System.Collections.IDictionary] $Values)

    $pairs = foreach ($key in $Values.Keys) {
        $value = $Values[$key]
        if ($null -eq $value) {
            continue
        }

        '{0}={1}' -f [System.Uri]::EscapeDataString([string]$key), [System.Uri]::EscapeDataString([string]$value)
    }

    return $pairs -join '&'
}

function New-ErpScreenUrl {
    param(
        [Parameter(Mandatory)][string] $BaseUrl,
        [Parameter(Mandatory)][string] $Company,
        [Parameter(Mandatory)][string] $ScreenId,
        [System.Collections.IDictionary] $Keys
    )

    $baseUri = $null
    if (-not [System.Uri]::TryCreate($BaseUrl, [System.UriKind]::Absolute, [ref]$baseUri)) {
        throw "ERP base URL '$BaseUrl' is not an absolute URL."
    }

    if ($baseUri.Scheme -notin @('http', 'https')) {
        throw "ERP base URL '$BaseUrl' must use HTTP or HTTPS."
    }

    $builder = [System.UriBuilder]::new($baseUri)
    $builder.Path = $builder.Path.TrimEnd('/') + '/Main'

    $ordered = [ordered]@{
        CompanyID = $Company
        ScreenId = $ScreenId
    }
    if ($null -ne $Keys) {
        foreach ($key in @($Keys.Keys | Sort-Object)) {
            if ($key -in @('CompanyID', 'ScreenId')) {
                throw "Record key '$key' is reserved by the ERP navigation helper."
            }
            $ordered[$key] = $Keys[$key]
        }
    }

    $builder.Query = ConvertTo-ErpQueryString -Values $ordered
    return $builder.Uri.AbsoluteUri
}

function Get-ErpLoginUrl {
    param(
        [Parameter(Mandatory)][string] $BaseUrl,
        [Parameter(Mandatory)][string] $TargetUrl
    )

    $root = $BaseUrl.TrimEnd('/')
    $target = [System.Uri]::new($TargetUrl)
    return "$root/Frames/Login.aspx?ReturnUrl=$([System.Uri]::EscapeDataString($target.PathAndQuery))"
}

function ConvertFrom-ErpPlaywrightJson {
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][string[]] $Output,
        [Parameter(Mandatory)][string] $Context
    )

    $text = $Output -join [Environment]::NewLine
    try {
        return $text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        # playwright-cli can emit a one-time informational banner before its JSON.
    }

    $lines = @($text -split '\r?\n')
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $trimmed = $lines[$index].TrimStart()
        if (!$trimmed.StartsWith('{') -and !$trimmed.StartsWith('[')) { continue }

        $candidate = $lines[$index..($lines.Count - 1)] -join [Environment]::NewLine
        try {
            return $candidate | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            continue
        }
    }

    throw "$Context returned invalid JSON: $text"
}

function Test-ErpUiSession {
    param([Parameter(Mandatory)][string] $Session)

    Assert-PlaywrightCli
    $output = @(& playwright-cli list --json 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not enumerate Playwright sessions: $($output -join [Environment]::NewLine)"
    }

    $data = ConvertFrom-ErpPlaywrightJson -Output $output -Context 'playwright-cli list'
    return @($data.browsers | Where-Object { $_.name -eq $Session -and $_.status -eq 'open' }).Count -gt 0
}

function Invoke-ErpPlaywright {
    param(
        [Parameter(Mandatory)][string] $Session,
        [Parameter(Mandatory)][string[]] $Arguments
    )

    Assert-PlaywrightCli
    $output = @(& playwright-cli "-s=$Session" @Arguments --json 2>&1)
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    if ($exitCode -ne 0) {
        throw "playwright-cli failed for session '$Session': $text"
    }

    $response = ConvertFrom-ErpPlaywrightJson -Output $output -Context "playwright-cli for session '$Session'"

    if ($response.PSObject.Properties.Name -contains 'error' -and $null -ne $response.error) {
        $message = if ($response.error -is [string]) { $response.error } else { $response.error | ConvertTo-Json -Compress -Depth 8 }
        throw "playwright-cli reported an error for session '$Session': $message"
    }

    return $response
}

function ConvertFrom-PlaywrightCodeResult {
    param([Parameter(Mandatory)] $Response)

    if ($Response.PSObject.Properties.Name -notcontains 'result') {
        throw "playwright-cli returned no result: $($Response | ConvertTo-Json -Compress -Depth 8)"
    }

    $value = $Response.result
    for ($attempt = 0; $attempt -lt 3 -and $value -is [string]; $attempt++) {
        try {
            $value = $value | ConvertFrom-Json
        }
        catch {
            break
        }
    }

    return $value
}

function Enter-ErpEnvironmentLock {
    param([ValidateRange(1, 7200)][int] $TimeoutSeconds = 3600)

    if ([string]::IsNullOrWhiteSpace($script:ErpEnvironmentMutexName)) {
        throw "ERP development profile 'local' is missing 'environmentMutexName'. Update '$(Get-ErpDevToolsConfigPath)'."
    }
    $mutex = [System.Threading.Mutex]::new($false, $script:ErpEnvironmentMutexName)
    $acquired = $false
    try {
        try {
            $acquired = $mutex.WaitOne([TimeSpan]::FromSeconds($TimeoutSeconds))
        }
        catch [System.Threading.AbandonedMutexException] {
            $acquired = $true
        }

        if (-not $acquired) {
            throw "Timed out after $TimeoutSeconds seconds waiting for the shared local ERP environment."
        }

        return [pscustomobject]@{
            Mutex = $mutex
            Acquired = $true
            Name = $script:ErpEnvironmentMutexName
        }
    }
    catch {
        if (-not $acquired) {
            $mutex.Dispose()
        }
        throw
    }
}

function Exit-ErpEnvironmentLock {
    param([Parameter(Mandatory)] $Lease)

    if ($Lease.Acquired) {
        $Lease.Mutex.ReleaseMutex()
        $Lease.Acquired = $false
    }
    $Lease.Mutex.Dispose()
}
