# SQL credentials

Local SQL uses Windows integrated authentication; no stored password is required.

For internal SQL, the helper reads Windows Credential Manager target `Codex.SqlServer.internal`. If it is missing or needs rotation, the user can run this in an interactive Windows PowerShell session after initializing `$sqlServerSkill` from [SKILL.md](../SKILL.md):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$sqlServerSkill\scripts\Set-SqlServerCredential.ps1" -Environment internal
```

The prompt stores the generic credential locally and does not print the password. Do not ask the user to paste it into chat or place it in command arguments or skill files.

For ephemeral automation, both `VISMA_SQL_INTERNAL_USER` and `VISMA_SQL_INTERNAL_PASSWORD` must be present to override Credential Manager. A partial override fails. Keep these process-scoped; do not persist the password in user- or machine-scoped environment variables.

The query helper supplies the password to `sqlcmd` through a temporary process `SQLCMDPASSWORD`, restores the previous value afterward, and zeroes the temporary native buffer. Do not replace this with `sqlcmd -P` or log environment/credential objects containing secrets.
