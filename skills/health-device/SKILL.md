---
name: health-device
version: "1.9.0"
description: "v1.9.0 — IOS-XE device health visit. GET-only RESTCONF. Diffs against the board on health/metadata-iosxe.json; a quiet visit writes the board only. Stamps carry moved/abnormal rows, structured deltas, ACL and CDP probe results, observed edges."
---

# Health Device skill

One IOS-XE GET visit per conversation. Tool is `iosxe_restconf_get`
with `port` from `inventory/prod.json`. Do not load `cisco-iosxe-mcp`
write or YANG-discovery workflows. Do not call other health MCPs.

Every visit rewrites `health/metadata-iosxe.json` — the **board**:
`current[]` (last-known state of every admin-up interface, BGP
neighbor, and ACL), `series[]`, `visits[]`, `relations[]`,
`last_collected_at`, `last_visit_id`, `baseline_visit_id`. Write
`health/iosxe/<stamp>.json` only when there is no board, when
something material moved against `current[]`, or when coverage is
not complete. Do not write `state/`. Do not read other planes. Do
not list `health/iosxe/` to find a prior stamp. Rank from
`prod.json` only. Never put a port or host in the metadata file.

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
recommendations. Do not write `asserted` relations; `observed` only,
from a CDP/LLDP neighbor or a resolved BGP peer.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. Write from the schemas. Do not
run a validator. Persist with `write_file` on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-iosxe.json` | metadata | Board. Every visit. No port, no host. |
| `health/iosxe/<stamp>.json` | observation | Plane `status`/`headline`. Never overwrite. Required `metrics`, `readings` (moved/abnormal rows; first visit all), `unchanged`, `baseline_ref`, `vs_prior` (structured `changed[]`). Optional `relations[]` (new edges), `concerns[]`. |

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
RESTCONF. Then `inventory/infra-sot.json` if it exists (peer
resolution only). Then `health/metadata-iosxe.json` if it exists;
its `iosxe.current[]` is what you diff against. Do not open the
prior stamp unless the board has no `current[]`. Collect four GETs
per ranked device (interfaces, BGP, ACL probe, CDP probe). Decide
stamp or quiet. Write the stamp if due and read it back. Rewrite the
board. Never overwrite a timestamped file.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. An interface key is always `interface:<device>/<interface>`. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machine

READ_PROD → READ_SOT → READ_BOARD → COLLECT → DIFF → DECIDE → [WRITE_CHECK → READ_BACK → PRUNE] → WRITE_BOARD → STOP

On collection failure: still write that check (`unavailable`, null
facts) and the board (prior rows kept).

## Reference routing

- Visit steps, budget, reply: `references/watch.md`
- IOS-XE GETs, field mapping, what is material: `references/iosxe.md`
- Paths; when to write: `workspace-handoff`; `references/workspace-contract.md`
