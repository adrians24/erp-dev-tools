# Inventory Receipts

List inventory receipts:

```powershell
Invoke-RunApi erp list inventory-receipt --page-size 10
```

Read an inventory receipt:

```powershell
Invoke-RunApi erp get inventory-receipt 1500171
```

Create an inventory receipt:

```powershell
Invoke-RunApi erp create inventory-receipt --body-file .\inventory-receipt.json
```

Minimal inventory receipt body:

```json
{
  "hold": { "value": false },
  "receiptLines": [
    {
      "operation": "Insert",
      "inventoryNumber": { "value": "ST1" },
      "warehouseId": { "value": "1" },
      "locationId": { "value": "1" },
      "quantity": { "value": 1.0 },
      "unitCost": { "value": 1.0 },
      "uom": { "value": "STK" }
    }
  ]
}
```

Release an inventory receipt:

```powershell
Invoke-RunApi erp action inventory-receipt release 1500171
```
