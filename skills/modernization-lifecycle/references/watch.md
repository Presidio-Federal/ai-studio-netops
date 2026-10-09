# Modernization Lifecycle visit

The visit is `scripts/visit_lifecycle.py`. The agent runs `collect`
under `mcp_orchestration` and `annotate` under `standard`. This
file is the manual order when stderr says `hai_mcp unavailable`.
Any other script failure: one line from stderr, then stop. Do not
collect by hand.

`collect` reads `state/lifecycle.json` and
`inventory/assets/devices.json`. It calls MCP only for estate rows whose
`pid` is a `product_id` on the asset file. No `product_id` means
Cisco is not called. It writes `inventory/assets/<pid>.json` and
merges onto the matching estate row. A family bulletin with no
single SKU is `needs_note`.
`annotate --ask <pid>=<why, then the choice>` writes
`replacement_ask`. The script does not invent that sentence, a
date, a train, or a price.

Checked and empty is `research.eox` / `software` / `ccw`
`unavailable`. That row is not collected again until `expires_at`.
`unavailable` is a real Cisco answer, including a virtual PID and
a SKU CCW will not price.

**First:** `read_file` `state/lifecycle.json` only on the manual
fallback. Missing: stop `unknown`. Do not create the estate. Do
not add devices or change pid from inventory — that is
Modernization. You may copy `software_version` from
`inventory/infra-sot.json` onto hostnames already on the row.

The example JSON is **shape only**. Never copy its hostnames or
PIDs. Use the `pid` already on each estate row.

Lifecycle dates do not get refreshed once a support date and a
replacement SKU are stored. A product with no date is asked again
so a later Cisco announcement is picked up. A replacement SKU with
no list price is asked again. `expires_at` is still stamped at
`updated_at` + 90 days, but it does not by itself cause a call.

## What needs work

A stamped `product_id` needs collect when any of:

- no `end_of_support` and no `end_of_software_support`
- `recommended_replacement` is null
- `recommended_replacement` is set and `list_cost_per_unit` is null
- estate `selected_replacement` is set and `list_cost_per_unit` is null

Do not call Cisco because PSIRT is empty, a software train is
empty, the detail file is missing, or `expires_at` has passed, when
a date and a replacement SKU and a list price are already stored.

## Always first

1. `read_file` `state/lifecycle.json` (or
   `file_explorer/state/lifecycle.json` after Access denied).
   Missing → Result `unknown`, stop.
2. For each `items[]` row, `read_file` `detail_ref` if present
   (same `file_explorer/` prefix if that is what worked). Missing
   detail is empty, not an error.
3. Do not `ls` `lifecycle/`.

Empty hardware EoX after pid and serial tries is not a failed
visit when the row is a CML / virtual `node_definition`. Mark
`research.eox` `unavailable`. Still collect software when
versions exist.

If **no** row needs work: no MCP. Do not rewrite. Result
`collected`, table is current.

Cap PIDs this turn: **8**. One sample device per PID.

## Collect (only rows that need work)

Tool names: `references/tools.md`. Use the row’s `pid` as written.
Do not invent a different chassis. Do not invent a software train.

1. **Hardware EoX** — `cisco_get_eox_product_ids` with that pid.
   Empty → retry the **same** pid with case / punctuation
   variants Cisco’s catalog uses, then
   `cisco_psirt_product_id_finder`. Serial
   on the sample (only if already on the estate or detail) →
   `cisco_get_product_info_by_serials` then
   `cisco_get_eox_by_serial_numbers`. Still empty:
   `research.eox` `unavailable`. Hardware dates and
   `recommended_replacement` stay null. That is accurate for
   virtual appliances.
2. **Software** — need a version string on the row. If
   `software_versions` is empty, `read_file`
   `inventory/infra-sot.json` (same `file_explorer/` retry) and
   copy non-null `devices[].software_version` for hostnames
   **already on this row**. Do not add hosts. Do not change pid.
   Then call `cisco_get_eox_by_sw_release` (live schema; pass the
   version string; pid/platform if the tool asks) then
   `cisco_psirt_software` (cap 2 versions). Copy software EoX
   dates onto `end_of_software_support` /
   `end_of_security_vuln_support`. Copy a
   recommended / suggested / fixed-in **version string Cisco
   returned** onto `recommended_software`. Never pick a train
   from the advisory list. Still no version:
   `research.software` `skipped`; Gaps; do not call those two
   tools.
3. **PSIRT (product)** — `cisco_psirt_by_product`. Messy name →
   `cisco_psirt_product_id_finder` first. Cap 15 advisories.
4. **NVD** — `nvd_get_cve` `concise=True` for up to 3 CVE ids from
   PSIRT.
5. **Hardware replacement SKU** — set `recommended_replacement`
   only when Cisco **hardware** EoX returned **one** SKU. Never
   put a software version in that field. Never invent a SKU.
   Family-only bulletin (Cisco named a series, not one SKU):
   leave `recommended_replacement` null. On the **item file**
   set `replacement.family`, `replacement.candidates`,
   `replacement.bulletin_url`, and `replacement.ask` as **one
   sentence of why + the choice**, using only names and size
   metrics from **that** Cisco result. Copy those four onto the
   estate row (`replacement_family` `replacement_candidates`
   `replacement_ask`). Do **not** write `selected_replacement`
   on the item file. Keep any existing `selected_replacement`
   on the estate row.
6. **CCW** — price this SKU, first match wins:
   - estate `selected_replacement` if set
   - else Cisco `recommended_replacement` if set
   Skip if that SKU is missing or equals `pid`.
   Batch unique SKUs: `ccw_get_catalog_items`. Write costs onto
   the estate row and onto the item `replacement` cost fields.
   Do not copy `selected_replacement` onto `replacement.sku`.
   No SKU to price: `research.ccw` `skipped`, costs stay null.

Empty MCP: try another valid shape, then write nulls /
`unavailable`. Never invent dates, prices, or trains.

Call budget: <= 28 Cisco API + 4 CCW + 8 NVD.

## Write

Catalog rows (also the `detail_ref` string):
`inventory/assets/<pid>.json` and `state/lifecycle.json`.

If `write_file` / `read_file` returns Access denied and Allowed
paths include `file_explorer`, retry **once** with prefix
`file_explorer/` (no leading slash, no UUID):

- `file_explorer/inventory/assets/<pid>.json`
- `file_explorer/state/lifecycle.json`

Never `/shared_workspace/HAI-ASSISTANTS-WAPSPACES/...`. Never
`sessions/`. Never `/workspace/`. Never `mkdir`. Never `ls`
`lifecycle/`. Do not put `file_explorer/` inside JSON
`detail_ref`.

For each PID collected:

1. `write_file` `inventory/assets/<pid>.json` (or the
   `file_explorer/` form after Access denied). Safe filename:
   letters, digits, `.` `_` `-` only. If that write still fails:
   merge onto the estate anyway; Gaps the detail file.
   Set top-level `keys` to the deduplicated `device:<name>`
   union from that item file's `devices`, or `[]`.
2. Re-read `state/lifecycle.json` (same prefix that worked).
   Merge **this PID’s** research onto the matching row. Keep
   `quantity` `devices` `summary` `source` `pid_source`
   `dispatched` `recommendations` `goals` `guidance`
   `assessment` `plan`
   `roadmap_ref` `selected_replacement`
   `selected_replacement_source`. Set
   `recommended_replacement` only from Cisco hardware EoX this
   visit or keep the prior value. Never overwrite
   `selected_replacement`. Set `recommended_software` only
   from Cisco software EoX / PSIRT Software Checker this visit or
   keep the prior value. Copy family / candidates / ask onto the
   row when Cisco named a family. Stamp `updated_at` / `expires_at`.
   `source_agent` `modernization-lifecycle`. Recount `coverage`
   (`with_software` = rows with `recommended_software` or
   `end_of_software_support`).
   Recompute top-level `keys` as the deduplicated
   `device:<name>` union from all `items[].devices`, or `[]`.
   `write_file` the full object. Do not drop other PIDs.
