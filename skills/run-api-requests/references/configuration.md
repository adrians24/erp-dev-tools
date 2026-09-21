# API configuration

## Local ERP

Non-secret settings come from the `local` machine profile. The protected credential lives in Windows Credential Manager target `Codex.VismaErp.local`. Process environment variables override profile or stored values:

- Credentials: `VISMA_ERP_AUTHORIZATION`, `VISMA_ERP_SIGNATURE`.
- Optional settings: `VISMA_ERP_BASE_URL`, `VISMA_ERP_COMPANY_ID`, `VISMA_ERP_USER_ID`, `VISMA_ERP_VERIFY_TLS`.

`erpApiBaseUrl`, `companyId`, `erpUser`, and `database` must be configured. Local `--database` records an expected name; it does not reconfigure the ERP instance or verify its database. Targeting another local database requires an instance/company profile that actually serves it.

## Internal ERP

The `internal` machine profile provides `tokenUrl`, `clientId`, `tenantId`, `companyId`, `erpUser`, and `database`. There are no committed internal defaults. Client-secret source: `VISMA_ERP_CLIENT_SECRET`, falling back to `VISMA_SALESORDER_CLIENT_SECRET`. Use process environment values or the existing protected setup, rather than literal secrets in command arguments.

SystemDataService resolves the supplied tenant/company to an instance and database. `--database` is an expectation check, not a database selector: a nonempty returned name that differs causes failure. An empty database name is not verified by the runner. For a different database, supply the corresponding company/tenant context and verify the returned context before writing. ERP requests use the resolved instance URL unless `--base-url` overrides it.

## Sales Order Service

Supported process overrides:

`VISMA_SALESORDER_SERVER_URL`, `VISMA_SALESORDER_TOKEN_URL`, `VISMA_SALESORDER_CLIENT_ID`, `VISMA_SALESORDER_CLIENT_SECRET`, `VISMA_SALESORDER_READ_SCOPE`, `VISMA_SALESORDER_WRITE_SCOPE`, `VISMA_SALESORDER_TENANT_ID`, `VISMA_SALESORDER_BRANCH_ID`, `VISMA_SALESORDER_VERIFY_TLS`.

The selected profile provides `salesOrderServerUrl`; localhost remains a safe fallback. The local profile also provides `salesOrderRepository`, used by `Ensure-SalesOrderService.ps1` to start a stopped local host. `VISMA_SALESORDER_REPOSITORY` overrides that checkout path for the current process. Use `--server-url` or the server environment override to target another service. See [Sales Order Service commands](salesorder.md) for startup, context, and authentication checks.

If authentication is missing, report the missing variable names or credential target. Have secrets configured locally; do not request or print secret values in chat.
