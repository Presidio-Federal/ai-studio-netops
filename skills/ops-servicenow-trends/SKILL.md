---
name: ops-servicenow-trends
version: "1.2.0"
description: "v1.2.0 — One ServiceNow trend visit. Write servicenow/trends/<stamp>.json then metadata. Use when a schedule or chat names the trends scan. Do not mutate records."
---

# Ops ServiceNow Trends skill

One scan per conversation. A schedule line or a chat that
names trends is authorization. Write one new stamp. Do not
mutate ServiceNow.

Write `servicenow/trends/<stamp>.json`. Update
`servicenow/metadata-trends.json` when scope or
`last_visit_id` changes. Do not write `state/`. Do not list
`servicenow/trends/` to find a prior stamp.

If they ask for a health visit or to mutate a ticket or KB:
reply `That's not what I do.` and stop.

## Hard boundaries

Read: `snow_find_incidents`, `snow_get_incident`,
`snow_find_changes`, `snow_get_change`, `snow_find_knowledge`,
`snow_get_knowledge`, `snow_find_assignment_groups`.
`snow_query_table` only when find is empty or unusable. Never
`snow_create_*`, `snow_update_*`, catalog, or assets. Do not
write `health/`, `state/servicenow.json`, `servicenow/cases/`,
`trends.json`, `trend-analysis.json`, or `health-board.md`.
Do not invent files or ticket numbers. Unavailable: counts
**null**, never `0`. Do not write under
`automations/schedules/`. Do **not** call `execute_command`.
Do not write scripts.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. Write from the schemas.
Do not run a validator. Persist with `write_file` on catalog
paths.

| Path | Kind | Envelope |
|------|------|----------|
| `servicenow/metadata-trends.json` | metadata | Scope and last-visit. **Not** five-field. |
| `servicenow/trends/<stamp>.json` | observation | Never overwrite. Required `metrics`. |

Use exactly: `references/watch.md`, `references/metadata.md`,
`references/workspace-contract.md`,
`schemas/servicenow-metadata-trends.schema.json`,
`schemas/servicenow-trend.schema.json`,
`examples/servicenow-metadata-trends.example.json`,
`examples/servicenow-trend.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**Visit — first tool:** `read_file`
`servicenow/metadata-trends.json` if it exists. If
`last_visit_id` is set, then
`servicenow/trends/<last_visit_id>.json`. Then
`inventory/prod.json` if it exists. Never overwrite a
timestamped file.

## State machine

Named / schedule visit: READ_METADATA → READ_PRIOR_STAMP →
RESOLVE_IF_NEEDED → PICK_STAMP → COLLECT → WRITE_CHECK →
READ_BACK → WRITE_METADATA → READ_BACK → STOP

On collection failure: still write that check
(`unavailable`, null counts). Do not advance
`last_visit_id`.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Scope: `references/metadata.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
