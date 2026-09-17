---
name: health-monitor
version: "1.30.0"
description: "v1.30.0 — One named Splunk or ThousandEyes health visit. Write that plane’s lab slip (metrics + vs_prior) and metadata. Use when the invoke names Splunk or ThousandEyes. Do not collect the other source."
---

# Health Monitor skill

One telemetry source per conversation. The invoke must name Splunk or
ThousandEyes. If it does not, ask which check and stop. Do not pick a
default.

Named Splunk → `splunk_search` (and listing only to resolve). Named
ThousandEyes → `te_get_test_results` / `te_list_alerts`. Do not call
the other source on this visit. Do not call other health MCPs.

If they ask for a different health check: reply `That's not what I
do.` and stop.

Write `health/<source>/<stamp>.json` as a **lab slip**: `headline`,
`coverage`, `metrics`, `vs_prior`. Do not dump the MCP result.
Do not write `state/`. You interpret this source vs its last stamp
(`metadata.last_visit_id`).

## Hard boundaries

Do not search Splunk `index=*`. Do not `stats` by `severity` or
`log_level`. Do not build dashboards. Do not use `te_raw_api_call` or
24h TE windows. Do not write `runs/`, `inventory/`, `state/`,
`trend-analysis.json`, `remediation-request.json`,
`state/network-sync.json`, other `health/<source>/` directories, or
`health-board.md`. Do not invent files. Do not invent measurements.
Unavailable collection: counts/loss **null**, never `0`. Do not write
under `automations/schedules/`. Do **not** call `execute_command`. Do
not write scripts. Do not stamp `expires_at`. Do not emit
recommendations.

## Files

Paths and catalog: **`workspace-handoff`**. Persist with `write_file`
on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-splunk.json` | metadata | Splunk visit. **Not** five-field. |
| `health/metadata-thousandeyes.json` | metadata | TE visit. **Not** five-field. |
| `health/splunk/<stamp>.json` | observation | Never overwrite. Required `metrics` and `vs_prior`. |
| `health/thousandeyes/<stamp>.json` | observation | Never overwrite. Required `metrics` and `vs_prior`. |

Use exactly: `references/watch.md`, `references/demo-scope.md`,
`references/workspace-contract.md`, `references/metadata.md`.
Splunk: `schemas/health-splunk-check.schema.json`,
`schemas/health-metadata-splunk.schema.json`,
`examples/health-check-splunk.example.json`,
`examples/health-check-unavailable.example.json`,
`examples/health-metadata-splunk.example.json`.
ThousandEyes: `schemas/health-thousandeyes-check.schema.json`,
`schemas/health-metadata-thousandeyes.schema.json`,
`examples/health-check.example.json`,
`examples/health-check-partial.example.json`,
`examples/health-metadata-thousandeyes.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**Named Splunk — first tool:** `read_file`
`health/metadata-splunk.json`. If `last_visit_id` is set, then that
stamp under `health/splunk/`.

**Named ThousandEyes — first tool:** `read_file`
`health/metadata-thousandeyes.json`. If `last_visit_id` is set, then
that stamp under `health/thousandeyes/`.

Never overwrite a timestamped file.

## State machine

If the invoke does not name Splunk or ThousandEyes: ASK_WHICH → STOP.

Named visit: READ_THIS_METADATA → READ_PRIOR_STAMP → RESOLVE_IF_NEEDED
→ PICK_STAMP → COLLECT → WRITE_CHECK → READ_BACK → WRITE_METADATA →
READ_BACK → STOP

On collection failure: still write that check (`unavailable`, null
counts). Do not advance the Splunk watermark.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Resolve / Splunk watermark: `references/metadata.md`
- Extract: `references/demo-scope.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
