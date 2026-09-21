# Customers and Purchase Orders

List customers:

```powershell
Invoke-RunApi erp list customer --page-size 10
```

Read a customer:

```powershell
Invoke-RunApi erp get customer 10000
```

Read a customer by internal ID:

```powershell
Invoke-RunApi erp get customer-internal 56677
```

Create a customer:

```powershell
Invoke-RunApi erp create customer --body-file .\customer.json
```

List purchase orders:

```powershell
Invoke-RunApi erp list purchaseorder --page-size 10
```

Read a purchase order:

```powershell
Invoke-RunApi erp get purchaseorder PO000123
```

Create a purchase order:

```powershell
Invoke-RunApi erp create purchaseorder --body-file .\purchaseorder.json
```

Update a purchase order:

```powershell
Invoke-RunApi erp update purchaseorder PO000123 --body-file .\purchaseorder-update.json
```

Create a purchase receipt from a purchase order:

```powershell
Invoke-RunApi erp action purchaseorder create-purchase-receipt PO000123
```

Update a customer by customer number:

```powershell
Invoke-RunApi erp update customer 10000 --body-file .\customer-update.json
```

Update a customer by internal ID:

```powershell
Invoke-RunApi erp update customer-internal 56677 --body-file .\customer-update.json
```

List sales orders for one customer:

```powershell
Invoke-RunApi erp list customer-salesorder --customer-no 10000 --page-size 10
```

List contacts for one customer:

```powershell
Invoke-RunApi erp list customer-contact --customer-no 10000 --page-size 10
```

Example customer create body (adapt IDs to the target environment):

```json
{
  "number": { "value": "C4L21" },
  "name": { "value": "Codex Customer" },
  "customerClassId": { "value": "1" }
}
```

Customer numbering:

- ERP may replace the requested `number` with an auto-assigned customer number. Read back the created customer or use the runner's resolved output.

Example purchase order create body:

```json
{
  "orderType": { "value": "RegularOrder" },
  "supplier": { "value": "50000" },
  "hold": { "value": false },
  "date": { "value": "2026-04-02T00:00:00" },
  "promisedOn": { "value": "2026-04-03T00:00:00" },
  "description": { "value": "Codex purchase order" },
  "location": { "value": "MAIN" },
  "supplierRef": { "value": "Codex-PO" },
  "lines": [
    {
      "operation": "Insert",
      "lineNumber": { "value": 1 },
      "inventory": { "value": "ST1" },
      "lineType": { "value": "GoodsForInventory" },
      "warehouse": { "value": "1" },
      "lineDescription": { "value": "Codex purchase order line" },
      "uom": { "value": "STK" },
      "orderQty": { "value": 2.0 },
      "unitCost": { "value": 2.0 },
      "receiptAction": { "value": "Accept" }
    }
  ]
}
```

Prior observations (not a current health check):

- `list`, `get`, `create`, and `update` worked in both `localhost` and `internal`.
- `erp action purchaseorder create-purchase-receipt <purchase_order_no>` previously returned `500` in both environments with `Error creating purchase receipt from purchase order. Object reference not set to an instance of an object.`
