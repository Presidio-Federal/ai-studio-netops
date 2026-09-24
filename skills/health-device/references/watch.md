# Network Device health visit

This agent runs the IOS-XE device plane. A schedule line or a chat
that names the network device / IOS-XE health check is authorization.
Do not confirm. Do not call other health MCPs.

A task line that names the **network topology map** is the other mode:
`references/topology.md`, not this file.

If they ask for a different health check: reply only `That's not what
I do.` and stop.

## This plane only

The observation file is **this visit's plane**. Do not write
`state/`. Do not write `consult`. The only metadata write is
`health/metadata-iosxe.json` — the board for this plane. Do not read
other planes. Do not list `health/` except this source directory
**after** a stamp write, to keep 10 stamps.

Envelope `status` is **this visit only**. The diff is against the
board's `iosxe.current[]`, not against the prior stamp. Open the prior
stamp only when the board has no `current[]`; then rebuild the board
from this collection and treat the visit as first.

The observation is a **lab slip**. Required: `headline`, `scope`,
`coverage`, `metrics`, `readings`, `unchanged`, `baseline_ref`,
`vs_prior`. Optional `concerns[]`: one workspace-handoff entity
reference per device that rebooted, is over a cpu/memory threshold,
has unsaved config, or has a non-zero fault metric
(`type` `device`, `name` as `inventory/prod.json` writes it,
`source_ref` `inventory/prod.json`). Omit healthy devices. Cap 8. Do
not invent `id`. The stamp has no `summary`, no `devices[]` tree, no
neighbors, no `relations`.

Observation `headline` quotes measurements: subject, field,
prior → current, since when.

## Shared order

1. `read_file` `inventory/prod.json`. Never `get_folder_structure`.
   Never `automations/schedules/...`. Rank and scope from
   `inventory/prod.json` only — do not open ThousandEyes or Splunk
   files.
2. `read_file` `inventory/topology-observed.json` if it exists (peer
   resolution and far-end context only). Missing is fine.
3. `read_file` `health/metadata-iosxe.json` if it exists. Keep
   `iosxe.current[]`, `series[]`, `visits[]`, `last_visit_id`,
   `baseline_visit_id`. Do not list `health/iosxe/`.
4. Collect (`references/iosxe.md`): five filtered GETs per device in
   scope, **one device at a time, never two ports in one message**.
   Reduce each device to its rows (device, interface, bgp) before
   the next device's calls.
5. Diff rows against `current[]` (`references/iosxe.md`, "what is
   material"). Produce `changed[]`, `delta`, `metrics[]`, `status`,
   `coverage`.
6. **Decide.** Write a stamp when there is no board, or `changed[]`
   is non-empty, or `coverage.state` ≠ `complete`. Otherwise the
   visit is **quiet**: skip step 7.
7. Stamp: pick `YYYY-MM-DDTHH-MM-SSZ` from `checked_at`. If
   `health/iosxe/<stamp>.json` exists, add 1 second. That stamp is
   `watch_id`. Write the lab slip from the check schema, then
   `read_file` it back. Keep **at most 10** stamps under
   `health/iosxe/`: delete oldest first, in that directory only.
   Never overwrite.
8. Write `health/metadata-iosxe.json` from the metadata schema —
   every visit, quiet or not:
   - `current[]` ← this visit's rows for devices in scope; rows for
     out-of-scope or failed devices kept as they were. A board row is
     the reading without `note`. `last_changed` moves only when a
     material field moved (interfaces: the device's `last-change`;
     device rows: `boot-time`).
   - `series[]` ← append **one estate row** (sums over collected
     devices; `cpu_5m_max` / `mem_used_pct_max` are the highest
     device values; `scope` `estate`); keep the last 10.
   - `visits[]` ← append `{watch_id (null when quiet), checked_at,
     status, coverage, delta, stamp_written, scope}`; keep the last
     10.
   - `last_collected_at` ← `checked_at`. `last_visit_id` ← this
     `watch_id` only when a stamp was written. `baseline_visit_id`
     ← this `watch_id` on the first visit, else unchanged.
   - `keys` ← union of keys on `current[]`.
   No port, no host. Persist with `write_file` on catalog paths. Do
   not write `health-board.md`. Do not `execute_command`.

## Collect

Read `inventory/prod.json` before RESTCONF. Pass **`port`** only from
`access.restconf.port`. Follow `references/iosxe.md` exactly: five
filtered GETs per device — system-data, cpu, memory, interfaces, BGP
address-families — every one with its `params={"fields": ...}`. No
CDP, no LLDP, no platform call, no ACL oper, no config trees, no
unkeyed BGP neighbor list on a health visit. BGP 204 / 404 is an
answer (the device runs no BGP), not a failure.

Board rows: one `device` row per collected device; admin-up physical,
sub-, and Tunnel interfaces — never `Loopback*`, `Vlan*`, `Null*`, or
admin-down; every BGP neighbor summary.

Plane `degraded` when a device rebooted since the board, is at
`cpu_5m` ≥ 80 or `mem_used_pct` ≥ 85, has an admin-up/oper-not-ready
(non-idle) interface, BGP not `fsm-established`, or flaps / errors /
CRC errors increased on a board interface. Discards, unsaved config,
and a version change never degrade on their own.

The first visit writes a reading for every board row; that stamp
becomes `baseline_visit_id`. Later stamps carry only rows that moved
or are abnormal, plus `unchanged` for the rest. Headline names the
subject, field, and prior → current — not "interfaces checked".

`metrics` one row per collected device `scope` `device:<name>`.
Keys: `oper_not_ready`, `bgp_not_established`, `num_flaps`,
`in_errors`, `in_discards`, `cpu_5m_max`, `mem_used_pct_max`. Null
when that device was not collected. `concerns` one row per device
that rebooted, is over a threshold, has unsaved config, or has a
non-zero fault metric, same `name` as that `prod.json` device.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 20 |
| IOS-XE `iosxe_restconf_get` | 5 × devices in scope, cap 50 |

If over budget: stop querying, write what you have (`partial`).

Unavailable measurements are `null`, never `0`. Quote measurements in
the check `headline`.

## Reply

Stamp written:
`Visit: iosxe` / `Result: <status>` / `Coverage: <coverage>` /
`Scope: <all | device list>` / `Wrote: health/iosxe/<stamp>.json` /
`Trend: <delta>` / `Findings:` one line per `changed` item or
abnormal row / `Next: none`.

Quiet visit:
`Visit: iosxe` / `Result: <status>` / `Coverage: complete` /
`Scope: <all | device list>` /
`Wrote: health/metadata-iosxe.json (no material change)` /
`Trend: unchanged` / `Board: <n> rows, last stamp <last_visit_id>` /
`Next: none`.
