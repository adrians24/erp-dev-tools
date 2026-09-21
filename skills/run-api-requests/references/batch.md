# Batch requests

Pass a JSON array of command argument arrays to `Invoke-RunApi.ps1 batch --file <path>`:

```json
[
  ["salesorder", "health"],
  ["erp", "get", "shipment", "000014"]
]
```

Replace sample identifiers with the requested records. Each entry accepts the same options as a standalone `erp` or `salesorder` command. Options remain individual strings, so quoting a payload or file path is unnecessary inside the array. Body-file paths resolve relative to the manifest; all body files are read before the first request. Nested batches are rejected. Keep credentials out of manifests and use the existing environment/credential-store configuration.

All entries run sequentially. The process reuses connections and caches tokens by token endpoint, client identity/secret, tenant, scope, and TLS policy. Tokens expire 30 seconds early and never leave process memory. Company/branch headers remain request-specific; HTTP cookies do not carry across API requests. Internal company resolution is still verified per request.

The output is one JSON envelope: `ok`, `elapsedSeconds`, `skipped`, and `results`. Each result has a one-based `index`, `elapsedSeconds`, and the normal command `result`. On the first error, the runner returns a nonzero exit code and does not run later entries. It does not retry failed writes, infer dependencies, or roll back earlier successes. Inspect completed results and resulting state before deciding what to run next; never replay an entire failed write batch automatically.

Run `uv run --with requests python scripts/test_batch.py` for isolated behavioral tests, including a loopback HTTP server with fake authentication. These tests do not contact ERP or mutate business data.
