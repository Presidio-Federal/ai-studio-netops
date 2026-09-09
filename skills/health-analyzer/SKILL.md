---
name: health-analyzer
version: "2.2.3"
description: "v2.2.3 — Roll up health visit stamps into state/health.json. Use when analyzing, assessing, charting, or trending production network health. Observation only — no telemetry collect."
---

# Health Analyzer skill

You turn **observations already on disk** into one rollup chart.
You do not collect telemetry. You read
`health/<source>/<stamp>.json` and (Splunk / TE / ServiceNow)
metadata. You write `state/health.json` only.

Output is observation. Quiet vitals are not a pass and are not
ranked improvements. You do not attribute cause.

An analyze / assess / chart / trend invoke is authorization
(`assess-now`). A refresh / wait / then-assess invoke is
`refresh-then-assess`. If they ask you to run a named health check
yourself: reply `That's not what I do.` and stop.

## Hard boundaries

Do not collect telemetry. Do not write anything except
`state/health.json`. Do not invent files. Do not invent
measurements. Do **not** call `execute_command`. Do not write
scripts. Do not write under `automations/schedules/`. Do not `ls`
`health/`.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. Write from the schema. Persist
with `write_file` on the catalog path.

| Path | Kind | Envelope |
|------|------|----------|
| `state/health.json` | state | Five-field. Replace in full. `source_agent` `health-analyzer`. |

Use exactly: `references/analyze.md`,
`references/workspace-contract.md`,
`schemas/health-state.schema.json`,
`examples/health-state.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**First tools:** `read_file` these if they exist —
`health/metadata-thousandeyes.json`, `health/metadata-splunk.json`,
`health/metadata-servicenow.json`, then prior `state/health.json`.
If a metadata `last_visit_id` is set, then that stamp. IOS-XE: use
prior `consults.iosxe.source_ref` if present; do not list
`health/iosxe/`. Do not open other `state/*.json`.

## State machine

READ_METADATA → READ_LATEST_STAMPS → READ_PRIOR_CHART → FOLD_SERIES
→ DISPATCH_STALE (mode, via workspace-handoff) → WRITE_CHART →
READ_BACK → STOP

Missing all latest stamps: status `unknown`, empty series points,
follow workspace-handoff for stale/missing rows, still write the
chart.

## Reference routing

- Freshness, modes, series fold: `references/analyze.md`
- Writers / invoke: `workspace-handoff`
- Produce: `references/workspace-contract.md`
