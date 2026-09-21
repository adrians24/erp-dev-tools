# Kit Specifications and Assemblies

List kit specifications:

```powershell
Invoke-RunApi erp list kit-specification --page-size 10
```

List kit specifications filtered by kit and revision:

```powershell
Invoke-RunApi erp list kit-specification --kit-inventory-id KIT001 --revision-id A1
```

Read all revisions for one kit specification:

```powershell
Invoke-RunApi erp get kit-specification KIT001
```

Read one kit specification revision:

```powershell
Invoke-RunApi erp get kit-specification KIT001 A1
```

Create a kit specification:

```powershell
Invoke-RunApi erp create kit-specification --body-file .\kit-specification.json
```

Update a kit specification revision:

```powershell
Invoke-RunApi erp update kit-specification KIT001 A1 --body-file .\kit-specification-update.json
```

Example stock-kit create body:

```json
{
  "operation": "Update",
  "kitInventoryID": { "value": "KIT001" },
  "revisionID": { "value": "0001" },
  "descr": { "value": "Codex kit spec" },
  "isActive": { "value": true },
  "isNonStock": { "value": null },
  "allowCompAddition": { "value": true },
  "stockComponentLines": [
    {
      "operation": "Insert",
      "lineNbr": { "value": 0 },
      "compInventoryID": { "value": "COMP001" },
      "uom": { "value": "STK" },
      "dfltCompQty": { "value": 1.5 },
      "minCompQty": { "value": 1.0 },
      "maxCompQty": { "value": 3.0 },
      "allowQtyVariation": { "value": false },
      "allowSubstitution": { "value": false },
      "disassemblyCoeff": { "value": 1.0 }
    }
  ]
}
```

Example stock-kit update body:

```json
{
  "operation": "Update",
  "kitInventoryID": null,
  "revisionID": null,
  "descr": { "value": "Codex kit spec updated" },
  "isActive": { "value": false },
  "isNonStock": { "value": false },
  "allowCompAddition": { "value": true },
  "stockComponentLines": [
    {
      "operation": "Update",
      "lineNbr": { "value": 0 },
      "compInventoryID": null,
      "uom": { "value": "STK" },
      "dfltCompQty": { "value": 2.25 },
      "minCompQty": { "value": 1.0 },
      "maxCompQty": { "value": 4.0 },
      "allowQtyVariation": { "value": true },
      "allowSubstitution": { "value": true },
      "disassemblyCoeff": { "value": 1.0 }
    }
  ]
}
```

List kit assemblies:

```powershell
Invoke-RunApi erp list kit-assembly --page-size 10
```

List one kit assembly with expanded allocations:

```powershell
Invoke-RunApi erp list kit-assembly --kit-assembly-type P --kit-assembly-ref-no 000001 --expand-stock-components --expand-kit-allocations
```

Read one kit assembly:

```powershell
Invoke-RunApi erp get kit-assembly P 000001
```

Create a kit assembly:

```powershell
Invoke-RunApi erp create kit-assembly --body-file .\kit-assembly.json
```

Update a kit assembly:

```powershell
Invoke-RunApi erp update kit-assembly P 000001 --body-file .\kit-assembly-update.json
```

Delete a kit assembly:

```powershell
Invoke-RunApi erp delete kit-assembly P 000001
```

Release a kit assembly:

```powershell
Invoke-RunApi erp action kit-assembly release P 000001
```

Example kit assembly create body:

```json
{
  "type": "P",
  "itemId": { "value": "KIT001" },
  "revision": { "value": "0001" },
  "date": { "value": "2026-04-01T00:00:00" },
  "quantity": { "value": 2.0 },
  "kitAllocations": [
    {
      "operation": "Insert",
      "quantity": { "value": 3.5 }
    }
  ]
}
```

Example kit assembly update body:

```json
{
  "type": "P",
  "kitAllocations": [
    {
      "operation": "Update",
      "lineNbr": { "value": 2 },
      "quantity": { "value": 4.0 }
    }
  ]
}
```

Important: omit `postPeriod` unless you already know a valid open period for that environment.
