# Network Device visit

This agent runs the IOS-XE device plane only. A schedule line or a
chat that names the network device / IOS-XE health check is
authorization. Do not confirm. Do not call other health MCPs.

If they ask for a different health check: reply only `That's not what
I do.` and stop.

## This plane only

The observation file is **this visit’s plane**. Do not write
`state/`. Do not write `consult`. Do not write metadata. Do not
read other planes. Do not list `health/` except this source
directory **after** a write, to keep 10 stamps.

Envelope `status` is **this visit only**. `trend.vs_prior` in the
reply is `first` (no prior stamp pointer on this plane).

Observation `headline` quotes measurements.

## Shared order

1. `read_file` `inventory/prod.json`. Never `get_folder_structure`.
   Never `automations/schedules/...`. Rank from `inventory/prod.json`
   only — do not open ThousandEyes or Splunk files.
2. Pick stamp `YYYY-MM-DDTHH-MM-SSZ`. If
   `health/iosxe/<stamp>.json` exists, add 1 second. Never overwrite.
   That stamp is `watch_id` on this observation.
3. Collect (`references/iosxe.md`). Write the observation from the
   check schema (including `metrics`), then `read_file`.
4. Keep **at most 10** stamps under `health/iosxe/`. Delete older
   stamp files in that directory only (oldest first). Do not
   overwrite. Do not write `health-board.md`. Do not
   `execute_command`. Persist with `write_file` on catalog paths.

## Collect

Read `inventory/prod.json` before RESTCONF. Pass **`port`** only from
`access.restconf.port`. Follow `references/iosxe.md`. Baseline:
interfaces-oper; BGP AF on wan / routing evidence. ACL GET only when
a ranked up interface is dropping (`in_discards` / `in_errors` /
`out_errors` > 0). Do not GET config interface trees or the unkeyed
BGP neighbor list.

Plane `degraded` when admin-up/oper-not-ready (non-idle), BGP not
`fsm-established`, or errors/flaps on a ranked up port. No ACL GET
when nothing is dropping; ACL 204 is zero ACLs, not failure. Headline
names devices, oper-not-ready, BGP, errors — not “interfaces checked.”

`metrics` one row per collected device `scope` `device:<name>`.
Keys: `oper_not_ready`, `bgp_not_established`, `in_errors`,
`in_discards`, `num_flaps`. Null when that device was not collected.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 20 |
| IOS-XE `iosxe_restconf_get` | 16 |

If over budget: stop querying, write what you have.

Unavailable measurements are `null`, never `0`. Quote measurements in
the check `headline`.
