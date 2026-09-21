# ERP Development Tools

Codex plugin for four shared Visma ERP development workflows:

- ERP UI navigation, inspection, and screenshots
- authenticated legacy ERP and Sales Order API requests
- SQL Server queries using protected credentials
- filtered SQL capture and persisted-data inspection

The plugin version is recorded in [.codex-plugin/plugin.json](.codex-plugin/plugin.json). Machine-specific endpoints and identifiers stay in a local profile, while passwords, tokens, and signatures remain in Windows Credential Manager or process environment variables.

## Install

Clone the repository into a stable development path:

```powershell
git clone https://github.com/adrians24/erp-dev-tools.git .\erp-dev-tools
```

Register that checkout as the `erp-dev-tools` source in a personal or team Codex marketplace, then install it with:

```powershell
codex plugin add erp-dev-tools@<marketplace-name>
```

Start a new Codex task after installation so the four plugin skills are discovered.

## Check a developer machine

Use Windows, PowerShell 7 (`pwsh`), Git, Python 3.11+, `uv`, `sqlcmd`, a SQL Server ODBC driver, and `playwright-cli` with its browser installed. The package retains Windows Credential Manager integration and is not a cross-platform port.

From the package root:

```powershell
pwsh -NoProfile -File .\scripts\Test-Setup.ps1
pwsh -NoProfile -File .\scripts\Test-Package.ps1
```

Setup checks tools, Python imports and the ODBC driver without connecting to ERP, SQL Server, or identity services. The first invocation may download pinned Python dependencies into uv's cache. Tests use fake authentication, loopback HTTP, temporary directories, and a private test mutex; they do not modify ERP data or acquire the live environment mutex.

## Configure local targets

No credential store or browser session was copied into this repository. Create the machine-local, non-secret profile and then replace every placeholder:

```powershell
pwsh -NoProfile -File .\scripts\Initialize-ErpDevTools.ps1
```

The default path is `%LOCALAPPDATA%\Visma\Codex\erp-dev-tools\profiles.json`. Set `ERP_DEV_TOOLS_CONFIG` only when an alternate path is needed. This file holds endpoints and identifiers; it must not contain passwords, tokens, authorization headers, or signatures. Configure authentication using the skill's documented credential targets or process environment. Never put secrets in command arguments or committed files.

- [API configuration](skills/run-api-requests/references/configuration.md): ERP authorization/signature and Sales Order client configuration.
- [SQL credentials](skills/sql-server/references/credentials.md): Windows integrated local access and protected internal credentials.
- [ERP UI](skills/erp-ui/SKILL.md): pass `-BaseUrl`, `-Company`, and `-Branch` for the intended instance. Internal login uses the developer's authorized account.
- [SQL capture](skills/sql-server-capture/SKILL.md): ODBC access and Extended Events permissions are needed for live captures.

Resolution order is explicit command argument, process environment, then the machine profile. SQL endpoint overrides are `VISMA_SQL_LOCAL_SERVER` / `VISMA_SQL_LOCAL_DATABASE` and `VISMA_SQL_INTERNAL_SERVER` / `VISMA_SQL_INTERNAL_DATABASE`. ERP UI overrides are `VISMA_ERP_UI_BASE_URL`, `VISMA_ERP_COMPANY`, and `VISMA_ERP_UI_USER`. Internal access has no committed endpoint or tenant fallback.

Invoke scripts using their actual package path, for example from the package root:

```powershell
& .\skills\erp-ui\scripts\Open-ErpScreen.ps1 -Screen shipment -BuildUrlOnly
& .\skills\run-api-requests\scripts\Invoke-RunApi.ps1 --help
& .\skills\sql-server-capture\scripts\Invoke-SqlCapture.ps1 --help
```

The API and capture launchers resolve `requirements.lock` relative to their own files, so the full package can be relocated. Install the complete plugin, not individual skill folders. The existing SQL query regression can be run explicitly against a configured local database with `skills/sql-server/scripts/Test-SqlServerQuery.ps1`; it performs SELECTs and intentional errors only and is excluded from the offline suite.

Configure `salesOrderRepository` in the local profile so agents can start a stopped local Sales Order Service. The API skill checks health, starts the service under the shared environment mutex, waits for readiness, and retries instead of treating an initial connection refusal as the final result.

## Concurrent worktrees

ERP sessions are named from the active worktree. Keep deployment, restart and shared writes inside `Invoke-ErpEnvironmentExclusive.ps1` for the whole operation. Configure `environmentMutexName` to the same value used by cooperating project runners. Do not nest the wrapper around a runner that already holds that mutex. This lock coordinates cooperating processes on the same Windows session; it is not a cross-computer database lock. Independent targets can intentionally share one conservative lock name.

## Distribution and updates

The source repository is `https://github.com/adrians24/erp-dev-tools`. Marketplace configuration, machine profiles, credentials, local services, and browser sessions remain outside the repository and installed plugin cache.

After installing and verifying the plugin, remove duplicate standalone copies of these skills. Start a new Codex task after every reinstall so Codex discovers the updated plugin version.

Consuming projects should record the tested plugin version and source commit. Keep one compatible shared installation per developer; conflicting project requirements need an explicit version decision. Do not silently upgrade shared tools in the middle of a task.

Edit helpers in this source checkout, run tests, then deliberately bump the manifest version and distribute the reviewed release. Do not edit an installed plugin cache. To update Python dependencies, change `requirements.in`, then from this root run:

```powershell
uv pip compile requirements.in --generate-hashes --no-header --output-file requirements.lock
```

The lock pins transitive packages and hashes. Re-run package tests after dependency updates. The Python pins do not pin Windows, PowerShell, the SQL driver, browser or playwright-cli; report those versions when diagnosing environment-specific behavior.
