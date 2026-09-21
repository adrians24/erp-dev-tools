# Context and Generic Requests

Local ERP context:

```powershell
Invoke-RunApi erp context
```

Internal ERP context:

```powershell
Invoke-RunApi erp --environment internal context
```

Validate that the configured internal company resolves to a non-default expected database (this flag does not switch databases):

```powershell
Invoke-RunApi erp --environment internal --database <expected-database> context
```

Generic ERP request:

```powershell
Invoke-RunApi erp request GET /v1/shipment/000014
```

Generic internal ERP request with query:

```powershell
Invoke-RunApi erp --environment internal request GET /v1/salesorder --query PageNumber=1 --query PageSize=1
```
