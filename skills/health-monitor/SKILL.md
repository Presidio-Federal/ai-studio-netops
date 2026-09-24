---
name: health-monitor
version: "1.35.0"
description: "v1.35.0 — One named Splunk or ThousandEyes health visit. Splunk: two fixed searches, a board on health/metadata-splunk.json (last state per device/kind/subject), stamp only when a material syslog event (BGP, link, config, reload, ACL log, failed auth) arrived; hosts resolved through prod.json and topology-observed.json. ThousandEyes unchanged this version."
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

**Splunk.** `references/splunk.md` is the whole visit: read the board
(`health/metadata-splunk.json` `splunk.current[]`), `prod.json`, and
`topology-observed.json` if present; run S1 and S2 exactly as
printed (S0 first on the baseline); resolve hosts; every S2 row is a
reading and a `changed[]` item; no S2 rows = **quiet visit** (board
only, watermark advanced, no stamp). The board carries `current[]`,
`series[]`, `visits[]`, the watermark. Do not open the prior stamp.
Do not write SPL of your own.

**ThousandEyes.** Write `health/thousandeyes/<stamp>.json` as a **lab
slip**: `headline`, `coverage`, `metrics`, `vs_prior`. Interpret vs
the last stamp (`metadata.last_visit_id`).

Both: do not dump the MCP result. Do not write `state/`.

## Hard boundaries

Do not search Splunk `index=*`. Do not `stats` by `severity` or
`log_level`. Only the SPL `references/splunk.md` prints — no
sampling raw events, no extra searches. Do not read
`inventory/infra-sot.json`. Do not build dashboards. Do not use
`te_raw_api_call`.
A later ThousandEyes visit does not use a 24h window. The first
ThousandEyes visit uses `7d`. Do not write `runs/`, `inventory/`, `state/`,
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
| `health/metadata-splunk.json` | metadata | Board. **Every** Splunk visit, quiet or not. Lookup, watermark, `current[]`, `series[]`, `visits[]`. **Not** five-field. |
| `health/metadata-thousandeyes.json` | metadata | TE visit. **Not** five-field. |
| `health/splunk/<stamp>.json` | observation | Only when S2 returned rows, on the first visit, or coverage ≠ complete. Never overwrite. Required `metrics`, `readings`, `unchanged`, `baseline_ref`, `vs_prior` (structured `changed[]`). |
| `health/thousandeyes/<stamp>.json` | observation | Never overwrite. Required `metrics` and `vs_prior`. |

Use exactly: `references/watch.md`, `references/splunk.md`,
`references/demo-scope.md`, `references/workspace-contract.md`,
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
then `inventory/topology-observed.json` if it exists. Do not open the
prior stamp.

**Named ThousandEyes — first tool:** `read_file`
`health/metadata-thousandeyes.json`. If `last_visit_id` is set, then
that stamp under `health/thousandeyes/`.

Never overwrite a timestamped file.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machine

If the invoke does not name Splunk or ThousandEyes: ASK_WHICH → STOP.

Splunk: READ_BOARD → READ_PROD → READ_TOPOLOGY → RESOLVE_IF_NEEDED →
[S0] → S1 → S2 → RESOLVE_HOSTS → DIFF → DECIDE → [WRITE_STAMP →
READ_BACK → PRUNE] → WRITE_BOARD → STOP

ThousandEyes: READ_THIS_METADATA → READ_PRIOR_STAMP →
RESOLVE_IF_NEEDED → PICK_STAMP → COLLECT → WRITE_CHECK → READ_BACK →
WRITE_METADATA → READ_BACK → STOP

On collection failure: still write that check (`unavailable`, null
counts). Do not advance the Splunk watermark.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Splunk searches, resolve, diff, board: `references/splunk.md`
- Resolve ids / Splunk watermark: `references/metadata.md`
- ThousandEyes extract: `references/demo-scope.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
