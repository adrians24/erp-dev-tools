---
name: run-api-requests
description: Call Visma legacy ERP and Sales Order Service APIs on localhost or internal environments using the bundled runner.
---

# Run API Requests

Use [scripts/Invoke-RunApi.ps1](scripts/Invoke-RunApi.ps1) for authenticated requests; it forwards CLI options and preserves the process exit code. The underlying [Python runner](scripts/run_api_requests.py) remains available to existing callers. Resolve `$apiSkillRoot` to the directory containing this `SKILL.md` from the skill catalog, then initialize the launcher in the process running the commands:

```powershell
$runApi = Join-Path $apiSkillRoot 'scripts\Invoke-RunApi.ps1'
```

The launcher uses the plugin's pinned `requirements.lock`. Keep the complete plugin layout so sibling helpers and dependencies remain available.

For local Sales Order requests, first run `scripts/Ensure-SalesOrderService.ps1`. It checks `/health`, starts the configured local checkout when the service is down, waits for readiness, and coordinates startup with the shared environment mutex. Do not stop at a connection-refused result for a required local service: start it through its owning project workflow, wait for health, and retry the original read-only check. Never start remote environments or replace an occupied unhealthy port.

## Target and scope

- Use `erp` for `/v1/...`; use `salesorder` for `/api/v3/...` and its `/health` endpoint.
- Default to the `local` machine profile. Use `--environment internal` when the request targets internal. Hosts, databases, tenant/company identifiers, and client ID come from the selected machine profile; preserve explicit choices with command options.
- `--database` does not switch the backing database. Internal resolution checks the returned company database; local configuration must already serve the intended database. Sales Order `--environment internal` also leaves the request host unchanged: set the intended `--server-url`. See [configuration](references/configuration.md) when choosing non-default targets or resolving authentication.
- Execute writes and actions within the user's authorized target and scope. Use `--body-file` for complex payloads. After an ambiguous write failure, inspect resulting state before retrying to avoid duplicates; stop if the outcome cannot be resolved safely.
- Keep secrets in the configured credential store or process environment, never in chat or literal command arguments.

## Commands and results

```powershell
& $runApi erp get shipment 000014
& $runApi salesorder health
```

Use `context`, `health`, or `token` when the corresponding configuration, connectivity, or authentication is uncertain. They are not prerequisites for every request.

The runner emits one JSON object. Use `ok`, `status_code`, `data`, `error`, and `resolved` to report the actual outcome, target, and relevant identifiers. For creates, use the returned `Location` or resolved identifier because server numbering may differ from the payload.

Read the relevant entry in [command references](references/commands.md) for entity-specific commands and body examples. Surface options precede the command, for example `salesorder --environment internal --server-url <url> request GET <path>`.

For several known requests, use `& $runApi batch --file <manifest.json>`. A batch runs commands sequentially in one process, reusing HTTP connections and unexpired tokens with the same authentication context. It validates command syntax and reads body files before executing, stops at the first failure, and never retries a request. Tokens stay in memory and are cleared when the batch ends. See [batch requests](references/batch.md) for the manifest and result shape. Use separate calls when a later request depends on inspecting an earlier response.
