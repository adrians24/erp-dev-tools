# SQL commands

Initialize `$sqlServerSkill` as shown in [SKILL.md](../SKILL.md). Commands invoke a child PowerShell process with `-ExecutionPolicy Bypass` for the unsigned local helpers; no persistent policy change is needed.

## Connection profile or diagnosis

Read the profile when the target or credential source is uncertain:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$sqlServerSkill\scripts\Get-SqlServerProfile.ps1" -Environment internal -Database <database> -AsJson
```

This resolves configuration, not connectivity. To check the selected connection:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$sqlServerSkill\scripts\Test-SqlServerConnection.ps1" -Environment local
```

Both helpers accept `-Environment local|internal` and `-Database`.

## Database listing

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$sqlServerSkill\scripts\Test-SqlServerConnection.ps1" -Environment internal -ListDatabases
```

The listing excludes system databases (`database_id <= 4`).

## Query or SQL file

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$sqlServerSkill\scripts\Invoke-SqlServerQuery.ps1" -Environment internal -Database <database> -Query "SELECT TOP 10 OrderNbr, Status FROM SOOrder WHERE CompanyId = <company-id> ORDER BY CreatedDateTime DESC"
powershell -NoProfile -ExecutionPolicy Bypass -File "$sqlServerSkill\scripts\Invoke-SqlServerQuery.ps1" -Environment local -Database DWConfiguration -InputFile .\query.sql
```

`Invoke-SqlServerQuery.ps1` accepts either `-Query` or `-InputFile`, plus `-OutputFile` and `-HideHeaders`. It also supports `-ListDatabases`. Database selection does not imply company filtering: include the tenant predicate in the SQL itself.

Text mode uses `sqlcmd -b` so SQL errors fail the process, and `-y 0` so variable-length values are not truncated. This emits headerless values; `-HideHeaders` remains accepted for existing callers. Trailing spaces are preserved. The connection timeout is 15 seconds; `-TimeoutSeconds` controls the query timeout (default 120).

For structured results, add `-AsJson`. The JSON envelope contains `ok`, `environment`, `server`, `database`, `resultSets` (each with `columns`, `rows`, and `rowCount`), `recordsAffected`, `elapsedSeconds`, and `error`. SQL null becomes JSON null; dates use ISO 8601; binary values use Base64. Duplicate or unnamed columns receive unique names. `-OutputFile` writes UTF-8 JSON instead of console output. Treat artifacts as private when they contain tenant data.

JSON mode uses ADO.NET and accepts T-SQL batches, including multiple SELECTs, but rejects `GO` and SQLCMD directives/variables before execution. Use text mode for those files. It does not automatically add a transaction or roll back writes; after a failure, inspect state before retrying. For writes, verify the intended state or affected rows before reporting completion.

The non-mutating regression probe is `scripts/Test-SqlServerQuery.ps1`; it exercises errors, full values, nulls, and multiple result sets against the default local database.
