# Screen lookup and interaction

## Find a screen or control

Use [`screens.json`](screens.json) for the maintained aliases, screen IDs, titles, and known record-key hints. `Open-ErpScreen.ps1 -Screen <alias>` resolves those entries and accepts arbitrary `-Keys`; use `-ScreenId` for a screen outside the catalog.

For other screens, use the UI search (Alt+S) or the target database's `SiteMap` via the `sql-server` skill:

```sql
SELECT DISTINCT ScreenID, Title FROM SiteMap
WHERE Title LIKE '%stock%' AND ScreenID IS NOT NULL
ORDER BY ScreenID
```

This query is for local screen discovery; internal queries must follow the SQL skill's tenant-filter rules. `DISTINCT` removes multitenant duplicates. A `PL` suffix, such as `AR2095PL`, denotes the list/inquiry variant. ASPX page titles often say `Untitled Page`, so they are not a screen-name directory.

For ambiguous fields or repeatable selectors, inspect `src/Base/Site/Pages/<Module>/<ScreenId>.aspx`. Its `DataField` declarations identify controls; rendered IDs such as `ctl00_phF_form_edDiscountID` can be used through `playwright-cli run-code`. Snapshot iframe refs (for example `f5eNN`) differ from shell refs and change after postbacks.

## Data entry

- New records: fill the key field, then click another field to trigger its blur callback. Tab alone may not commit, and the main toolbar `+` can be unreliable through snapshot refs. A committed new key drops previous record-key URL parameters and resets the form/grid.
- Grid rows: the grid toolbar `+` opens the first editable cell; fill it and use Tab to advance. Tabbing beyond the last cell may append an empty row that Save discards.
- AR discount breakpoints use Pending Break Amount/Percent/Date. When the requested task includes activating those values, Update Discounts promotes them to current through a Filter Date dialog. Use the date appropriate to the task; the dialog defaults to today.
- The main toolbar commonly starts with back, Save & Close, Save, undo, add, delete, and record navigation. Prefer labels or confirmed selectors when icons are ambiguous. A successful save rewrites the URL with record keys.

## Recovery and diagnostics

After about 30–60 minutes idle, `#errorModal` may report session expiry and intercept clicks. If closing it and navigating fails while the site still answers HTTP requests, open a new tab with `tab-new <login url>` and authenticate again. The old tab's unsaved state will be lost; account for that before closing it or repeating data entry.

Previously observed background noise includes a 404 for `Lib/vsn-components/vsn-components.js` / Gaia Chat UI, keep-alive timeouts, and meta-element parsing errors. Prioritize errors tied to the observed failure, but investigate these too if evidence connects them to it.
