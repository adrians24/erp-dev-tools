---
name: sql-server
description: Query and modify local or internal Visma SQL Server databases using the bundled PowerShell helpers.
---

# SQL Server

Use the bundled helpers for connection profiles, credentials and `sqlcmd` execution. Resolve `$sqlServerSkill` to the directory containing this `SKILL.md` from the skill catalog. Use that absolute path in the PowerShell process running the commands; do not assume a personal installation directory.

## Target and scope

| Environment | Select when | Server | Default database |
| --- | --- | --- | --- |
| `local` | Unspecified, local or localhost | Machine profile | Machine profile |
| `internal` | Request targets internal or Azure ERP SQL | Machine profile | Machine profile |

An ERP mention alone does not select internal. Pass `-Database` when the user names a database.

Internal tenant-data queries require the selected profile's `CompanyId` filter unless the user specifies another company. The helpers do **not** apply this filter automatically. Metadata (`sys.*`, `INFORMATION_SCHEMA`) and database lists do not need it; see [tenant queries](references/tenant-queries.md) when table scope or parameter binding needs inspection.

Run requested reads and authorized writes through completion. Before a write, establish the target database, affected rows or objects, and intended effect; reuse authorization already present in the task. Ask only when destructive scope or intent remains unresolved. If a write's outcome is uncertain, inspect state before retrying.

## Run a query

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$sqlServerSkill\scripts\Invoke-SqlServerQuery.ps1" -Environment local -Query "SELECT TOP 5 name FROM sys.tables ORDER BY name"
```

Local authentication uses the current Windows identity. Internal authentication uses Windows Credential Manager target `Codex.SqlServer.internal`; read [credentials](references/credentials.md) only for missing credentials or automation overrides. Keep passwords out of arguments, files and chat.

Read [commands](references/commands.md) for database listing, SQL files, output options or connection diagnosis. Run a connection/profile check when needed, not before every query. Report the environment, database and applicable company filter with the result. SQL errors now return nonzero exit codes. Prefer `-AsJson` for machine-readable results: it preserves complete values, nulls, column names, and multiple result sets. Text mode remains available for SQLCMD files and emits complete headerless values. Both modes accept `-TimeoutSeconds` (default 120). A successful command still requires checking the requested business outcome.

## Machine configuration

Profiles are loaded from `%LOCALAPPDATA%\Visma\Codex\erp-dev-tools\profiles.json`, or `ERP_DEV_TOOLS_CONFIG` when explicitly set. Override endpoints with `VISMA_SQL_LOCAL_SERVER` / `VISMA_SQL_LOCAL_DATABASE` or `VISMA_SQL_INTERNAL_SERVER` / `VISMA_SQL_INTERNAL_DATABASE`. An explicit database argument wins. Keep credentials in the protected stores described above.
