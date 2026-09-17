---
name: health-servicenow
version: "1.6.0"
description: "v1.6.0 — Read-only ServiceNow health visit for this lab’s tickets. Write the lab slip and metadata. Use when the invoke names the ServiceNow health check. Do not file or update tickets."
---

# Health ServiceNow skill

One ServiceNow **read** visit per conversation. Find/get in-scope
incidents and changes. Do not create or update records. Do not call
other health MCPs.

Write `health/servicenow/<stamp>.json`. Update
`health/metadata-servicenow.json` when the marker or `last_visit_id`
changes. Do not write `state/`. Do not read other planes. You
interpret this source vs its last stamp (`servicenow.last_visit_id`).

If they ask for a different health check, or to file/update a ticket:
reply `That's not what I do.` and stop.

## Hard boundaries

Read only: `snow_find_incidents`, `snow_get_incident`,
`snow_find_changes`, `snow_get_change`. `snow_query_table` only when
find returns empty or unusable. Never `snow_create_*`,
`snow_update_*`, catalog, assets, or knowledge. Do not write `runs/`,
`servicenow/`, `state/servicenow.json`, `inventory/`,
`trend-analysis.json`, `remediation-request.json`,
`state/network-sync.json`, other `health/<source>/` directories, or
`health-board.md`. Do not invent files. Do not invent ticket numbers
or hostnames. Do not invent a demo marker. Unavailable collection:
counts **null**, never `0`. Do not write under
`automations/schedules/`. Do **not** call `execute_command`. Do not
write scripts. Do not stamp `expires_at`. Do not emit
recommendations.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. Write from the schemas. Do not
run a validator. Persist with `write_file` on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-servicenow.json` | metadata | Marker and match terms. **Not** five-field. |
| `health/servicenow/<stamp>.json` | observation | Plane `status`/`headline`. Never overwrite. Required `metrics` and `vs_prior`. |

Use exactly: `references/watch.md`, `references/query.md`,
`references/demo-scope.md`, `references/metadata.md`,
`references/workspace-contract.md`,
`schemas/health-servicenow-check.schema.json`,
`schemas/health-metadata-servicenow.schema.json`,
`examples/health-check-servicenow.example.json`,
`examples/health-check-unavailable.example.json`,
`examples/health-metadata-servicenow.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**Visit — first tools:** `read_file`
`health/metadata-servicenow.json` if it exists. If
`servicenow.last_visit_id` is set, then that stamp under
`health/servicenow/`. Then `inventory/prod.json` before any
ServiceNow call. Never overwrite a timestamped file.

## State machine

If `servicenow.marker` is missing: RESOLVE_MARKER → (ask if
needed) → then the visit, or STOP if still missing.

Named visit with marker: READ_METADATA → READ_PRIOR_STAMP → READ_PROD
→ PICK_STAMP → COLLECT → WRITE_CHECK → READ_BACK → WRITE_METADATA →
READ_BACK → STOP

On collection failure: still write that check (`unavailable`, null
counts). Do not advance metadata last-visit.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Query: `references/query.md`
- Demo scope: `references/demo-scope.md`
- Marker: `references/metadata.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
