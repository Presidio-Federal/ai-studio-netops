# Estate evidence — Modernization Analysis

Fill `state/lifecycle.json` from workspace files and this-turn
operator input. Never copy hostnames or PIDs from skill examples.

Do **not** infer hardware or software from a hostname, role, or
tag. Do not invent a commercial SKU. The product id is
`device_type` / `node_definition` **as written** until a serial
or Cisco lookup says otherwise.

## Where identity lives

Prefer Ops NetBox SoT when present. Then Sync access inventory.
Then this-turn upload or verbal.

### `inventory/infra-sot.json` (Ops NetBox SoT)

Writer: Ops NetBox SoT. Schema `infra-sot/v1`.

Per `devices[]` row:

| Record | Path |
|--------|------|
| hostname | `name` |
| product id (group key) | `device_type` as written |
| software | `software_version` (null if the box was not GETtable) |
| role | `role` |
| `pid_source` | `netbox` |

`seed[].node_definition` matches `device_type` when both exist.
Use `devices[]` as the estate list, not `seed[]` alone.

`source.kind` `cmdb` (or `inventory` if they named files only).
`reliability` `medium`. `ref` `inventory/infra-sot.json`.

### `inventory/prod.json` (Ops Network Sync)

Writer: Ops Network Sync. Schema `network-access-inventory/v3`.

Per `devices[]` row:

| Record | Path |
|--------|------|
| hostname | `name` |
| product id (group key) | `source_metadata.node_definition` if present, else do not invent a pid from `platform` (`iosxe` is an OS, not a product) |
| role | `role` |
| `pid_source` | `device_type` when grouped on `node_definition` |

`platform` may be `iosxe` for every Cat8Kv. Do not split those
rows by `role` into different products.

`source.kind` `inventory`. `reliability` `medium`. `ref`
`inventory/prod.json`.

If both files exist: same hostname → prefer SoT `device_type`.
Keep the SoT name list; add prod-only names as extra rows.

### Upload / verbal / live

| kind | reliability | When |
|------|-------------|------|
| `live` | `high` | Operator-named serial or software already on a workspace file (e.g. `health/iosxe/<stamp>.json`). Do not call IOS-XE. |
| `upload` | `low` | Spreadsheet or file they attached this turn |
| `verbal` | `low` | Spoken or typed asset list this turn |
| `cmdb` | `medium` | They named NetBox / CMDB; use infra-sot |

`pid_source` `upload` / `verbal` / `serial` / `unknown` as
matches the evidence. `ref` is the path or `operator`.

Do not replace a `high` row with `medium` or `low` unless they
explicitly override.

## Grouping

One `items[]` row per distinct product id (`pid`):

1. Serial already resolved to a Cisco PID → that PID (`serial`).
2. Else `device_type` / `node_definition` **as written**.
3. Else what they named on upload/verbal.
4. Else `pid_source` `unknown` — still write the hostnames. Gaps.

`devices[]` is hostname **strings** only. `quantity` is that
array’s length. `software_versions` only if the evidence has
them. Missing serial or version: Gaps, still write the row.

`recommended_replacement` stays null until Lifecycle copies a
hardware SKU Cisco returned. `selected_replacement` stays null
until they **name** a SKU. `recommended_software` stays null
until Lifecycle copies a train Cisco returned. Do not fill any
of those from a map. New rows: `selected_replacement` null,
`replacement_family` null, `replacement_candidates` `[]`,
`replacement_ask` null.

`detail_ref` `lifecycle/items/<pid>.json` (safe filename:
letters, digits, `.` `_` `-` only).
