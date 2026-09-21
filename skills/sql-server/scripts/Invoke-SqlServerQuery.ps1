[CmdletBinding(DefaultParameterSetName = 'Query')]
param(
    [ValidateSet('local', 'internal')]
    [string]$Environment = 'local',

    [string]$Database,

    [Parameter(ParameterSetName = 'Query')]
    [string]$Query,

    [Parameter(Mandatory = $true, ParameterSetName = 'File')]
    [string]$InputFile,

    [string]$OutputFile,

    [switch]$HideHeaders,

    [switch]$ListDatabases,

    [switch]$AsJson,

    [ValidateRange(1, 7200)]
    [int]$TimeoutSeconds = 120
)

$profileScript = Join-Path $PSScriptRoot 'Get-SqlServerProfile.ps1'
$profile = & $profileScript -Environment $Environment -Database $Database

if (-not $ListDatabases -and -not $Query -and -not $InputFile) {
    throw 'Provide -Query, -InputFile, or -ListDatabases.'
}

if ($AsJson) {
    $jsonArguments = @{ Profile = $profile; TimeoutSeconds = $TimeoutSeconds }
    if ($ListDatabases) { $jsonArguments.Query = 'SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name' }
    elseif ($InputFile) { $jsonArguments.Query = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $InputFile).Path) }
    else { $jsonArguments.Query = $Query }
    if ($OutputFile) { $jsonArguments.OutputFile = $OutputFile }
    & (Join-Path $PSScriptRoot 'Invoke-SqlServerJson.ps1') @jsonArguments
    exit $LASTEXITCODE
}

$args = @(
    '-S', $profile.Server,
    '-C',
    '-b', '-r', '1', '-y', '0', '-w', '65535',
    '-l', '15', '-t', "$TimeoutSeconds"
)

if ($profile.Authentication -eq 'Integrated') {
    $args += '-E'
}
else {
    $args += @('-U', $profile.User)
}

if (-not $ListDatabases) {
    $args += @('-d', $profile.Database)
}

# sqlcmd -y 0 emits untruncated, headerless values and rejects -h. Keep
# -HideHeaders accepted for compatibility; use -AsJson for column metadata.

if ($ListDatabases) {
    $args += @('-Q', 'SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name')
}
elseif ($PSCmdlet.ParameterSetName -eq 'Query') {
    $args += @('-Q', $Query)
}
else {
    $args += @('-i', $InputFile)
}

if ($OutputFile) {
    $args += @('-o', $OutputFile)
}

if ($profile.Authentication -eq 'Integrated') {
    & sqlcmd @args
    $exitCode = $LASTEXITCODE
}
else {
    $credentialScript = Join-Path $PSScriptRoot 'Get-SqlServerCredential.ps1'
    $credential = & $credentialScript -Environment $Environment
    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($credential.Password)
    $previousSqlCmdPassword = $env:SQLCMDPASSWORD
    try {
        $env:SQLCMDPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
        & sqlcmd @args
        $exitCode = $LASTEXITCODE
    }
    finally {
        if ($null -eq $previousSqlCmdPassword) {
            Remove-Item Env:SQLCMDPASSWORD -ErrorAction SilentlyContinue
        }
        else {
            $env:SQLCMDPASSWORD = $previousSqlCmdPassword
        }
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
}

if ($exitCode -ne 0) {
    exit $exitCode
}
