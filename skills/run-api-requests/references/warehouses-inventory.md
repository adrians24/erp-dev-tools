# Warehouses, Locations, and Inventory

`warehouse-location` refers to warehouse bins; `location` refers to business-account locations.

List warehouses:

```powershell
Invoke-RunApi erp list warehouse
```

Read a warehouse:

```powershell
Invoke-RunApi erp get warehouse 1
```

List warehouse locations:

```powershell
Invoke-RunApi erp list warehouse-location --warehouse-id 1
```

Read a warehouse location:

```powershell
Invoke-RunApi erp get warehouse-location 1 1
```

List business-account locations:

```powershell
Invoke-RunApi erp list location --page-size 10
```

Read a business-account location:

```powershell
Invoke-RunApi erp get location 10000 MAIN
```

Create a business-account location:

```powershell
Invoke-RunApi erp create location --body-file .\location.json
```

Update a business-account location:

```powershell
Invoke-RunApi erp update location 10000 MAIN --body-file .\location-update.json
```

Create a warehouse location:

```powershell
Invoke-RunApi erp create warehouse-location 1 --body-file .\warehouse-location.json
```

Update a warehouse location:

```powershell
Invoke-RunApi erp update warehouse-location 1 1 --body-file .\warehouse-location-update.json
```

List branches:

```powershell
Invoke-RunApi erp list branch
```

Read a branch:

```powershell
Invoke-RunApi erp get branch 1
```

Read inventory with warehouse detail:

```powershell
Invoke-RunApi erp get inventory ST1 --warehouse-details
```

Read inventory with one warehouse filtered:

```powershell
Invoke-RunApi erp get inventory ST1 --warehouse-details --warehouse 1
```

Read inventory summary rows:

```powershell
Invoke-RunApi erp get inventory-summary ST1
```

Read inventory summary rows filtered to one warehouse and location:

```powershell
Invoke-RunApi erp get inventory-summary ST1 --warehouse 1 --location 1
```
