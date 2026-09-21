# Internal sessions

Resolve the current instance using the installed `run-api-requests` skill's ERP context command; do not assume a previously observed instance is current:

```powershell
# $erpUiRoot is the directory containing the ERP UI SKILL.md.
$erpContextScript = Join-Path (Split-Path -Parent $erpUiRoot) 'run-api-requests\scripts\Invoke-RunApi.ps1'
& $erpContextScript erp --environment internal context
```

Use the resolved instance, database, company, and branch from the current request and machine profile. Do not retain previously observed internal context in the plugin.

## Mock login

Internal redirects to `/mocks/account/login`. Username is `type=email`; local development usernames fail browser validation. Use the current developer's authorized email account for the requested company. Fill the email, click Login, and verify the company in the resulting shell.

If the account cannot authenticate, inspect the authentication/access error rather than trying arbitrary identities. For an authorized user lookup, use the `sql-server` skill against the resolved internal database:

```sql
SELECT TOP 50 Username, FullName, Email, IsApproved, DeletedDatabaseRecord
FROM Users
WHERE CompanyID = <configured-company-id>
ORDER BY CreationDate DESC
```

## Navigation

Direct screen URLs can lose `ScreenId` while redirecting through login. After the shell title becomes a real screen (often `Start page`), use Open menu and its search field. For example, Stock Items may open list `IN2025PL`; New stock item opens entry screen `IN202500`.

Once authenticated, navigation can use the current workspace path, such as `/2101531208/(W(1))/main?ScreenId=IN202500`. Derive the instance and workspace from the actual URL instead of hardcoding the example. A redirect to mock login means authentication must be restored before continuing.

For `IN202500`, a save adds `InventoryCD` to the URL, sometimes padded with `+` characters. When independent persistence verification is needed, query the exact requested item and resolved company through `sql-server`:

```sql
SELECT CompanyID, InventoryCD, Descr, StkItem, ItemStatus, ItemClassID,
       TaxCategoryID, PostClassID, LotSerClassID, BaseUnit, SalesUnit, PurchaseUnit
FROM InventoryItem
WHERE CompanyID = <configured-company-id> AND InventoryCD = '<requested item code>'
```
