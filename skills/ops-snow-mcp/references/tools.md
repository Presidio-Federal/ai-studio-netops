# ServiceNow tools

Slice of `mcp-tool-capability-lookup.yaml` (2026-08-23). Studio uses live MCP for schemas.
Prefix: `snow_`. Lookup id: `snow-mcp`.

Use when:
- Incidents (INC), catalog requests (REQ/RITM), change requests (CHG/CTASK)
- Hardware assets (alm_hardware), CMDB computers, models, locations, stockrooms
- Users, assignment groups, SLAs, knowledge articles
- Service Catalog browse/cart/order

Do not use for:
- Network device config (cisco-iosxe) or DCIM cabling (netbox-mcp)
- Arbitrary writes to unknown tables — snow_query_table is GET-only, max 50 rows

Typical flows:
- Incident: snow_find_incidents → snow_get_incident (includes task_slas) → snow_update_incident
- Create INC: snow_create_incident(short_description=..., jamf_evidence=optional)
- Dispatch: snow_find_users / snow_list_group_members → snow_update_incident(assigned_to=...) → snow_update_user(availability='busy', confirm=true)
- Catalog: snow_list_catalogs → snow_list_catalog_items → snow_get_catalog_item → snow_order_catalog_item OR cart checkout
- Warehouse: snow_find_models → snow_upsert_asset(serial_number=...)
- Change: snow_create_change → snow_upsert_change_task → snow_get_change

| Tool | Access | Required | Purpose |
|------|--------|----------|---------|
| `snow_test_connection` | read | — | Test connectivity to ServiceNow. |
| `snow_list_catalogs` | read | — | List ServiceNow Service Catalogs available to the authenticated client. |
| `snow_list_catalog_categories` | read | catalog_id | List categories in a ServiceNow Service Catalog (e.g. |
| `snow_list_catalog_items` | read | — | List / search ServiceNow catalog items (devices and services available to order). |
| `snow_get_catalog_item` | read | item_id | Get details for a single ServiceNow catalog item by item_id (sys_id), including price, description, category, and order variables. |
| `snow_get_cart` | read | — | Get the current ServiceNow Service Catalog shopping cart for the authenticated client. |
| `snow_add_to_cart` | write | item_id | Add a ServiceNow catalog item to the shopping cart. |
| `snow_update_cart_item` | write | cart_item_id, quantity | Update the quantity of an existing cart line item. |
| `snow_remove_from_cart` | write | cart_item_id | Remove a single line item from the ServiceNow shopping cart by cart_item_id (from snow_get_cart / snow_add_to_cart). |
| `snow_clear_cart` | write | — | Remove all items from the current ServiceNow Service Catalog shopping cart. |
| `snow_checkout_cart` | write | — | Checkout / submit the current ServiceNow shopping cart. |
| `snow_order_catalog_item` | write | item_id | Order a ServiceNow catalog item immediately (order_now) without using the shopping cart. |
| `snow_get_request` | read | — | Get a ServiceNow Service Catalog Request (REQ) and its Requested Items (RITM). |
| `snow_find_incidents` | read | — | Search / list ServiceNow incidents. |
| `snow_find_requests` | read | — | Search / list ServiceNow Service Catalog Requests (REQ). |
| `snow_find_users` | read | — | Find ServiceNow users / EUC demo engineers. |
| `snow_update_user` | write | — | Patch a sys_user for EUC demo dispatch state. |
| `snow_ensure_user` | write | email | Find a ServiceNow sys_user by email or create a minimal active user if missing. |
| `snow_get_incident` | read | — | Get a single ServiceNow incident by incident_number (e.g. |
| `snow_create_incident` | write | short_description | Create a ServiceNow incident. |
| `snow_update_incident` | write | — | Update an existing ServiceNow incident by incident_number or incident_id. |
| `snow_find_models` | read | — | Find ServiceNow CMDB models (cmdb_model) to use when creating hardware assets. |
| `snow_find_assets` | read | — | Search ServiceNow hardware assets (alm_hardware). |
| `snow_get_asset` | read | — | Get a single ServiceNow hardware asset by asset_id (sys_id), serial_number, or asset_tag. |
| `snow_create_asset` | write | serial_number | Create a ServiceNow hardware asset (alm_hardware). |
| `snow_update_asset` | write | — | Update a ServiceNow hardware asset. |
| `snow_upsert_asset` | write | serial_number | Create or update a ServiceNow hardware asset by serial_number (preferred for Coupa receive). |
| `snow_find_assignment_groups` | read | — | Find ServiceNow assignment groups (sys_user_group). |
| `snow_find_locations` | read | — | Find cmn_location hubs and sites (Presidio Hub - *, Disney sites). |
| `snow_find_stockrooms` | read | — | Find alm_stockroom pools (AE spare / Staging / Loaner) by hub. |
| `snow_find_slas` | read | — | Find SLA definitions (contract_sla, fallback sla). |
| `snow_get_task_slas` | read | — | Get live task_sla clocks for an INC/REQ/task (has_breached, percentage, planned_end_time). |
| `snow_find_knowledge` | read | — | Search kb_knowledge articles (e.g. |
| `snow_get_knowledge` | read | — | Get a kb_knowledge article by number (e.g. |
| `snow_create_knowledge` | write | short_description, text | Create a kb_knowledge article for first-line troubleshooting (e.g. |
| `snow_update_knowledge` | write | — | Update an existing kb_knowledge article (short_description, text, meta, topic, active) by number or knowledge_id. |
| `snow_list_group_members` | read | — | List members of a sys_user_group (e.g. |
| `snow_find_cis` | read | — | Find cmdb_ci_computer records (e.g. |
| `snow_get_ci` | read | — | Get one cmdb_ci_computer by ci_id, name, or serial_number. |
| `snow_find_companies` | read | — | Find core_company records (Disney EUC vs DCL scope). |
| `snow_find_changes` | read | — | Search change_request records (CHG…). |
| `snow_get_change` | read | — | Get a change_request by number (CHG…) or change_id, including plan fields and change_tasks[] (set include_tasks=false to skip tasks). |
| `snow_create_change` | write | short_description | Create a change_request. |
| `snow_update_change` | write | — | Update a change_request by number (CHG…) or change_id. |
| `snow_find_change_tasks` | read | — | Search change_task records (CTASK…). |
| `snow_upsert_change_task` | write | — | Create or update a change_task. |
| `snow_query_table` | read | table | Read-only Table API escape hatch: any table + encoded query + optional fields. |

