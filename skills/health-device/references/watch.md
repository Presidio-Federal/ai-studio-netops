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
reference per device with a non-zero metric or an ACL mismatch
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
4. Collect (`references/iosxe.md`): three GETs per device in scope.
   Build this visit's rows (interface, bgp, acl).
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
     material field moved (interfaces: the device's `last-change`).
   - `series[]` ← append **one estate row** (sums over collected
     devices, `scope` `estate`); keep the last 10.
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
`access.restconf.port`. Follow `references/iosxe.md`: interfaces-oper,
BGP address-families, acl-oper on every device in scope. No CDP, no
LLDP, no platform call on a health visit. ACL is a capability probe:
204 / 404 / empty is an answer (`acls` 0, no acl rows), not a failure.
Do not GET config interface trees or the unkeyed BGP neighbor list.

Board rows are admin-up physical, sub-, and Tunnel interfaces only —
never `Loopback*`, `Vlan*`, `Null*`, or admin-down — plus every BGP
neighbor and every ACL the device returned.

Plane `degraded` when admin-up/oper-not-ready (non-idle), BGP not
`fsm-established`, or errors/discards/flaps increased on a board
interface. Zero ACLs never degrade.

The first visit writes a reading for every board row; that stamp
becomes `baseline_visit_id`. Later stamps carry only rows that moved
or are abnormal, plus `unchanged` for the rest. Headline names the
subject, field, and prior → current — not "interfaces checked".

`metrics` one row per collected device `scope` `device:<name>`.
Keys: `oper_not_ready`, `bgp_not_established`, `in_errors`,
`in_discards`, `num_flaps`, `acls`. Null when that device was not
collected. `concerns` one row per device whose metrics are non-zero
(`acls` does not count) or with an ACL mismatch, same `name` as that
`prod.json` device.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 20 |
| IOS-XE `iosxe_restconf_get` | 30 |

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
