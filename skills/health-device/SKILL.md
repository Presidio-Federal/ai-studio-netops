---
name: health-device
version: "1.8.0"
description: "v1.8.0 — IOS-XE device health visit. GET-only RESTCONF. Write a lab slip at health/iosxe/<stamp>.json and last_visit_id on health/metadata-iosxe.json. Use when the invoke names the network device or IOS-XE health check."
---

# Health Device skill

One IOS-XE GET visit per conversation. Tool is `iosxe_restconf_get`
with `port` from `inventory/prod.json`. Do not load `cisco-iosxe-mcp`
write or YANG-discovery workflows. Do not call other health MCPs.

Write `health/iosxe/<stamp>.json`. Write
`health/metadata-iosxe.json` with `last_visit_id` and
`last_collected_at` only. Do not write `state/`. Do not read other
planes. Do not list `health/iosxe/` to find a prior stamp. Trend is
`vs_prior` vs `health/iosxe/<last_visit_id>.json`. If that id is
missing: `delta` `first`. Rank from `prod.json` only. Never put a
port or host in the metadata file.

If they ask for a different health check: reply `That's not what I
do.` and stop.

## Hard boundaries

GET only — never PUT/PATCH/DELETE, SSH, save-config, or
`iosxe_get_platform_and_yang`. Do not write `runs/`, `inventory/`,
`trend-analysis.json`, `remediation-request.json`,
`state/network-sync.json`, `health/metadata.json`,
any metadata file except `health/metadata-iosxe.json`, other
`health/<source>/` directories, or
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
| `health/metadata-iosxe.json` | metadata | `last_visit_id` and `last_collected_at` only. No port, no host. |
| `health/iosxe/<stamp>.json` | observation | Plane `status`/`headline`. Never overwrite. Required `metrics` and `vs_prior`. Optional `concerns[]`: one device entity-ref when a metric on that device is non-zero. |

Use exactly: `references/watch.md`, `references/iosxe.md`,
`references/workspace-contract.md`,
`schemas/health-iosxe-check.schema.json`,
`schemas/health-metadata-iosxe.schema.json`,
`examples/health-check-iosxe.example.json`,
`examples/health-check-unavailable.example.json`,
`examples/health-metadata-iosxe.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**Visit — first tools:** `read_file` `inventory/prod.json` before any
RESTCONF. Then `health/metadata-iosxe.json` if it exists. If
`iosxe.last_visit_id` is set, `read_file`
`health/iosxe/<last_visit_id>.json` and compare. Read the new
observation back. Then write `last_visit_id` to this visit’s
`watch_id`. Never overwrite a timestamped file. Never write a port
or host into metadata.

## State machine

READ_PROD → READ_METADATA → READ_PRIOR_STAMP → PICK_STAMP → COLLECT → WRITE_CHECK → READ_BACK → WRITE_METADATA → STOP

On collection failure: still write that check (`unavailable`, null
facts).

## Reference routing

- Visit steps, budget: `references/watch.md`
- IOS-XE GETs + ranking: `references/iosxe.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
