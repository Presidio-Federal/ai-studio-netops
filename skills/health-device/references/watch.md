# Network Device visit

This agent runs the IOS-XE device plane only. A schedule line or a
chat that names the network device / IOS-XE health check is
authorization. Do not confirm. Do not call other health MCPs.

If they ask for a different health check: reply only `That's not what
I do.` and stop.

## This plane only

The observation file is **this visit’s plane**. Do not write
`state/`. Do not write `consult`. The only metadata write is
`health/metadata-iosxe.json` (`last_visit_id`, `last_collected_at`).
Do not read other planes. Do not list `health/` except this source
directory **after** a write, to keep 10 stamps.

Envelope `status` is **this visit only**. Required `vs_prior`: if
`health/metadata-iosxe.json` `iosxe.last_visit_id` is set,
`read_file` `health/iosxe/<last_visit_id>.json` and compare; else
`delta` `first`. Reply `Trend:` is `vs_prior.delta`. After the
slip is written, set `last_visit_id` to this visit’s `watch_id`
and `last_collected_at` to `checked_at`. That file has no port
and no host.

The observation is a **lab slip**. Required: `headline`, `coverage`,
`metrics`, `vs_prior`. Optional `concerns[]`: one workspace-handoff
entity reference when a metric on that device is non-zero (`type`
`device`, `name` as `inventory/prod.json` writes it, `source_ref`
`inventory/prod.json`). Omit healthy devices. Cap 8. Do not invent
`id`. Do not open `inventory/infra-sot.json`. The stamp has no
`summary` and no `devices[]` tree.

Observation `headline` quotes measurements.

## Shared order

1. `read_file` `inventory/prod.json`. Never `get_folder_structure`.
   Never `automations/schedules/...`. Rank from `inventory/prod.json`
   only — do not open ThousandEyes or Splunk files.
2. `read_file` `health/metadata-iosxe.json` if it exists. If
   `iosxe.last_visit_id` is set, `read_file`
   `health/iosxe/<last_visit_id>.json` and keep it for `vs_prior`.
   Do not list `health/iosxe/` to find that file.
3. Pick stamp `YYYY-MM-DDTHH-MM-SSZ`. If
   `health/iosxe/<stamp>.json` exists, add 1 second. Never overwrite.
   That stamp is `watch_id` on this observation.
4. Collect (`references/iosxe.md`). Write the lab slip from the
   check schema (`headline`, `coverage`, `metrics`, `readings`,
   `vs_prior`, `concerns`), then `read_file`. First visit: `delta`
   `first`, `changed` []. Later visit: `changed` is the diff of
   `readings` against the prior stamp.
5. Write `health/metadata-iosxe.json`: `last_visit_id` is this
   `watch_id`, `last_collected_at` is `checked_at`. No other keys.
   Keep **at most 10** stamps under `health/iosxe/`. Delete older
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
when nothing is dropping; ACL 204 is zero ACLs, not failure. The first visit writes a reading for every admin-up interface and
every BGP neighbor the GET returned. Do not write empty `readings`
when the GET returned them. Headline names the oper state, BGP
state, errors, and prefixes — not “interfaces checked.”

`metrics` one row per collected device `scope` `device:<name>`.
Keys: `oper_not_ready`, `bgp_not_established`, `in_errors`,
`in_discards`, `num_flaps`. Null when that device was not collected.
`concerns` one row per device whose metrics are non-zero, same
`name` as that `prod.json` device. `metrics.scope` stays
`device:<name>`.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 20 |
| IOS-XE `iosxe_restconf_get` | 16 |

If over budget: stop querying, write what you have.

Unavailable measurements are `null`, never `0`. Quote measurements in
the check `headline`.
