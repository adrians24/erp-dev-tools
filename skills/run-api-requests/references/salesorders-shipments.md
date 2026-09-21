# Sales Orders and Shipments

Create a sales order from a file:

```powershell
Invoke-RunApi erp create salesorder --body-file .\salesorder.json
```

Create an inventory item inline:

```powershell
Invoke-RunApi erp create inventory --body-json '{"inventoryNumber":{"value":"10001"}}'
```

Create a shipment from a sales order:

```powershell
Invoke-RunApi erp action salesorder create-shipment 000746 --shipment-warehouse 1
```
