# Discounts and Lot/Serial Classes

List discount codes:

```powershell
Invoke-RunApi erp list discount-code --page-size 10
```

List discounts:

```powershell
Invoke-RunApi erp list discount --page-size 10
```

List discounts filtered by code and series:

```powershell
Invoke-RunApi erp list discount --discount-code 2PERCENT --series 01 --page-size 10
```

Read one discount sequence:

```powershell
Invoke-RunApi erp get discount 2PERCENT 01
```

Create a discount sequence:

```powershell
Invoke-RunApi erp create discount --body-file .\discount.json
```

Delete a discount sequence:

```powershell
Invoke-RunApi erp delete discount 2PERCENT 01
```

Promote pending discount values:

```powershell
Invoke-RunApi erp action discount update-discounts 2PERCENT 01
```

Read one discount code:

```powershell
Invoke-RunApi erp get discount-code 100
```

List lot serial classes:

```powershell
Invoke-RunApi erp list lot-serial-class --page-size 10
```

Read one lot serial class:

```powershell
Invoke-RunApi erp get lot-serial-class 0
```

Example discount create body:

```json
{
  "discountCode": { "value": "2PERCENT" },
  "series": { "value": "CDX0402" },
  "description": { "value": "Codex discount" },
  "discountBreakpoints": [
    {
      "operation": "Insert",
      "pendingDiscountPercent": { "value": 2.0 },
      "pendingDate": { "value": "2026-04-02T00:00:00" }
    }
  ]
}
```

Prior discount observations:

- Use pending breakpoint fields, not current-value breakpoint fields.
- `update-discounts` without `--filter-date` worked.
