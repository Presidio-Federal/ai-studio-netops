---
name: ops-servicenow-trends
version: "1.1.0"
description: "v1.1.0 — Nightly/on-demand ServiceNow trend scan. Scope from servicenow/metadata-trends.json. Write servicenow/trends/<stamp>.json. Recommend KB when close_notes agree. Do not mutate records."
---

# Ops ServiceNow Trends skill

One scan per conversation. Scope is
`servicenow/metadata-trends.json`. You write one new stamp.
You do not mutate ServiceNow.

## Hard boundaries

Read: `snow_find_incidents`, `snow_get_incident`,
`snow_find_changes`, `snow_get_change`, `snow_find_knowledge`,
`snow_get_knowledge`, `snow_find_assignment_groups`.
`snow_query_table` only when find is empty or unusable. Never
`snow_create_*`, `snow_update_*`, catalog, or assets. Do not
write `health/`, `state/servicenow.json`, `servicenow/cases/`,
`trends.json`, or `trend-analysis.json`. Do not invent files
or ticket numbers. Unavailable: counts **null**, never `0`.
Do **not** call `execute_command`. Do not write scripts.

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
`inventory/prod.json` if it exists.

## State machine

Missing scope: RESOLVE → ask if needed → scan or STOP.
Named scan: READ_METADATA → READ_PRIOR → COLLECT → CLUSTER →
WRITE_STAMP → WRITE_METADATA → STOP

## Reference routing

- Scan: `references/watch.md`
- Scope: `references/metadata.md`
- Paths: `workspace-handoff`
