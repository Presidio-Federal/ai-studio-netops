# NetFlow visit — Elasticsearch

The health check runs `scripts/visit_netflow.py`. This file is the
rules that script implements. Use the manual order below only when
stderr says `hai_mcp unavailable`.

Tools are `elasticsearch_query` and, when F1 returns no rows and the
stream is not operator-pinned, `elasticsearch_list_data_streams`.
`data_stream` and `window` come from `health/metadata-netflow.json`.
Do not put a collector address in this file. Do not create Kibana
rules. Do not call Grafana. Do not read `inventory/infra-sot.json`.

Three ES|QL queries, copied exactly. One call per message. Copy
numbers; do not reason about the platform. A call that fails is
retried once; a second failure is coverage `unavailable` (F1) or
`partial` (F2 or F3).

## Setup (reads, before any Elasticsearch call)

1. `read_file` `health/metadata-netflow.json` — lookup and the
   **board** (`netflow.current[]`, `series[]`, `visits[]`). Missing
   `data_stream` → discover, then continue. A `measurement` that
   does not start with `logs-` or `metrics-` is not a stream.
2. `read_file` `inventory/prod.json` — `devices[].name` and
   `access.*.host`. An exporter `source` or a flow address that
   equals a device's access host resolves to that device.
3. `read_file` `inventory/topology-observed.json` if it exists —
   `devices[].name` + `interfaces[].cidr` resolve an exporter
   `source` or a flow `src` / `dst` to a device. Missing is fine.

Do not open the prior stamp; the board is the prior state.

**Window.** Always `netflow.window` from metadata (default `1h`).
Pass it as `timerange`. The query text uses the same window:
`15m` → `15 minutes`, `1h` → `1 hour`, `1d` → `1 day`. Do not use
`7d` or `24h`. Do not change `window`.

## Calls

Substitute `<measurement>` from `data_stream` and `<window>` from
the mapping above. `timerange` is the board window (`1h`, not
`1 hour`). Each result is `{ok, rows, truncated}`.

**F1 — exporters. Always.** One row per `observer.ip` this window.
`netflow.exporter.address` includes an ephemeral source port. Do
not use it as the exporter identity. `observer.name` is the name
when the stream has one.

`elasticsearch_query(timerange=<board window>, limit=50, query=`
```
FROM <measurement>
| WHERE @timestamp >= NOW() - <window>
| EVAL exporter_name = COALESCE(observer.name, "")
| STATS bytes = SUM(network.bytes), flows = COUNT(*), last_at = MAX(@timestamp) BY observer.ip, exporter_name
| EVAL source = TO_STRING(observer.ip)
| KEEP source, exporter_name, bytes, flows, last_at
| SORT bytes DESC
| LIMIT 50
```
`)`

Row columns: `source`, `exporter_name`, `bytes`, `flows`, `last_at` (RFC3339).

**F2 — paths. Always.** The largest client → server paths this
window, one row per exporter, source name, destination name, and
service. A name is `lab.source.device` or `lab.destination.device`
when the stream has it, otherwise the address. The service is
`lab.destination.service`, else `lab.destination.application`, else
the destination port. Telemetry toward the collectors (NetFlow
2055, syslog 1514, sFlow 6343) and reverse flows toward ephemeral
ports (≥ 32768) are excluded **in the query**. This is not one
row per flow and not one row per ephemeral port.

`elasticsearch_query(timerange=<board window>, limit=50, query=`
```
FROM <measurement>
| WHERE @timestamp >= NOW() - <window>
  AND network.transport IN ("tcp", "udp")
  AND destination.port > 0 AND destination.port < 32768
  AND destination.port != 2055 AND destination.port != 1514 AND destination.port != 6343
| EVAL exporter_name = COALESCE(observer.name, ""), src_name = COALESCE(lab.source.device, TO_STRING(source.ip)), dst_name = COALESCE(lab.destination.device, TO_STRING(destination.ip)), service = COALESCE(lab.destination.service, lab.destination.application, TO_STRING(destination.port))
| STATS bytes = SUM(network.bytes), flows = COUNT(*), last_at = MAX(@timestamp) BY observer.ip, exporter_name, src_name, dst_name, service, network.transport
| EVAL source = TO_STRING(observer.ip), src = src_name, dst = dst_name, dst_port = service, protocol = network.transport
| KEEP source, exporter_name, src, dst, dst_port, protocol, bytes, flows, last_at
| SORT bytes DESC
| LIMIT 40
```
`)`

**F3 — firewall denies. Always, on the same stream.** Cisco NSEL
`netflow.firewall_event` value `3` is denied. Created, deleted, and
update events are not rows. Zero rows is a quiet result.

`elasticsearch_query(timerange=<board window>, limit=50, query=`
```
FROM <measurement>
| WHERE @timestamp >= NOW() - <window> AND netflow.firewall_event == 3
| EVAL exporter_name = COALESCE(observer.name, ""), src_name = COALESCE(lab.source.device, TO_STRING(source.ip)), dst_name = COALESCE(lab.destination.device, TO_STRING(destination.ip))
| STATS flows = COUNT(*) BY observer.ip, exporter_name, src_name, dst_name, destination.port, network.transport
| EVAL event = "denied", source = TO_STRING(observer.ip), src = src_name, dst = dst_name, dst_port = TO_STRING(destination.port), protocol = network.transport
| KEEP source, exporter_name, src, dst, dst_port, protocol, event, flows
| SORT flows DESC
| LIMIT 40
```
`)`

**F4 — port spread. Always, on the same stream.** One row per
exporter, source name, and destination name when that pair used
at least 20 destination ports this window. Ports at or above
32768 are the return path of a normal session and are not counted.
Ports are not folded
into a service name. A port scan is many ports and few bytes, so
it does not have to win the F2 byte sort. `dst_port` in the result
is the distinct port count. The script stores `protocol` `scan`.

`elasticsearch_query(timerange=<board window>, limit=30, query=`
```
FROM <measurement>
| WHERE @timestamp >= NOW() - <window>
  AND network.transport IN ("tcp", "udp")
  AND destination.port > 0 AND destination.port < 32768
| EVAL exporter_name = COALESCE(observer.name, ""), src_name = COALESCE(lab.source.device, TO_STRING(source.ip)), dst_name = COALESCE(lab.destination.device, TO_STRING(destination.ip))
| STATS flows = COUNT(*), bytes = SUM(network.bytes), ports = COUNT_DISTINCT(destination.port), last_at = MAX(@timestamp) BY observer.ip, exporter_name, src_name, dst_name
| WHERE ports >= 20
| SORT ports DESC
| LIMIT 20
| EVAL source = TO_STRING(observer.ip), src = src_name, dst = dst_name, dst_port = TO_STRING(ports), protocol = "scan"
| KEEP source, exporter_name, src, dst, dst_port, protocol, bytes, flows, last_at
```
`)`

Nothing else. No per-flow drill-down,
no host-metric stream, no syslog stream. `logs-system.syslog-default`
on this cluster is the collector host, not the firewalls. Device
syslog stays on the Splunk nurse.

## Empty F1 — check the stream before anything goes silent

F1 `ok` with **zero rows** means every exporter stopped at once, or
`data_stream` no longer points at the flow data. Check the lookup
before a single row is carried `silent`.

1. `elasticsearch_list_data_streams()`.
2. Keep names that start with `logs-` and contain `netflow`.
3. Run F1 on each. First candidate with rows → write `data_stream`
   and `measurement` to that name, `bucket` `elasticsearch`,
   `provenance.netflow` `discovered`, run F2 and F3, finish.
   Coverage `detail` starts with `stream moved: <old> -> <new>`.
   When `provenance.netflow` is `user`, do not write and do not
   search: ask and stop.
4. No candidate returns rows → `unavailable`. Null estate row,
   `readings` `[]`, board rows untouched. No exporter becomes
   `silent`.

```text
Need: data_stream
Tried: <data_stream> (empty)
Which data stream holds the NetFlow data now?
```

## Operator correction

A reply that names a data stream, or says the data is wrong:

- **Names a stream** → F1 against it. Rows → write it,
  `provenance.netflow` `user`, finish. Empty → one line with what
  you ran, ask again.
- **"Wrong data", nothing named** → the lookup check, then the ask.
- **"The stream is right"** → zero F1 rows are real: carry every
  board exporter `silent`, plane `degraded`.

A `user` value is replaced only by the operator.

## Resolve an address

Fresh evidence is an exact interface address (the address before `/`
in a topology cidr), an access host, or a name equal to a
`prod.json` device. An address that only falls inside a subnet is
not that device.

One fresh device → `identity` `resolved` and `device` set. More than
one, or a stored device that is not in the fresh set, or an address
listed in `identity_review` → `identity` `conflicted`, `device` null.
A stored name with no fresh evidence → `identity` `unverified`,
`device` null.

`src` and `dst` stay endpoints. `src_gateway` and `dst_gateway` are
set only on an exact interface or access-host match.

## Build the rows

**Exporter row** (kind `exporter`) — one per F1 row. `source` is
`observer.ip`. `exporter_name` is the F1 name when it is non-empty,
else the name the board already stored. `exporter_site` stays as
the board stored it. `state` `reporting`. Keys:
`device:<device>` when resolved; `site:<exporter_site>` when that
site is set; else `[]`.

A board exporter whose `source` has **no** F1 row is carried
`silent`, bytes 0, flows 0, `last_flow_at` kept. When F1 returned
zero rows in total, carry nothing until the lookup check or the
operator says the stream is right.

**Conversation row** (kind `conversation`) — one per F2 path.
`src` and `dst` are the names from F2. `dst_port` is the service
token from F2, which may be a service name rather than a port.
`scope` is `flow:<source>/<src>><dst>:<dst_port>/<protocol>`.
`state` `present`. A board path missing from this query is carried
`not_in_top_n`. That is not absence, not a stamp, and not a worse
delta. A new path is traffic. It is a stamp only when its flow
count is a bunch for the window (20 in 15m, 40 in 1h, 200 in 1d).

**Firewall row** (kind `firewall`) — one per F3 row. `event` is
`denied`. `state` `present`. A board deny missing from F3 is
carried `absent`.

`bytes_per_s` is bytes divided by the window. A 4× byte move counts
only when both rows use the same window and both rates are above
zero. A 4× flow move counts only when both rows use the same window
and the larger count is a bunch for that window. A steady path is
not a finding. A surge is the finding, and the note says to
research that path. It is not a forwarding failure.

Estate `bytes` and `flows` come from the reporting exporter with the
largest byte total (`observation_source`). Matching five-tuples are
not summed.

Silence is not a forwarding failure. Referrals: Devices for exporter
configuration and send statistics; Collector monitoring for receipt,
templates, and decode; Inventory for a conflicted address.

Rows carry no `application:` key. Do not name an application from a
port number.

## Diff against the board

Match rows to `netflow.current[]` by `scope`.

| Kind | Material when | `changed[].field` |
|------|---------------|-------------------|
| exporter | `state` differs (`reporting` ↔ `silent`) | `state` |
| exporter | scope not on the board | `row` |
| exporter | `identity` differs | `identity` |
| conversation | protocol `scan`: new, or flows or port count at least 2× | `flows` |
| conversation | `present` ↔ `absent` only. `present` ↔ `not_in_top_n` is not material | `state` |
| conversation | scope not on the board, and `flows` is a bunch for the window | `row` |
| conversation | same window, both `bytes_per_s` > 0, and the rate ≥ 4× or ≤ ¼ | `bytes_per_s` |
| conversation | same window, both `flows` > 0, the count ≥ 4× or ≤ ¼, and the larger count is a bunch | `flows` |
| firewall | `state` differs (`present` ↔ `absent`) | `state` |
| firewall | scope not on the board, and `flows` is a bunch for the window | `row` |
| firewall | same window, deny count ≥ 4× or ≤ ¼, and the larger count is a bunch | `flows` |

A path that merely leaves the top query is not a reading.
`not_in_top_n` is not worse. **Delta.** `first` on the baseline.
`worse` when any exporter went `silent`, a deny count surged, or a
port spread is new or at least twice the prior window.
`better` when something returned and nothing is worse. `changed`
when a path surged or a loud new path appeared. `unchanged` when
none.

## Stamp or quiet

- Baseline: stamp; `delta` `first`; `changed` `[]`. Readings are
  the reporting exporters and the five largest paths. Every note
  is `Baseline.` The other paths stay on the board and are
  `unchanged`. Do not copy every F2 row into the stamp.
- A later visit: stamp when a row in the table above moved, or
  coverage is not `complete`. The note on a surge names the path
  and says to research it. Do not paste flow records.
- Otherwise quiet: board only.

Plane `status`: `degraded` when any exporter is `silent`, a deny
count surged, or any port spread is in the window; `unknown` when
F1 failed or the lookup is suspect; else `ok`. A deny that matches
the board does not degrade the plane. A byte surge on one service
does not degrade the plane. A port spread does. Coverage:
`complete` when F1, F2, and F3 returned; `partial` when F1 returned
and F2 or F3 failed; `unavailable` when F1 failed.

## Reply

Stamp written:

```text
Visit: netflow
Result: <ok | degraded | unknown>
Coverage: <complete|partial|unavailable>
Window: <window> (<window_start> -> <window_end>)
Wrote: health/netflow/<stamp>.json
Trend: <delta>
Collection: <the summary collection line>
Traffic: <the summary traffic line>
Scans: <the summary scans line>
Referrals: <the summary referrals, or none>
Next: none
```

Quiet:

```text
Visit: netflow
Result: <ok | degraded>
Coverage: complete
Wrote: health/metadata-netflow.json (no material change)
Trend: unchanged
Board: <the summary board line>
Next: none
```
