# Network Device visit

This agent runs the IOS-XE device plane only. A schedule line or a
chat that names the network device / IOS-XE health check is
authorization. Do not confirm. Do not call other health MCPs.

If they ask for a different health check: reply only `That's not what
I do.` and stop.

## This plane only

The observation file is **this visit's plane**. Do not write
`state/`. Do not write `consult`. The only metadata write is
`health/metadata-iosxe.json` — the board for this plane. Do not read
other planes. Do not list `health/` except this source directory
**after** a stamp write, to keep 10 stamps.

Envelope `status` is **this visit only**. The diff is against the
board's `iosxe.current[]`, not against the prior stamp. The prior
stamp is opened only when the board has no `current[]` (a v1
board): then diff its `readings` once and rebuild the board from
this collection.

The observation is a **lab slip**. Required: `headline`, `coverage`,
`metrics`, `readings`, `unchanged`, `baseline_ref`, `vs_prior`.
Optional `concerns[]`: one workspace-handoff entity reference when a
metric on that device is non-zero (`type` `device`, `name` as
`inventory/prod.json` writes it, `source_ref` `inventory/prod.json`).
Omit healthy devices. Cap 8. Do not invent `id`. The stamp has no
`summary` and no `devices[]` tree.

Observation `headline` quotes measurements: subject, field,
prior → current, since when.

## Shared order

1. `read_file` `inventory/prod.json`. Never `get_folder_structure`.
   Never `automations/schedules/...`. Rank from `inventory/prod.json`
   only — do not open ThousandEyes or Splunk files.
2. `read_file` `inventory/infra-sot.json` if it exists (peer
   resolution only). Missing: `peer` is null everywhere.
3. `read_file` `health/metadata-iosxe.json` if it exists. Keep
   `iosxe.current[]`, `series[]`, `visits[]`, `relations[]`,
   `last_visit_id`, `baseline_visit_id`. Do not list `health/iosxe/`.
4. Collect (`references/iosxe.md`): four GETs per ranked device.
   Build this visit's rows (interface, bgp, acl) and edges.
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
   - `current[]` ← this visit's rows. A row for a device that failed
     collection keeps its prior values. `last_changed` moves only
     when a material field moved (interfaces: the device's
     `last-change` when it has one).
   - `series[]` ← append this visit's `metrics[]` rows; when rows
     from more than 10 distinct `at` values are present, drop every
     row of the oldest `at`.
   - `visits[]` ← append `{watch_id (null when quiet), checked_at,
     status (healthy|degraded|unknown), coverage, delta,
     stamp_written}`; keep the last 10.
   - `relations[]` ← every edge this collection saw (rebuilt).
   - `last_collected_at` ← `checked_at`. `last_visit_id` ← this
     `watch_id` only when a stamp was written. `baseline_visit_id`
     ← this `watch_id` on the first visit, else unchanged.
   - `keys` ← union of keys on `current[]` and ends of `relations[]`.
   No port, no host. Persist with `write_file` on catalog paths. Do
   not write `health-board.md`. Do not `execute_command`.

## Collect

Read `inventory/prod.json` before RESTCONF. Pass **`port`** only from
`access.restconf.port`. Follow `references/iosxe.md`: interfaces-oper,
BGP address-families, acl-oper, cdp-neighbor-details on every ranked
device. ACL and CDP are capability probes: 204 / 404 / empty is an
answer (`present: false`, `neighbor` null), not a failure. Do not GET
config interface trees or the unkeyed BGP neighbor list.

Plane `degraded` when admin-up/oper-not-ready (non-idle), BGP not
`fsm-established`, or errors/discards/flaps increased on a ranked up
port. Zero ACLs or no neighbors never degrade.

The first visit writes a reading for every admin-up interface, every
BGP neighbor, and every ACL the GETs returned; that stamp becomes
`baseline_visit_id`. Later stamps carry only rows that moved or are
abnormal, plus `unchanged` for the rest. Headline names the subject,
field, and prior → current — not "interfaces checked".

`metrics` one row per collected device `scope` `device:<name>`.
Keys: `oper_not_ready`, `bgp_not_established`, `in_errors`,
`in_discards`, `num_flaps`, `acls`. Null when that device was not
collected. `concerns` one row per device whose metrics are non-zero
(`acls` does not count), same `name` as that `prod.json` device.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 20 |
| IOS-XE `iosxe_restconf_get` | 40 |

If over budget: stop querying, write what you have (`partial`).

Unavailable measurements are `null`, never `0`. Quote measurements in
the check `headline`.

## Reply

Stamp written:
`Wrote: health/iosxe/<stamp>.json` / `Status: <status>` /
`Trend: <delta>` / `Headline: <headline>`.

Quiet visit:
`Wrote: health/metadata-iosxe.json (no material change)` /
`Status: <status>` / `Trend: unchanged` / `Board: <n> rows,
<m> edges, last stamp <last_visit_id>`.
