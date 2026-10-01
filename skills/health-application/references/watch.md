# Visit procedure

One visit type. If the invoke asks for anything other than the
application health check (Splunk, NetFlow, device, ServiceNow,
config, remediation), reply `That's not what I do.` and stop.

An invoke that names the application check, or a bare invoke from
the Analyzer or a schedule, is authorization. Do not confirm.

Tools: `grafana_prometheus_targets`, `grafana_query_prometheus`,
`grafana_annotations` (list only), `grafana_prometheus_labels`
(baseline). Never `grafana_query_influx`, `grafana_influx_schema`,
`grafana_get_dashboard`, `grafana_search_dashboards`,
`grafana_alerts`, `grafana_annotations(action="create")`,
`splunk_search`, or a device MCP.

## This plane only

The observation is **this plane** (`ok` / `degraded` / `unknown`).
Do not write `state/`. Do not read or write `health/metadata-splunk.json`,
`health/metadata-netflow.json`, or any other board.

A **board visit**: `health/metadata-application.json` carries
`current[]` (one row per probe, container, host, and scrape target),
`annotations[]`, `series[]`, `visits[]`. The board is the prior. A
visit with no material change writes the board only. A stamp is
written on the baseline, when a row moved materially, or when
coverage is not `complete`.

The observation is a **lab slip**, not a Prometheus dump. Required:
`headline`, `coverage`, `metrics`, `readings`, `unchanged`,
`baseline_ref`, `vs_prior` (structured `changed[]`). No `summary`,
`series[]` copies, raw samples, or label maps.

## The visit

Everything is in `references/prometheus.md`: two reads, one target
call, twelve instant expressions copied exactly, one annotation
list, rows built by copying label values into columns, unseen board
rows carried as `gone` / `unreachable`, diff against the board,
board written first, stamp when due.

Order: READ_BOARD → READ_PROD → T → [RESOLVE probe_job] → P1 → P2 →
P3 → P4 → C1 → C2 → C3 → C4 → H1 → H2 → H3 → H4 → A → BUILD →
CARRY → DIFF → WRITE_BOARD → DECIDE → [WRITE_STAMP → READ_BACK →
PRUNE → WRITE_BOARD] → STOP.

`window` is always metadata `application.window` (default `1h`).
`probe_job` is always from metadata. Material means what the table
in `references/prometheus.md` says; a number drifting is not
material. The nurse copies and compares; it does not decide why a
probe failed, whether a restart was planned, or which application a
host "really" serves. `device` is set only when `host_name` matches
`inventory/prod.json`; otherwise the host stays a host.

## Stamps

Stamp `YYYY-MM-DDTHH-MM-SSZ`. If that path exists, add 1 second.
Never overwrite. That stamp is `watch_id`. After a stamp write,
`read_file` it, then keep **at most 10** stamps under
`health/application/` only. Do not list other `health/`
directories. Do not write `health-board.md`. Do not
`execute_command`. Persist with `write_file` on catalog paths.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 6 |
| `grafana_prometheus_targets` | 1 (plus one retry) |
| `grafana_query_prometheus` | 12 (plus one retry each) |
| `grafana_annotations` | 1 |
| `grafana_prometheus_labels` | 4 (baseline only) |

If over budget: stop querying, write what you have with coverage
`partial`. Do not record a kind as empty if you never collected it.

Unavailable measurements are `null`, never `0`. Quote measurements
in the check `headline`.
