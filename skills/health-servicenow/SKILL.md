---
name: health-servicenow
version: "2.0.1"
description: "v2.0.1 — Read-only ServiceNow board visit. Scope is decided in the query (agent-managed inventory device names, marker, match terms) so a shared instance returns only this lab's tickets; typed entity columns are discovered once from sys_dictionary and read as row columns (device, interface, ip, service, rfc — the edges); board on health/metadata-servicenow.json; stamp only when a ticket's state, urgency, typed field, rfc, issue, or update time moved. snow_query_table only; no find/get. Use when the invoke names the ServiceNow health check. Do not file or update tickets."
---

# Health ServiceNow skill

One ServiceNow **read** visit per conversation. This is a **board
visit**: `health/metadata-servicenow.json` carries the last-known row
per in-scope ticket (`current[]`), `series[]`, `visits[]`. The board
is the prior; do not open the prior stamp. No moved ticket = **quiet
visit**: board only, no stamp.

If they ask for a different health check, or to file/update a ticket:
reply `That's not what I do.` and stop.

`references/query.md` is the whole visit: read the board,
`inventory/prod.json`, and `inventory/services.json` if present;
build `since` and the scope terms; one `snow_query_table` on
`incident` and one on `change_request` (plus one on `sys_dictionary`
on the baseline to discover the typed columns); build one row per
returned ticket; derive `keys` by the fixed rule; diff against
`current[]`; stamp when something moved.

**Shared instance.** Most tickets are not this lab's. Scope lives in
the query, not in your judgment: the terms are the names of
`prod.json` devices with `agent_access` `true`, metadata `marker`,
and `match_terms`. Nodes with `agent_access` `false` are not terms —
a generic node name matches other tenants' tickets. Do not widen a
query to "see what else is there". Do not classify a wider set
yourself. Do not query by category, caller, or assignment group
alone. Date/time cells: take the stored (`sys_id`) member, it is UTC;
all other cells: `display`.

**Typed columns are the edges.** `device`, `interface`, `ip`,
`service`, `rfc` on a row are copied from the ticket's own columns
(names discovered once and kept in metadata `entity_fields`). They
are the relations; do not also write `relations[]`. A column the
platform lacks is `null` on every row — a capability result, not a
failure.

## Hard boundaries

Only `snow_query_table`, read-only, three calls at most. Never
`snow_find_*`, `snow_get_*`, `snow_create_*`, `snow_update_*`,
catalog, assets, or knowledge. Do not request `description`,
`work_notes`, or `comments`. Do not query `sys_journal_field`,
`cmdb_ci*`, or `sys_user`. Do not read other planes' metadata or
stamps. Do not read `inventory/infra-sot.json`. Do not write
`state/`, `runs/`, `servicenow/`, `state/servicenow.json`,
`inventory/`, `trend-analysis.json`, `remediation-request.json`,
`state/network-sync.json`, other `health/<source>/` directories, or
`health-board.md`. Do not invent files, ticket numbers, hostnames,
or a marker. Unavailable collection: counts **null**, never `0`.
Tickets never set `status`; it is `ok` or `unknown`. Do not write
under `automations/schedules/`. Do **not** call `execute_command`.
Do not write scripts. Do not stamp `expires_at`. Do not emit
recommendations or a cause.

## Files

Paths and catalog: **`workspace-handoff`**. Write from the schemas.
Do not run a validator. Persist with `write_file` on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-servicenow.json` | metadata | Board. **Every** visit. `marker`, `match_terms`, `lookback_days`, `entity_fields`, `current[]`, `series[]`, `visits[]`. **Not** five-field. |
| `health/servicenow/<stamp>.json` | observation | Only when a row moved, on the first visit, or coverage ≠ complete. Never overwrite. Required `metrics`, `threads`, `unchanged`, `baseline_ref`, `vs_prior` (structured `changed[]`). |

Use exactly: `references/watch.md`, `references/query.md`,
`references/metadata.md`, `references/workspace-contract.md`,
`schemas/health-servicenow-check.schema.json`,
`schemas/health-metadata-servicenow.schema.json`,
`examples/health-check-servicenow.example.json`,
`examples/health-check-unavailable.example.json`,
`examples/health-metadata-servicenow.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**Visit — first tools:** `read_file` `health/metadata-servicenow.json`
(the board), then `inventory/prod.json`, then
`inventory/services.json` if it exists. Do not open the prior stamp.
Never overwrite a timestamped file.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machine

If `servicenow.marker` is missing: set it from `inventory/prod.json`
`lab_title`, else `source.name`. Do not ask. If `entity_fields` is
missing: call D once and write it. Both marker strings missing:
write `unavailable` and stop.

READ_BOARD → READ_PROD → READ_SERVICES → RESOLVE_IF_NEEDED → [D] → I
→ C → BUILD → DIFF → DECIDE → [WRITE_STAMP → READ_BACK → PRUNE] →
WRITE_BOARD → STOP

On I failing twice: still write the check (`unavailable`, null
counts, `threads []`); do not advance `last_collected_at`. On C
failing twice with I good: `partial`, incident rows only.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Since, scope, queries, rows, keys, diff, board, reply: `references/query.md`
- Marker and entity-field discovery: `references/metadata.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
