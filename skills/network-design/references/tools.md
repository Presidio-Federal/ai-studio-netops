# ServiceNow tools — Network Design

Slice of `mcp-tool-capability-lookup.yaml`. Prefix: `snow_`.
Lookup id: `snow-mcp`. Exact names only. Do not invent tools.

Use for warehouse stock, catalog order, and change records
that carry this roadmap. Do not use for Splunk, ThousandEyes,
IOS-XE, Cisco EoX, or NetBox.

| Tool | Access | Purpose |
|------|--------|---------|
| `snow_find_stockrooms` | read | Find stockrooms. Start `search="warehouse"`. |
| `snow_find_assets` | read | Search `alm_hardware`. Filter `in_stock`. Prefer `NETOPS` / stockroom. |
| `snow_get_asset` | read | One asset by asset_id, serial_number, or asset_tag. |
| `snow_find_models` | read | CMDB models when matching a replacement SKU. |
| `snow_update_asset` | write | Reserve / ship: comments + install_status. Serial is the key. |
| `snow_upsert_asset` | write | Create or update by serial_number. |
| `snow_list_catalog_items` | read | Find a catalog item to order. |
| `snow_get_catalog_item` | read | Required before order — learn variables. |
| `snow_order_catalog_item` | write | Order now. Confirm the item name first. |
| `snow_get_request` | read | Read back REQ / RITM. |
| `snow_find_locations` | read | Destination site. |
| `snow_create_change` | write | CHG for a cutover / software / config window. |
| `snow_get_change` | read | Read the CHG back. |
| `snow_find_changes` | read | Existing CHG for this work. |

`snow_query_table` is GET-only, max 50 rows. Prefer the named
tools above.
