---
name: health-servicenow
version: "2.1.0"
description: "v2.1.0 — Health ServiceNow nurse: visit_servicenow.py collects scoped tickets; board every visit, stamp only on change; no relations[]."
---

# Health ServiceNow skill

One ServiceNow **read** visit per conversation. This is a **board
visit**: `health/metadata-servicenow.json` carries the last-known row
per in-scope ticket (`current[]`), `series[]`, `visits[]`. The board
is the prior; do not open the prior stamp. No moved ticket = **quiet
visit**: board only, no stamp.

If they ask for a different health check, or to file/update a ticket:
reply `That's not what I do.` and stop.

Run `scripts/visit_servicenow.py collect` (see `references/watch.md`).
The script reads the board, `inventory/prod.json`, and
`inventory/services.json` if present; builds `since` and the scope
terms; one `snow_query_table` on `incident` and one on
`change_request` (plus one on `sys_dictionary` when `entity_fields`
is missing); builds one row per returned ticket; derives `keys` by
the fixed rule; diffs against `current[]`; stamps when something
moved. The model sees the summary line, then `annotate` under
`standard` only when that line has `needs_note`.

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

Only `snow_query_table`, read-only, three calls at most, and only
from `scripts/visit_servicenow.py`. Never `snow_find_*`,
`snow_get_*`, `snow_create_*`, `snow_update_*`, catalog, assets, or
knowledge. Do not request `description`, `work_notes`, or
`comments`. Do not query `sys_journal_field`, `cmdb_ci*`, or
`sys_user`. Do not read other planes' metadata or stamps. Do not
read `inventory/infra-sot.json`. Do not write `state/`, `runs/`,
`servicenow/`, `state/servicenow.json`, `inventory/`,
`trend-analysis.json`, `remediation-request.json`,
`state/network-sync.json`, other `health/<source>/` directories, or
`health-board.md`. Do not invent files, ticket numbers, hostnames,
or a marker. Unavailable collection: counts **null**, never `0`.
Tickets never set `status`; it is `ok` or `unknown`. Do not write
under `automations/schedules/`. Call `execute_command` only to run
`scripts/visit_servicenow.py`. Do not write scripts. Do not stamp
`expires_at`. Do not emit recommendations or a cause.

## Files

Paths and catalog: **`workspace-handoff`**. The script validates and
writes the board and the stamp. On the manual fallback, persist with
`write_file` on catalog paths. Do not run a validator yourself.

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

**Visit — first tool:** `read_file` `inventory/prod.json` to confirm
the workspace is there. Then one `execute_command`,
`execution_type: "mcp_orchestration"`, the collect command in
`references/watch.md`. If the summary `needs_note` is non-empty, one
`annotate` command under `execution_type: "standard"`. Reply from the
summary line. If stderr says `hai_mcp unavailable`, follow the manual
order in `references/watch.md`. Do not open the prior stamp. Never
overwrite a timestamped file.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machine

If `servicenow.marker` is missing: set it from `inventory/prod.json`
`lab_title`, else `source.name`. Do not ask. If `entity_fields` is
missing: call D once and write it. Both marker strings missing:
write `unavailable` and stop.

READ_PROD → COLLECT_SCRIPT → [ANNOTATE] → STOP. Manual fallback, only
when hai_mcp is unavailable: READ_BOARD → READ_PROD → READ_SERVICES →
RESOLVE_IF_NEEDED → [D] → I → C → BUILD → DIFF → DECIDE →
[WRITE_STAMP → READ_BACK → PRUNE] → WRITE_BOARD → STOP

On I failing twice: still write the check (`unavailable`, null
counts, `threads []`); do not advance `last_collected_at`. On C
failing twice with I good: `partial`, incident rows only.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Since, scope, queries, rows, keys, diff, board, reply: `references/query.md`
- Marker and entity-field discovery: `references/metadata.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
