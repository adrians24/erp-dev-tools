# Internal tenant queries

For internal tenant tables, use the selected profile's `CompanyId` unless another company was requested. `Get-SqlServerProfile.ps1 -CompanyId` only changes profile metadata; query execution does not inject predicates. Apply the appropriate company constraint to tenant-scoped joins as well.

If a table's scope is unclear, inspect its columns:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$sqlServerSkill\scripts\Invoke-SqlServerQuery.ps1" -Environment internal -Query "SELECT TABLE_SCHEMA, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'SOOrder' ORDER BY ORDINAL_POSITION"
```

Metadata queries themselves do not require tenant predicates.

When bound parameters are needed, use `SqlCommand` with the protected credential helper. Initialize `$sqlServerSkill` from [SKILL.md](../SKILL.md); run direct helper invocations in a PowerShell process that permits the unsigned scripts, for example a child started with `-ExecutionPolicy Bypass`.

```powershell
$profile = & "$sqlServerSkill\scripts\Get-SqlServerProfile.ps1" -Environment internal
$resolvedCredential = & "$sqlServerSkill\scripts\Get-SqlServerCredential.ps1" -Environment internal
$sqlCredential = New-Object System.Data.SqlClient.SqlCredential($resolvedCredential.UserName, $resolvedCredential.Password)
$connection = New-Object System.Data.SqlClient.SqlConnection("Server=$($profile.Server);Database=$($profile.Database);TrustServerCertificate=True", $sqlCredential)
$command = $connection.CreateCommand()
$command.CommandText = 'SELECT TOP 10 OrderNbr, Status FROM SOOrder WHERE CompanyId = @CompanyId ORDER BY CreatedDateTime DESC'
$null = $command.Parameters.Add('@CompanyId', [System.Data.SqlDbType]::Int)
$command.Parameters['@CompanyId'].Value = $profile.CompanyId
$adapter = New-Object System.Data.SqlClient.SqlDataAdapter($command)
try {
    $connection.Open()
    $dataset = New-Object System.Data.DataSet
    $null = $adapter.Fill($dataset)
    $dataset.Tables[0] | Format-Table -AutoSize
}
finally {
    $adapter.Dispose()
    $command.Dispose()
    $connection.Dispose()
}
```

Adapt the database, company and SQL to the request; the sample reads the default internal database.
