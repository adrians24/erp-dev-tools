# API command reference

Use the launcher in [SKILL.md](../SKILL.md). In older examples, replace the `Invoke-RunApi` function name with `& $runApi`; no function initialization is needed. Read only the reference for the requested operation; examples use sample IDs and dates that must be adapted to the target data. Historical observations describe earlier runs, not current service status.

- [ERP context and generic requests](erp-requests.md): context lookup, database expectations, raw methods and paths.
- [Sales orders and shipments](salesorders-shipments.md): creation and shipment actions.
- [Customers and purchase orders](customers-purchaseorders.md): customer lookup, numbering, order bodies and receipts.
- [Warehouses, locations and inventory](warehouses-inventory.md): bins, business-account locations, branches and stock queries.
- [Discounts and lot/serial classes](discounts-lotserial.md): sequences, pending breakpoints and promotion.
- [Kit specifications and assemblies](kits.md): revisions, components, allocations and release.
- [Inventory receipts](inventory-receipts.md): receipt creation and release.
- [Sales Order Service](salesorder.md): host selection, context, token checks and `/api/v3/...` requests.
- [Configuration](configuration.md): credential sources, environment overrides and database validation limits.
- [Batch requests](batch.md): sequential requests with reusable authentication and one JSON result.

For options not shown here, use `Invoke-RunApi <surface> <command> --help`. Surface options such as `--environment`, `--database`, `--tenant-id` and `--branch-id` precede the command. Commands acquire their own authentication; a separate token check is only useful for diagnosis.
