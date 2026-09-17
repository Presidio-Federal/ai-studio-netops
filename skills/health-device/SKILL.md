---
name: health-device
version: "1.7.0"
description: "v1.7.0 — IOS-XE device health visit. GET-only RESTCONF. Write a lab slip at health/iosxe/<stamp>.json. Use when the invoke names the network device or IOS-XE health check."
---

# Health Device skill

One IOS-XE GET visit per conversation. Tool is `iosxe_restconf_get`
with `port` from `inventory/prod.json`. Do not load `cisco-iosxe-mcp`
write or YANG-discovery workflows. Do not call other health MCPs.

Write `health/iosxe/<stamp>.json`. Do not write `state/`. Do not
write metadata. Do not read other planes. Do not list `health/iosxe/`.
Trend is `vs_prior` vs the last IOS-XE stamp named on
`state/health.json` `consults.iosxe.source_ref` (no directory list).
If that path is missing: `delta` `first`. Rank from `prod.json` only.

If they ask for a different health check: reply `That's not what I
do.` and stop.

## Hard boundaries

GET only — never PUT/PATCH/DELETE, SSH, save-config, or
`iosxe_get_platform_and_yang`. Do not write `runs/`, `inventory/`,
`trend-analysis.json`, `remediation-request.json`,
`state/network-sync.json`, `health/metadata.json`,
`health/metadata-*.json`, other `health/<source>/` directories, or
`health-board.md`. Do not invent files. Do not invent measurements.
Unavailable collection: counts **null**, never `0`. Do not write
under `automations/schedules/`. Do **not** call `execute_command`. Do
not write scripts. Do not stamp `expires_at`. Do not emit
recommendations.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. Write from the schemas. Do not
run a validator. Persist with `write_file` on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/iosxe/<stamp>.json` | observation | Plane `status`/`headline`. Never overwrite. Required `metrics` and `vs_prior`. |

Use exactly: `references/watch.md`, `references/iosxe.md`,
`references/workspace-contract.md`,
`schemas/health-iosxe-check.schema.json`,
`examples/health-check-iosxe.example.json`,
`examples/health-check-unavailable.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**Visit — first tool:** `read_file` `inventory/prod.json` before any
RESTCONF. If `state/health.json` exists, read it for
`consults.iosxe.source_ref` then that stamp. Read the new observation
back. Never overwrite a timestamped file.

## State machine

READ_PROD → READ_PRIOR_FROM_CHART → PICK_STAMP → COLLECT → WRITE_CHECK → READ_BACK → STOP

On collection failure: still write that check (`unavailable`, null
facts).

## Reference routing

- Visit steps, budget: `references/watch.md`
- IOS-XE GETs + ranking: `references/iosxe.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
