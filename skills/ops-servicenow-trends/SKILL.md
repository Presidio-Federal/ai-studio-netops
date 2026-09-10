---
name: ops-servicenow-trends
version: "1.0.0"
description: "v1.0.0 — Cluster ServiceNow tickets in metadata scope (EUC/demo or whatever they named). Write servicenow/trends/<stamp>.json. Recommend KB or restaff. Do not mutate records."
---

# Ops ServiceNow Trends skill

One trend visit per conversation. Scope is
`servicenow/metadata-trends.json`. Inventory is engineering
context. You write one new stamp. You do not mutate ServiceNow.

## Hard boundaries

Read: `snow_find_incidents`, `snow_get_incident`,
`snow_find_changes`, `snow_get_change`, `snow_find_knowledge`,
`snow_get_knowledge`, `snow_find_assignment_groups`.
`snow_query_table` only when find is empty or unusable. Never
`snow_create_*`, `snow_update_*`, catalog, or assets. Do not write `health/`, `state/servicenow.json`,
`servicenow/cases/`, `trend-analysis.json`. Do not invent files.
Do not invent ticket numbers. Unavailable: counts **null**, never
`0`. Do **not** call `execute_command`. Do not write scripts.

## Files

Paths: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`.

| Path | Kind |
|------|------|
| `servicenow/metadata-trends.json` | metadata — not the envelope |
| `servicenow/trends/<stamp>.json` | observation — never overwrite |

Use exactly: `references/watch.md`, `references/metadata.md`,
`references/workspace-contract.md`,
`schemas/servicenow-metadata-trends.schema.json`,
`schemas/servicenow-trend.schema.json`,
`examples/servicenow-metadata-trends.example.json`,
`examples/servicenow-trend.example.json`.
Do not search the workspace for them.

**First tools:** `read_file` `servicenow/metadata-trends.json` if
it exists. If `last_visit_id` is set, that stamp. Then
`inventory/prod.json`.

## State machine

Missing scope: RESOLVE → ask if needed → visit or STOP.
Named visit: READ_METADATA → READ_PRIOR → READ_PROD → COLLECT →
CLUSTER → WRITE_STAMP → WRITE_METADATA → STOP

## Reference routing

- Visit: `references/watch.md`
- Scope: `references/metadata.md`
- Paths: `workspace-handoff`
