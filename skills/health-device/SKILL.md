---
name: health-device
version: "1.11.0"
description: "v1.11.0 — IOS-XE device visits, GET-only RESTCONF with fields filters. Health mode: five small GETs per device (boot/version, cpu, memory, interface state, BGP sessions), diffed against the board on health/metadata-iosxe.json; stamp only when something material moved. Topology mode records each device's version, interfaces, and CDP neighbors to inventory/topology-observed.json, one device at a time, file rewritten per device, no cross-device reasoning. One tool, iosxe_restconf_get. No ACL oper, no traffic rates, no CDP on health visits."
---

# Health Device skill

One IOS-XE visit per conversation, in one of two modes. One tool:
`iosxe_restconf_get` with `port` from `inventory/prod.json` and the
`params={"fields": ...}` filter each recipe prints. Do not load
`cisco-iosxe-mcp` write or YANG-discovery workflows. Do not call
`iosxe_get_platform_and_yang` or other health MCPs.

| Task line names | Mode | Reference | Writes |
|-----------------|------|-----------|--------|
| network device / IOS-XE health check | health | `references/watch.md`, `references/iosxe.md` | `health/metadata-iosxe.json` every visit; `health/iosxe/<stamp>.json` only when material |
| network topology map | topology | `references/topology.md` | `inventory/topology-observed.json` |

`Scope: device:<a> device:<b>` on either task line limits the visit to
those `prod.json` devices. No scope → every RESTCONF device, ranked.

**Health.** Five filtered GETs per device — system-data (boot time,
version, reboot reason), cpu, memory, interfaces, BGP summaries —
**one device at a time, never two ports in one message**. The
**board** `health/metadata-iosxe.json` carries `current[]`
(last-known state: one `device` row per device, every admin-up
interface, every BGP neighbor), `series[]` (one estate row per
visit), `visits[]`, `last_collected_at`, `last_visit_id`,
`baseline_visit_id`. Diff this collection against `current[]`. Write
a stamp only when there is no board, something material moved, or
coverage is not complete. Material: a reboot, a state change, flaps
or errors that increased, a cpu/memory threshold crossed, a BGP reset.
Not material: discards, traffic rates, unsaved config. Do not GET CDP,
LLDP, or ACL oper on a health visit; far-end context comes from
`inventory/topology-observed.json` when it exists.

**Topology.** Per device: version, interface names with addresses,
and its CDP/LLDP rows copied into `devices[].neighbors[]`. **One
device at a time, never two ports in one message, rewrite the file
after every device.** You never pair two devices' reports, never read
`description`, never use addresses to decide cabling — a reader pairs
`neighbors[]` rows. A neighbor name not in `prod.json` keeps
`far_name` with `far` null. `changes[]` is a per-device diff against
that device's prior row.

Both: do not write `state/`. Do not read other planes. Do not list
`health/iosxe/` to find a prior stamp. Rank and resolve names from
`prod.json` only. Never put a port or host in any written file.

If they ask for a different health check: reply `That's not what I
do.` and stop.

## Hard boundaries

GET only — never PUT/PATCH/DELETE, SSH, save-config,
`iosxe_get_platform_and_yang`, `yang_model`, or `list_modules`. Only
the paths the references print, each with its `fields` filter — an
unfiltered CPU or interfaces GET is the payload that breaks the
visit. Do not write `runs/`,
`inventory/prod.json`, `inventory/infra-sot.json`,
`trend-analysis.json`, `remediation-request.json`,
`state/network-sync.json`, `health/metadata.json`, any metadata file
except `health/metadata-iosxe.json`, other `health/<source>/`
directories, or `health-board.md`. Do not invent files. Do not invent
measurements. Unavailable collection: counts **null**, never `0`. Do
not write under `automations/schedules/`. Do **not** call
`execute_command`. Do not write scripts. Do not stamp `expires_at`. Do
not emit recommendations. Do not write `relations[]`; edges are the
`peer` column and `neighbors[].far`.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. Write from the schemas. Do not
run a validator. Persist with `write_file` on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-iosxe.json` | metadata | Board. Every health visit. No port, no host. |
| `health/iosxe/<stamp>.json` | observation | Plane `status`/`headline`. Never overwrite. Required `metrics`, `readings` (moved/abnormal rows; first visit all), `unchanged`, `baseline_ref`, `vs_prior` (structured `changed[]`). Optional `concerns[]`. |
| `inventory/topology-observed.json` | snapshot | Envelope. `coverage` `devices[]` (each with `interfaces[]` `neighbors[]`) `changes[]`. Rewritten after every device. |

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
stamp unless the board has no `current[]`. Then, one device at a
time, the five filtered GETs from `references/iosxe.md` (system-data,
cpu, memory=Processor, interfaces, BGP address-families) → reduce to
that device's rows → next device. Decide stamp or quiet. Write the
stamp if due and read it back. Rewrite the board.

**Topology map — first tools:** `read_file` `inventory/prod.json`,
then `inventory/topology-observed.json` if it exists (prior map).
Write the file once as `partial`. Then for each device in scope, in
order, the three filtered GETs from `references/topology.md`
(system-data version → `native/interface` → `cdp-neighbor-details`,
LLDP once on 204) → reduce → `write_file`. Never start the next
device before the file is written. Finish, write, read back.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. An interface key is always `interface:<device>/<interface>`. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machines

Health: READ_PROD → READ_TOPOLOGY → READ_BOARD → (per device: FIVE_GETS → REDUCE)* → DIFF → DECIDE → [WRITE_CHECK → READ_BACK → PRUNE] → WRITE_BOARD → STOP

Topology: READ_PROD → READ_PRIOR_MAP → WRITE_PARTIAL → (per device: VERSION → INTERFACES → NEIGHBORS → REDUCE → DIFF → WRITE_MAP)* → FINISH → WRITE_MAP → READ_BACK → STOP

On collection failure: health still writes the check (`unavailable`,
null facts) and the board (prior rows kept); topology retries a call
once, then lists the device in `coverage.failed`, keeps its prior row,
and moves to the next device.

## Reference routing

- Health visit steps, budget, reply: `references/watch.md`
- Health GETs, field mapping, what is material: `references/iosxe.md`
- Topology map: `references/topology.md`
- Paths; when to write: `workspace-handoff`; `references/workspace-contract.md`
