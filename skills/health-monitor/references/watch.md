# Named visit procedure

If the invoke does not name Splunk or NetFlow, ask which and stop.
Do not default. Do not collect.

```text
Which check: Splunk or NetFlow?
```

A line that names Splunk or NetFlow is authorization to run that
visit. Do not confirm.

If they ask for a different health check: reply `That's not what I
do.` and stop.

Splunk visit: `splunk_search`. Do not call Grafana or other health
MCPs. NetFlow visit: `grafana_query_influx` (and
`grafana_influx_schema` on the baseline or for an unknown
exporter). Do not call Splunk, `grafana_query_prometheus`, or
other health MCPs.

## This plane only

The observation file is **this visit’s plane** (`ok` / `degraded` /
`unknown`). Do not write `state/`. Do not read or write another
plane.

Both planes are **board visits**: the metadata file carries the
last-known state (`current[]`), `series[]`, `visits[]`. The board is
the prior; do not open the prior stamp. A visit with no material
change writes the board only. A stamp is written on the baseline,
when something material moved, or when coverage is not `complete`.

The observation is a **lab slip**, not a MCP dump. Required:
`headline`, `coverage`, `metrics`, `readings`, `unchanged`,
`baseline_ref`, `vs_prior` (structured `changed[]`). No `summary`,
`series[]` copies, `samples`, `top_hosts`, raw flow records, or
buckets.

Required `metrics` on the observation: same keys every visit;
explicit `null` when not collected.

## Splunk visit

Everything is in `references/splunk.md`: three reads, two searches
grouped by device in Splunk, a spelling lookup per device, diff
against the board on `health/metadata-splunk.json`, board written
first, stamp when due. Baseline window `-7d`.

Order: READ_BOARD → READ_PROD → READ_TOPOLOGY → S1 → S2 → RESOLVE →
DIFF → WRITE_BOARD → DECIDE → [WRITE_STAMP → READ_BACK → PRUNE →
WRITE_BOARD] → STOP.

A window with no S2 rows is **quiet**. A failed S1 is
`unavailable`: null counts, watermark **not** advanced, stamp
written. SSH NO_MATCH and successful auth are counts, never
readings.

## NetFlow visit

Everything is in `references/netflow.md`: three reads, two Flux
queries already aggregated per exporter and per conversation, an
address-to-device lookup, one row per exporter and per
conversation, unseen board rows carried as `silent` / `absent`,
diff against the board on `health/metadata-netflow.json`, board
written first, stamp when due.

Order: READ_BOARD → READ_PROD → READ_TOPOLOGY → [SCHEMA] → F1 → F2 →
RESOLVE → BUILD → CARRY → DIFF → WRITE_BOARD → DECIDE →
[WRITE_STAMP → READ_BACK → PRUNE → WRITE_BOARD] → STOP.

`timerange` is always `netflow.window` from metadata (default
`1h`); no `7d`, no `24h`. State per row is the fixed rule
(`reporting` / `silent` for an exporter, `present` / `absent` for a
conversation). Only a state flip, a new row, or a bytes move by 4×
is material. A failed F1 is `unavailable`: null counts, stamp
written, board rows untouched. A failed F2 with F1 good is
`partial`: conversation rows kept as they were.

## Stamps

Stamp `YYYY-MM-DDTHH-MM-SSZ`. If that path exists, add 1 second.
Never overwrite. That stamp is `watch_id`. After a stamp write,
`read_file` it, then keep **at most 10** stamps under this source's
directory only (delete oldest first). Do not list other `health/`
directories. Do not write `health-board.md`. Do not
`execute_command`. Persist with `write_file` on catalog paths.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 12 |
| Splunk collection (`splunk_search`) | 2 (plus one retry each) |
| Splunk listing (resolve only) | 2 |
| NetFlow `grafana_query_influx` | 2 (plus one retry each) |
| NetFlow `grafana_influx_schema` | 2 (baseline / unknown exporter only) |

If over budget: stop querying, write what you have. Do not record a
source as empty if you never collected it.

Unavailable measurements are `null`, never `0`. Quote measurements
in the check `headline`.
