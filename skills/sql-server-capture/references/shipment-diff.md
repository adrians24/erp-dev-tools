# Shipment SQL and table diffs

Use this mode when the authorized action is to create a shipment and the investigation needs both generated SQL and row changes. Initialize `$sqlCapture` from the parent skill first.

```powershell
& $sqlCapture create-shipment-diff 000797 --shipment-warehouse 1
```

The order number and warehouse above are examples. Use the actual target from the task. Optional arguments include `--order-type` (default `SO`), `--shipment-date`, `--operation I|R`, `--api-timeout` (default 120 seconds), and the capture filters from the parent skill. `--api-script` overrides the sibling `run-api-requests/scripts/run_api_requests.py` path.

The generated API command and SQL capture both use the configured local profile. `--database` is forwarded to the API and SQL connections and otherwise comes from that profile. The snapshots have no `CompanyId` filter. Use this convenience mode only when the order and inventory scope are unambiguous. For internal or multi-company workflows, use `around` with an explicitly targeted API command and before/after queries scoped according to `$sql-server`.

## Compared tables

| Scope | Tables |
| --- | --- |
| Order | `SOOrder`, `SOLine`, `SOLineSplit`, `SOOrderShipment` |
| Resulting shipment | `SOShipment`, `SOShipLine`, `SOShipLineSplit` |
| Inventory planning and quantities | `INItemPlan`, `INSiteStatus`, `INLocationStatus` |

The helper compares selected key and state columns, not every column or a full database snapshot. It reads the order and inventory scope before the action and follows the resulting shipment afterward. Shipment tables use an empty before baseline; reported inserts there represent observed shipment rows, so they are not proof that each row was newly inserted if an existing shipment was reused.

## Additional output

`observed_entities` includes the order and shipment identifiers, the source of the resolved shipment number (`command_result` or `soordershipment_diff`), pre/post inventory scopes, and `scope_warnings`. Review `new_post_site_keys_not_in_pre_scope`: those keys lack a matching before snapshot.

`changed_tables` lists tables with differences. `table_diffs` maps each table to `key_columns`, `compare_columns`, pre/post row counts, inserted/updated/deleted counts, and the corresponding row details. Updated rows contain the key and per-column `before` / `after` values.

Use `INSiteStatus` for warehouse quantities and `INLocationStatus` for location quantities. Attribute changes to the action only as far as the scope and captured SQL support; concurrent writes can also change these rows.
