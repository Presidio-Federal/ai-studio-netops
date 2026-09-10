# Warehouse and coordination — Network Design

Exact tools: `references/tools.md`. Demo stock lives in
ServiceNow, not in this file. Call the tools. Do not memorize
serials from an example.

## Check (every design invoke that has hardware items)

```text
snow_find_stockrooms(search="warehouse")
snow_find_assets(stockroom=<name or sys_id>, install_status=in_stock)
```

Filter to network gear (`NETOPS` comments / Cisco router and
switch models). Laptops and printers are not this roadmap.

Only `in_stock` is shippable. `in_transit` / `in_use` in a
stockroom is not available.

Match **physical models** to the replacement SKU already on
`state/lifecycle.json` (`selected_replacement` or Cisco
`recommended_replacement`). Lab images (`cat8000v`, `iosvl2`)
are not warehouse models. If no SKU is on the row, report
that — do not invent one.

Record what you found on `warehouse.found` (asset tag + model
+ serial together). `coverage.warehouse` is `current` after a
successful find, `missing` if MCP failed.

## Coordinate (only when they ask this turn)

Words like coordinate, order, reserve, ship, execute the
roadmap, start the logistics — authorization to mutate.

1. Confirm the unit (tag, model, serial) in the reply before
   the write if more than one unit fits.
2. Reserve: `snow_update_asset` — comments name this roadmap
   item and the site. `in_stock` until it actually ships.
3. If nothing in stock matches the SKU: resolve a catalog
   item (`snow_list_catalog_items` → `snow_get_catalog_item`)
   then `snow_order_catalog_item` with variables from get.
   Read back with `snow_get_request`. Never guess variable
   names.
4. A software or config cutover that needs a window:
   `snow_create_change` then `snow_get_change`. Report the
   CHG number. Ordering a catalog item is a REQ, not a CHG.

Do not place a catalog order or reserve on a design-only
ask. Check stock anyway and write `stock` on each hardware
item (`in_stock` / `not_in_stock` / `not_checked`).

## Dates from logistics

Delivery / install dates come from the REQ/RITM/CHG or
asset comments after the MCP return. Put them on the
hardware item `date` with `date_basis` `servicenow`. Do not
invent an ETA.
