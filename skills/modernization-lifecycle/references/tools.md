# MCP tools (Modernization-Lifecycle)

Studio uses live MCP for schemas. Do not invent tools. Tool names
live in this job skill — there is no separate MCP skill zip.

## Cisco API (`cisco-api`)

| Tool | Purpose |
|------|---------|
| `cisco_get_eox_product_ids` | EoL by PID |
| `cisco_get_eox_by_dates` | EoL in a date range |
| `cisco_get_eox_by_serial_numbers` | EoL by serial |
| `cisco_get_eox_by_sw_release` | EoL by software release (dates for that train) |
| `cisco_psirt_advisory_by_cve` | Advisory by CVE |
| `cisco_psirt_advisory_by_bugid` | Advisory by Bug ID |
| `cisco_psirt_product_id_finder` | Find product names/IDs for PSIRT |
| `cisco_psirt_by_product` | Advisories for a product |
| `cisco_psirt_software` | PSIRT Software Checker — versions, platforms, advisories; copy a recommended/fixed-in train if Cisco returned one |
| `cisco_get_product_info_by_serials` | PID/series from serials |

Bug tools exist on the server; do not use them on a Lifecycle visit
unless PSIRT returned nothing and they asked for bugs.

## Cisco CCW (`cisco-ccw`)

| Tool | Purpose |
|------|---------|
| `ccw_get_catalog_items` | Price / availability / lead time by SKU |

`priceListCode=GLUS`, `currency=USD`. Only a SKU already on the
row (`selected_replacement`, else Cisco `recommended_replacement`)
and different from `pid`. Do not call estimate tools
(`ccw_search_estimates`, `ccw_get_estimate`, `ccw_copy_estimate`,
`ccw_share_estimate`). `unitListPrice.cost` is the list price.
`ERR-03` / `ERR-10` is unpriced, not a failed visit.

## Arguments the collect script sends

| Tool | Arguments |
|------|-----------|
| `cisco_get_eox_product_ids` | `product_ids` (one PID string) |
| `cisco_get_eox_by_serial_numbers` | `serial_numbers` |
| `cisco_get_product_info_by_serials` | `serial_numbers` |
| `cisco_get_eox_by_sw_release` | `software_release`, and `product_id` when the tool accepts it |
| `cisco_psirt_product_id_finder` | `product` |
| `cisco_psirt_by_product` | `product` (retry `product_id` if rejected) |
| `cisco_psirt_software` | `version` |
| `ccw_get_catalog_items` | `skus`, `priceListCode=GLUS`, `currency=USD` |
| `nvd_get_cve` | `cve_id`, `concise=true` |

A schema error is a gap on that PID. The script does not guess a
third argument name.

## NIST NVD (`nist-nvd`)

| Tool | Purpose |
|------|---------|
| `nvd_get_cve` | CVE summary. `concise=True` |

Only for CVE ids already returned by PSIRT (cap 3). Do not
`nvd_search_cve` on this visit.
