# NetFlow visit — flow board

The health check runs `scripts/visit_netflow.py`. This file is the
rules that script implements. Use the manual order below only when
stderr says `hai_mcp unavailable`.

Tools are `grafana_query_influx` and, on the baseline or when a
`source` is not in `exporters[]`, `grafana_influx_schema`. `bucket`,
`measurement`, `window`, `exporters[]` come from
`health/metadata-netflow.json`. Do not put a datasource uid, a
collector address, or an exporter name in this file. Do not create
dashboards. Do not call `grafana_query_prometheus` on this visit.
Do not read `inventory/infra-sot.json`.

Two Flux queries, copied exactly. One call per message. Copy
numbers; do not reason about the platform. A call that fails is
retried once; a second failure is coverage `unavailable` (F1) or
`partial` (F2).

## Setup (reads, before any Grafana call)

1. `read_file` `health/metadata-netflow.json` — lookup and the
   **board** (`netflow.current[]`, `series[]`, `visits[]`). Missing
   `bucket`, `measurement`, or `exporters[]` → `references/metadata.md`
   (resolve), write metadata, then continue.
2. `read_file` `inventory/prod.json` — `devices[].name` and
   `access.*.host`; an exporter `source` or a flow address that equals
   a device's access host resolves to that device.
3. `read_file` `inventory/topology-observed.json` if it exists —
   `devices[].name` + `interfaces[].cidr` resolve an exporter `source`
   or a flow `src` / `dst` to a device. Missing is fine: then only
   `exporters[].device` and exact access-host matches resolve.

Do not open the prior stamp; the board is the prior state.

**Window.** Always `netflow.window` from metadata (default `1h`).
Pass it as the tool's `timerange`. Same window every visit, first or
later. Do not use `7d` or `24h`. Do not change `window`.

## Calls

Substitute `<bucket>` and `<measurement>` from metadata. Every
query keeps `range(start: v.timeRangeStart, stop: v.timeRangeStop)`;
the tool fills it from `timerange`. Each result is one `series[]`
entry whose `rows[]` are the table rows; a `truncated` flag means
the table was cut at the tool's row cap.

**F1 — exporters. Always.** One row per exporter address this
window. This is the `exporter` row, the `metrics` row, and the
`series[]` row.

`grafana_query_influx(timerange=<window>, query=`
```
from(bucket: "<bucket>")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "<measurement>" and r._field == "in_bytes")
  |> group(columns: ["source", "exporter_name", "exporter_site"])
  |> reduce(fn: (r, accumulator) => ({bytes: accumulator.bytes + r._value, flows: accumulator.flows + 1, last_at: if r._time > accumulator.last_at then r._time else accumulator.last_at}), identity: {bytes: 0, flows: 0, last_at: 1970-01-01T00:00:00Z})
  |> map(fn: (r) => ({r with last_at: string(v: r.last_at)}))
  |> group()
```
`)`

Row columns: `source`, `exporter_name`, `exporter_site`, `bytes`,
`flows`, `last_at` (RFC3339).

**F2 — conversations. Always.** The 40 largest client → server
conversations this window, per exporter. Telemetry toward the
collectors (NetFlow 2055, syslog 1514, sFlow 6343) and reverse
flows toward ephemeral ports (≥ 32768) are excluded **in the
query**; do not add them back.

`grafana_query_influx(timerange=<window>, query=`
```
from(bucket: "<bucket>")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "<measurement>" and r._field == "in_bytes")
  |> filter(fn: (r) => exists r.src and exists r.dst and exists r.dst_port and exists r.protocol)
  |> filter(fn: (r) => (r.protocol == "tcp" or r.protocol == "udp") and r.dst_port != "2055" and r.dst_port != "1514" and r.dst_port != "6343" and int(v: r.dst_port) < 32768)
  |> group(columns: ["source", "exporter_name", "src", "dst", "dst_port", "protocol"])
  |> reduce(fn: (r, accumulator) => ({bytes: accumulator.bytes + r._value, flows: accumulator.flows + 1, last_at: if r._time > accumulator.last_at then r._time else accumulator.last_at}), identity: {bytes: 0, flows: 0, last_at: 1970-01-01T00:00:00Z})
  |> map(fn: (r) => ({r with last_at: string(v: r.last_at)}))
  |> group()
  |> sort(columns: ["bytes"], desc: true)
  |> limit(n: 40)
```
`)`

Row columns: `source`, `exporter_name`, `src`, `dst`, `dst_port`,
`protocol`, `bytes`, `flows`, `last_at`.

**S — schema (baseline, or when an F1 `source` is not in
`exporters[]`).** `grafana_influx_schema(bucket=<bucket>,
measurement=<measurement>, tag="exporter_name")` and once more with
`tag="source"`. Write every `source` to `exporters[]` with its
`exporter_name` from the F1 row (`unmapped` is a value, keep it) and
`device` resolved below. Never list schema otherwise.

Nothing else. No third query, no `app_id` follow-up, no per-flow
drill-down, no dashboards.

## Empty F1 — check the lookup before anything goes silent

F1 `ok` with **zero rows** means every exporter stopped at once, or
`bucket` / `measurement` / datasource no longer point at the flow
data. The second is the likelier one. Check the lookup before a
single row is carried `silent`. Do not run F1 again with the same
arguments; it returns the same empty result.

1. `grafana_list_datasources()`. Each `influxdb` `uid`. The
   datasource `database` is only that source's default bucket, so
   it is not the candidate list.
2. `grafana_query_influx` with `buckets() |> keep(columns: ["name"])`.
   The tool rejects a query whose text has no `range(`, so the query
   also carries a comment that contains `range(start: v.timeRangeStart, stop: v.timeRangeStop)`.
   Drop names that start with `_`.
3. Per bucket, `grafana_influx_schema(bucket=<b>, datasource_uid=<uid>)`,
   then tag keys for each measurement. Keep a measurement only when
   the tag keys include `source`, `src`, `dst`, `dst_port`, and
   `protocol`. Run F1 there. Do not assume a measurement name.
4. First candidate whose F1 returns rows → the lookup moved. Write
   `bucket`, `measurement`, and `datasource_uid` to metadata,
   `provenance.netflow` `discovered`, run F2 there, finish the visit.
   Coverage `detail` and the headline start with
   `bucket moved: <old> -> <new>`. When `provenance.netflow` is
   `user`, do not write and do not search: ask and stop.
5. No candidate returns rows → the lookup is **suspect**.
   `unavailable` path (null estate row, `readings` `[]`, board rows
   untouched — no exporter becomes `silent`). Coverage `detail`:
   `F1 empty; tried <bucket>/<measurement>; no other bucket returned rows`.
   Reply with the ask and stop. No human (schedule): same, stop.

```text
Need: bucket
Tried: <bucket>/<measurement> (empty)<, candidate (empty)>
Which bucket holds the NetFlow data now?
```

A baseline with zero F1 rows follows the same steps.

## Operator correction

The operator's word on where the data is beats metadata. The invoke
or a reply that names a bucket, measurement, or datasource, or says
you are looking at the wrong data:

- **Names a value** → one `grafana_influx_schema(bucket=<named>)`
  (`measurement=<m>` too when named) to confirm it, then F1 against
  it. Rows → write it, `provenance.netflow` `user`, finish the
  visit. Empty → one line with what you ran, ask again. Do not fall
  back to the old value.
- **"Wrong data", nothing named** → the lookup check above if not
  already run in this conversation, then the `Need: bucket` ask.
  Do not re-run the old query. Do not defend the empty result.
- **"The bucket is right"** → zero F1 rows are real: carry every
  board exporter `silent`, plane `degraded`.

A `user` value is replaced only by the operator.

## Resolve an address to a device

For an exporter `source`, a flow `src`, or a flow `dst`, in this
order; stop at the first hit:

1. `exporters[]` row with this `source` and a non-null `device` →
   that device (exporters only).
2. `exporter_name` equals a `prod.json` `devices[].name`
   case-insensitively → that name (exporters only).
3. The address equals the address part of any
   `topology-observed.json` `devices[].interfaces[].cidr`, or falls
   inside that cidr → that device's name.
4. The address equals `access.restconf.host` or `access.ssh.host`
   on a `prod.json` device → that name.
5. No match → null. Do not guess. `unmapped` and `unknown` are not
   device names.

Write the `prod.json` spelling.

## Build the rows

**Exporter row** (kind `exporter`) — one per F1 row.

| Column | From |
|--------|------|
| `kind` | `exporter` |
| `scope` | `exporter:<source>` |
| `source` `exporter_name` `exporter_site` | F1 |
| `device` | resolved, or null |
| `bytes` `flows` | F1 |
| `last_flow_at` | F1 `last_at` |
| `at` | `checked_at` |
| `state` | `reporting` |
| `keys` | `device:<device>` when resolved; `site:<exporter_site>` when `exporter_site` is not `unknown` and not null; else `[]` |

A board exporter row whose `source` has **no** F1 row this window
is carried with `state` `silent`, `bytes` 0, `flows` 0,
`last_flow_at` kept, `at` `checked_at`. When F1 returned zero rows
in total, carry nothing until the lookup check (above) or the
operator says the bucket is right.

**Conversation row** (kind `conversation`) — one per F2 row.

| Column | From |
|--------|------|
| `kind` | `conversation` |
| `scope` | `flow:<source>/<src>>` + `<dst>:<dst_port>/<protocol>` (e.g. `flow:10.0.0.1/10.1.1.5>10.2.2.9:443/tcp`) |
| `source` `exporter_name` `src` `dst` `dst_port` `protocol` | F2 |
| `exporter` | the exporter row's `device` for this `source`, or null |
| `src_device` `dst_device` | resolved from `src` / `dst`, or null |
| `bytes` `flows` | F2 |
| `last_seen_at` | F2 `last_at` |
| `at` | `checked_at` |
| `state` | `present` |
| `keys` | `device:<exporter>`, `device:<src_device>`, `device:<dst_device>` when resolved (deduplicated); `[]` when none |

A board conversation row with **no** F2 row this window is carried
with `state` `absent`, `bytes` 0, `flows` 0, `last_seen_at` kept.
Drop an `absent` row once `last_seen_at` is older than 7 days.

Rows carry no `application:` key yet; when
`inventory/applications.json` exists a later reader joins `dst` to
it. Do not name an application from a port number.

## Diff against the board

Match rows to `netflow.current[]` by `scope`. Only these move a row
onto the stamp:

| Kind | Material when | `changed[].field` |
|------|---------------|-------------------|
| exporter | `state` differs (`reporting` ↔ `silent`) | `state` |
| exporter | scope not on the board | `row` |
| conversation | `state` differs (`present` ↔ `absent`) | `state` |
| conversation | scope not on the board | `row` |
| conversation | both `bytes` > 0 and this `bytes` ≥ 4 × board `bytes` or ≤ board `bytes` / 4 | `bytes` |

Not material: `flows`, `last_*`, `at`, an exporter's byte count
(collectors dominate it), a bytes move under the factor. Those land
on the board only.

`changed[]` item: `{keys, field, prior, current, at}` — `prior` from
the board row (null when new), `current` from this row, `at` the
row's `at`, `keys` the row's `keys`.

**Delta.** `first` on the baseline. `worse` when any exporter went
`silent` or a conversation whose `dst_device` or `src_device`
resolved went `absent`. `better` when items exist and none is worse
and at least one is a return (`silent` → `reporting`, `absent` →
`present`). `changed` for anything else (new rows, byte moves,
unresolved conversations vanishing). `unchanged` when none.

## Stamp or quiet

- Baseline (no `baseline_visit_id`): stamp; every row is a reading;
  `delta` `first`; **`changed` `[]`**; `unchanged` 0;
  `prior_watch_id` null.
- `changed[]` non-empty, or coverage not `complete`: stamp; readings
  = the rows that moved.
- Otherwise **quiet**: no stamp. Board only.

Plane `status`: `degraded` when any exporter row is `silent`;
`unknown` when F1 failed or the lookup is suspect; else `ok`.
Conversations do not vote plane status. Coverage: `complete` when
F1 and F2 returned; `partial` when F1 returned and F2 failed
(conversation rows kept from the board, `at` unchanged);
`unavailable` when F1 failed or the lookup is suspect
(stamp with a single all-null estate metric row, `readings` `[]`,
board rows untouched, `last_collected_at` still advanced).

## Write

**Stamp** (schema `health-netflow-check`). Top-level fields, these
names and no others:

```json
{
  "keys": [], "schema": "health-netflow-check/v1", "source": "netflow",
  "watch_id": "<YYYY-MM-DDTHH-MM-SSZ>", "checked_at": "<ISO Z>", "ok": true,
  "status": "ok|degraded|unknown", "headline": "...",
  "window": "1h", "window_start": "<checked_at minus window>", "window_end": "<checked_at>",
  "coverage": { "state": "complete|partial|unavailable", "detail": "..." },
  "metrics": [ { "at": "...", "scope": "estate", "exporters": 5, "exporters_silent": 0, "exporters_unresolved": 3,
                 "flows": 5592, "bytes": 10281000000, "conversations": 40, "conversations_absent": 0, "top_scope": "flow:..." } ],
  "readings": [ { "...row columns...", "note": "..." } ],
  "unchanged": 0, "baseline_ref": null,
  "vs_prior": { "prior_watch_id": null, "delta": "first", "changed": [] },
  "concerns": [ { "type": "device", "name": "<device>" } ]
}
```

`metrics` = one `estate` row: `exporters` (F1 rows), `exporters_silent`
(board exporters with no F1 row), `exporters_unresolved` (F1 rows
with `device` null), `flows` and `bytes` summed over F1,
`conversations` (F2 rows), `conversations_absent`, `top_scope` (the
largest F2 row's scope). `readings` = moved rows + `note`.
`unchanged` = board rows not replaced. `baseline_ref` =
`health/netflow/<baseline_visit_id>.json` (null on the baseline).
`headline`: which exporters report and which are silent, the top
conversation by name (devices, not addresses, when resolved), what
appeared or vanished. `concerns`: one `{type: device, name}` per
silent exporter that resolved to a device.

`note` is one or two sentences about **this row against its board
row**: silent since when, returned after how long, new pair or a
pair that vanished, bytes up or down by how much. Not the columns
again. Do not name an application, a cause, or a device that is not
`exporter`, `src_device`, or `dst_device`. On the baseline the note
is `Baseline.` unless the row is a silent exporter.

**Board** (schema `health-metadata-netflow`) — every visit:
- `current[]` ← built rows replace rows with the same `scope`;
  carried rows (`silent`, `absent`) keep their scope; cap 120 (drop
  `absent` rows oldest `last_seen_at` first).
- `series[]` ← append the estate metric row; keep 10.
- `visits[]` ← append `{watch_id (null when quiet), checked_at,
  status, coverage, delta, stamp_written, window}`; keep 10.
- `exporters[]` ← rewritten only when S ran (new `source`) or a
  `device` resolved this visit that was null before.
- `last_collected_at` ← `checked_at`. `last_visit_id` ← this
  `watch_id` only when a stamp was written. `baseline_visit_id` ←
  this `watch_id` on the first visit.
- `keys` ← union of keys on `current[]`.

Write the board as soon as the rows exist, then the stamp (when
due), `read_file` it, prune to 10 stamps in `health/netflow/` only,
then rewrite the board with `last_visit_id`.

## Budget

| Item | Max |
|------|----:|
| Workspace reads | 3 |
| Workspace writes | 4 (board, stamp, prune, board) |
| `grafana_query_influx` | 2 (plus one retry each); +2 F1 for the lookup check or an operator value |
| `grafana_influx_schema` | 2 (baseline / unknown source only); +2 for the lookup check or an operator value |
| `grafana_list_datasources` | 1 (lookup check only) |

## Reply

Stamp written:

```text
Visit: netflow
Result: <ok | degraded | unknown>
Coverage: <complete|partial|unavailable>
Window: <window> (<window_start> -> <window_end>)
Wrote: health/netflow/<stamp>.json
Trend: <delta>
Findings:
- exporter <device or source>: <reporting|silent>, <flows> flows, last flow <last_flow_at>
- <src_device or src> -> <dst_device or dst>:<dst_port>/<protocol> via <exporter or source>: <present|absent>, <bytes> B
Next: none
```

Quiet:

```text
Visit: netflow
Result: <ok | degraded>
Coverage: complete
Window: <window> (<window_start> -> <window_end>)
Wrote: health/metadata-netflow.json (no material change)
Trend: unchanged
Board: <n> exporters (<k> silent), <m> conversations, last stamp <last_visit_id>
Next: none
```
