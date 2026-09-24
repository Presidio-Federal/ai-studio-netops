---
name: health-monitor
version: "1.36.1"
description: "v1.36.1 — One named Splunk or ThousandEyes health visit; both are board visits. Splunk: two fixed searches grouped by device in Splunk, -7d baseline, board written before the stamp, stamp only on a material syslog event. ThousandEyes: one network-results call per metadata test, board on health/metadata-thousandeyes.json (one row per test + agent with src/dst device), stamp only when state, loss, latency, or error rounds moved; agents resolved to devices through topology-observed.json."
---

# Health Monitor skill

One telemetry source per conversation. The invoke must name Splunk or
ThousandEyes. If it does not, ask which check and stop. Do not pick a
default.

Named Splunk → `splunk_search` (and listing only to resolve). Named
ThousandEyes → `te_get_test_results` / `te_list_alerts`
(`te_agents_get_agents` on the baseline). Do not call the other
source on this visit. Do not call other health MCPs.

If they ask for a different health check: reply `That's not what I
do.` and stop.

Both planes are **board visits**. The metadata file carries
`current[]` (last-known rows), `series[]`, `visits[]`. The board is
the prior; do not open the prior stamp. No material change = **quiet
visit**: board only, no stamp.

**Splunk.** `references/splunk.md` is the whole visit: read the board
(`health/metadata-splunk.json`), `prod.json`, and
`topology-observed.json` if present; run S1 and S2 exactly as
printed (baseline window `-7d`); Splunk already groups by device —
you only look up the `prod.json` spelling; write the board, then
the stamp; every S2 row is a reading and a `changed[]` item. Do not
write SPL of your own.

**ThousandEyes.** `references/thousandeyes.md` is the whole visit:
read the board (`health/metadata-thousandeyes.json`) and
`topology-observed.json` if present; one `te_get_test_results`
(`result_type="network"`, metadata `window`) per metadata test, one
per message; one `te_list_alerts`; build one row per test + agent
(`state` from the fixed rule; `src_device` / `dst_device` from agent
IP and `serverIp` through topology cidr); diff against
`current[]` — only `state`, a 10-point loss move, a 20 ms latency
move, error rounds appearing, or a new row are material.

Both: do not dump the MCP result. Do not write `state/`.

## Hard boundaries

Do not search Splunk `index=*`. Do not `stats` by `severity` or
`log_level`. Only the SPL `references/splunk.md` prints — no
sampling raw events, no extra searches. Do not read
`inventory/infra-sot.json`. Do not build dashboards. Do not use
`te_raw_api_call`. No path-vis, no `te_get_alert`. ThousandEyes
window is always the metadata `window`; never `7d` or `24h`. Do not
write `runs/`, `inventory/`, `state/`, `trend-analysis.json`,
`remediation-request.json`, `state/network-sync.json`, other
`health/<source>/` directories, or `health-board.md`. Do not invent
files. Do not invent measurements. Unavailable collection:
counts/loss **null**, never `0`. Do not write under
`automations/schedules/`. Do **not** call `execute_command`. Do not
write scripts. Do not stamp `expires_at`. Do not emit
recommendations.

## Files

Paths and catalog: **`workspace-handoff`**. Persist with `write_file`
on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-splunk.json` | metadata | Board. **Every** Splunk visit. Lookup, watermark, `current[]`, `series[]`, `visits[]`. **Not** five-field. |
| `health/metadata-thousandeyes.json` | metadata | Board. **Every** ThousandEyes visit. Lookup, `window`, `tests[]`, `agents[]`, `current[]`, `series[]`, `visits[]`. **Not** five-field. |
| `health/splunk/<stamp>.json` | observation | Only when S2 returned rows, on the first visit, or coverage ≠ complete. Never overwrite. |
| `health/thousandeyes/<stamp>.json` | observation | Only when a row moved materially, on the first visit, or coverage ≠ complete. Never overwrite. |

Both stamps require `metrics`, `readings`, `unchanged`,
`baseline_ref`, `vs_prior` (structured `changed[]`).

Use exactly: `references/watch.md`, `references/splunk.md`,
`references/thousandeyes.md`, `references/workspace-contract.md`,
`references/metadata.md`.
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

**Named Splunk — first tools:** `read_file`
`health/metadata-splunk.json` (the board), then `inventory/prod.json`,
then `inventory/topology-observed.json` if it exists.

**Named ThousandEyes — first tools:** `read_file`
`health/metadata-thousandeyes.json` (the board), then
`inventory/topology-observed.json` if it exists.

Neither opens the prior stamp. Never overwrite a timestamped file.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machine

If the invoke does not name Splunk or ThousandEyes: ASK_WHICH → STOP.

Splunk: READ_BOARD → READ_PROD → READ_TOPOLOGY → RESOLVE_IF_NEEDED →
S1 → S2 → RESOLVE_DEVS → DIFF → WRITE_BOARD → DECIDE → [WRITE_STAMP →
READ_BACK → PRUNE → WRITE_BOARD] → STOP

ThousandEyes: READ_BOARD → READ_TOPOLOGY → RESOLVE_IF_NEEDED →
[AGENTS] → (per test: NETWORK)* → ALERTS → BUILD → DIFF → DECIDE →
[WRITE_STAMP → READ_BACK → PRUNE] → WRITE_BOARD → STOP

On collection failure: still write that check (`unavailable`, null
counts). Do not advance the Splunk watermark.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Splunk searches, resolve, diff, board: `references/splunk.md`
- ThousandEyes calls, row build, diff, board: `references/thousandeyes.md`
- Resolve ids / windows: `references/metadata.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
