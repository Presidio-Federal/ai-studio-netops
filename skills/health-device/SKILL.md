---
name: health-device
version: "1.10.0"
description: "v1.10.0 — IOS-XE device visits, GET-only RESTCONF. Health mode diffs against the board on health/metadata-iosxe.json and writes a stamp only when something material moved. Topology mode maps observed cabling, versions, and interfaces to inventory/topology-observed.json. No CDP on health visits; no counters on topology maps."
---

# Health Device skill

One IOS-XE visit per conversation, in one of two modes. Tools are
`iosxe_restconf_get` and (topology mode only) `iosxe_get_platform_and_yang`
with no YANG arguments, both with `port` from `inventory/prod.json`. Do
not load `cisco-iosxe-mcp` write or YANG-discovery workflows. Do not
call other health MCPs.

| Task line names | Mode | Reference | Writes |
|-----------------|------|-----------|--------|
| network device / IOS-XE health check | health | `references/watch.md`, `references/iosxe.md` | `health/metadata-iosxe.json` every visit; `health/iosxe/<stamp>.json` only when material |
| network topology map | topology | `references/topology.md` | `inventory/topology-observed.json` |

`Scope: device:<a> device:<b>` on either task line limits the visit to
those `prod.json` devices. No scope → every RESTCONF device, ranked.

**Health.** The **board** `health/metadata-iosxe.json` carries
`current[]` (last-known state of every admin-up interface, BGP
neighbor, and ACL), `series[]` (one estate row per visit), `visits[]`,
`last_collected_at`, `last_visit_id`, `baseline_visit_id`. Diff this
collection against `current[]`. Write a stamp only when there is no
board, something material moved, or coverage is not complete. Do not
GET CDP or LLDP on a health visit; far-end context comes from
`inventory/topology-observed.json` when it exists.

**Topology.** Version, interface list with addresses, and CDP/LLDP
neighbors per device. One file, overwritten, with a `changes[]` ring
of what moved since the prior map. Neighbors not in `prod.json` go on
`unresolved[]` without a key.

Both: do not write `state/`. Do not read other planes. Do not list
`health/iosxe/` to find a prior stamp. Rank and resolve names from
`prod.json` only. Never put a port or host in any written file.

If they ask for a different health check: reply `That's not what I
do.` and stop.

## Hard boundaries

GET only — never PUT/PATCH/DELETE, SSH, save-config. Never
`iosxe_get_platform_and_yang` on a health visit; on a topology map,
never with `yang_model` or `list_modules`. Do not write `runs/`,
`inventory/prod.json`, `inventory/infra-sot.json`,
`trend-analysis.json`, `remediation-request.json`,
`state/network-sync.json`, `health/metadata.json`, any metadata file
except `health/metadata-iosxe.json`, other `health/<source>/`
directories, or `health-board.md`. Do not invent files. Do not invent
measurements. Unavailable collection: counts **null**, never `0`. Do
not write under `automations/schedules/`. Do **not** call
`execute_command`. Do not write scripts. Do not stamp `expires_at`. Do
not emit recommendations. Do not write `relations[]`; edges are the
`peer` column and `links[]`.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. Write from the schemas. Do not
run a validator. Persist with `write_file` on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-iosxe.json` | metadata | Board. Every health visit. No port, no host. |
| `health/iosxe/<stamp>.json` | observation | Plane `status`/`headline`. Never overwrite. Required `metrics`, `readings` (moved/abnormal rows; first visit all), `unchanged`, `baseline_ref`, `vs_prior` (structured `changed[]`). Optional `concerns[]`. |
| `inventory/topology-observed.json` | snapshot | Envelope. `devices[]` `links[]` `unresolved[]` `changes[]`. Overwrite. |

Use exactly: `references/watch.md`, `references/iosxe.md`,
`references/topology.md`, `references/workspace-contract.md`,
`schemas/health-iosxe-check.schema.json`,
`schemas/health-metadata-iosxe.schema.json`,
`schemas/topology-iosxe.schema.json`,
`examples/health-check-iosxe.example.json`,
`examples/health-check-unavailable.example.json`,
`examples/health-metadata-iosxe.example.json`,
`examples/topology-observed.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**Health visit — first tools:** `read_file` `inventory/prod.json`
before any RESTCONF. Then `inventory/topology-observed.json` if it
exists. Then `health/metadata-iosxe.json` if it exists; its
`iosxe.current[]` is what you diff against. Do not open the prior
stamp unless the board has no `current[]`. Three GETs per device in
scope (interfaces, BGP, ACL probe). Decide stamp or quiet. Write the
stamp if due and read it back. Rewrite the board.

**Topology map — first tools:** `read_file` `inventory/prod.json`,
then `inventory/topology-observed.json` if it exists (prior map).
Per device in scope: platform call, interfaces GET, CDP GET (LLDP
once on 204). Write the file and read it back.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. An interface key is always `interface:<device>/<interface>`. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machines

Health: READ_PROD → READ_TOPOLOGY → READ_BOARD → COLLECT → DIFF → DECIDE → [WRITE_CHECK → READ_BACK → PRUNE] → WRITE_BOARD → STOP

Topology: READ_PROD → READ_PRIOR_MAP → COLLECT → DIFF → WRITE_MAP → READ_BACK → STOP

On collection failure: health still writes the check (`unavailable`,
null facts) and the board (prior rows kept); topology writes `gaps`
with the prior rows for the failed device.

## Reference routing

- Health visit steps, budget, reply: `references/watch.md`
- Health GETs, field mapping, what is material: `references/iosxe.md`
- Topology map: `references/topology.md`
- Paths; when to write: `workspace-handoff`; `references/workspace-contract.md`
