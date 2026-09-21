# Sales Order Service

Local defaults:

```powershell
Invoke-RunApi salesorder context
```

Default local Sales Order host: `https://localhost:5001`

Internal resolved context (this validates company context; it does not select the Sales Order host):

```powershell
Invoke-RunApi salesorder --environment internal context
```

Check write-token acquisition (the output contains metadata and claims, not the bearer token):

```powershell
Invoke-RunApi salesorder token
```

Acquire a read token with an explicit tenant:

```powershell
Invoke-RunApi salesorder --tenant-id <tenant-id> --scope visma.net.erp.salesorder:read token
```

Check the local host:

```powershell
Invoke-RunApi salesorder health
```

Ensure a stopped local host is started and healthy before a request:

```powershell
& (Join-Path $apiSkillRoot 'scripts\Ensure-SalesOrderService.ps1')
```

The helper uses `salesOrderRepository` from the local machine profile, starts the documented Sales Order API project in a hidden process, writes logs below `%LOCALAPPDATA%\Visma\Codex\erp-dev-tools\logs`, and leaves the healthy service running. Startup is serialized by the configured shared environment mutex. It rechecks health after acquiring the lock, refuses to replace an occupied unhealthy port, and never starts a non-loopback host.

Call a different host explicitly:

```powershell
Invoke-RunApi salesorder --server-url https://example-host health
```

Generic request with auth:

```powershell
Invoke-RunApi salesorder request GET /api/v3/SalesOrders/SO/006759
```

Create a sales order inline:

```powershell
Invoke-RunApi salesorder create salesorder --body-json '{"type":"SO","customer":{"id":"10000"}}'
```

Force a branch:

```powershell
Invoke-RunApi salesorder --branch-id 13 create salesorder --body-file .\salesorder.json
```

`--environment internal` resolves company context through SystemDataService, but the request host still comes from `--server-url`, `VISMA_SALESORDER_SERVER_URL`, or the localhost default. Set the intended host explicitly for remote calls. Local `context` skips SystemDataService unless `--company-id` is supplied.
