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
not use it as the exporter identity.

`elasticsearch_query(timerange=<board window>, limit=50, query=`
```
FROM <measurement>
| WHERE @timestamp >= NOW() - <window>
| STATS bytes = SUM(network.bytes), flows = COUNT(*), last_at = MAX(@timestamp) BY observer.ip
| EVAL source = TO_STRING(observer.ip)
| KEEP source, bytes, flows, last_at
| SORT bytes DESC
| LIMIT 50
```
`)`

Row columns: `source`, `bytes`, `flows`, `last_at` (RFC3339).

**F2 — conversations. Always.** The 40 largest client → server
conversations this window, per exporter. Telemetry toward the
collectors (NetFlow 2055, syslog 1514, sFlow 6343) and reverse
flows toward ephemeral ports (≥ 32768) are excluded **in the
query**.

`elasticsearch_query(timerange=<board window>, limit=50, query=`
```
FROM <measurement>
| WHERE @timestamp >= NOW() - <window>
  AND network.transport IN ("tcp", "udp")
  AND destination.port > 0 AND destination.port < 32768
  AND destination.port != 2055 AND destination.port != 1514 AND destination.port != 6343
| STATS bytes = SUM(network.bytes), flows = COUNT(*), last_at = MAX(@timestamp) BY observer.ip, source.ip, destination.ip, destination.port, network.transport
| EVAL source = TO_STRING(observer.ip), src = TO_STRING(source.ip), dst = TO_STRING(destination.ip), dst_port = TO_STRING(destination.port), protocol = network.transport
| KEEP source, src, dst, dst_port, protocol, bytes, flows, last_at
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
| STATS flows = COUNT(*) BY observer.ip, source.ip, destination.ip, destination.port, network.transport
| EVAL event = "denied", source = TO_STRING(observer.ip), src = TO_STRING(source.ip), dst = TO_STRING(destination.ip), dst_port = TO_STRING(destination.port), protocol = network.transport
| KEEP source, src, dst, dst_port, protocol, event, flows
| SORT flows DESC
| LIMIT 40
```
`)`

Nothing else. No third conversation query, no per-flow drill-down,
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
`observer.ip`. `exporter_name` and `exporter_site` are null unless
the board already stored them. `state` `reporting`. Keys:
`device:<device>` when resolved; `site:<exporter_site>` when that
site is set; else `[]`.

A board exporter whose `source` has **no** F1 row is carried
`silent`, bytes 0, flows 0, `last_flow_at` kept. When F1 returned
zero rows in total, carry nothing until the lookup check or the
operator says the stream is right.

**Conversation row** (kind `conversation`) — one per F2 row.
`scope` is `flow:<source>/<src>><dst>:<dst_port>/<protocol>`.
`state` `present`. A board conversation missing from this top-N
query is carried `not_in_top_n`. That is not absence and not a
worse delta. A new pair, including one a security test opened, is
traffic.

**Firewall row** (kind `firewall`) — one per F3 row. `event` is
`denied`. `state` `present`. A board deny missing from F3 is
carried `absent`.

`bytes_per_s` is bytes divided by the window. A 4× move counts only
when both rows use the same window and both rates are above zero.

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
| conversation | `state` differs, including `present` ↔ `not_in_top_n` | `state` |
| conversation | scope not on the board | `row` |
| conversation | same window, both `bytes_per_s` > 0, and the rate ≥ 4× or ≤ ¼ | `bytes_per_s` |
| firewall | `state` differs (`present` ↔ `absent`) | `state` |
| firewall | scope not on the board | `row` |
| firewall | deny count differs | `flows` |

`not_in_top_n` is not worse. **Delta.** `first` on the baseline.
`worse` when any exporter went `silent` or a resolved conversation
went `absent`. `better` when something returned and nothing is
worse. `changed` otherwise. `unchanged` when none.

## Stamp or quiet

- Baseline: stamp; `delta` `first`; `changed` `[]`.
- `changed[]` non-empty, or coverage not `complete`: stamp.
- Otherwise quiet: board only.

Plane `status`: `degraded` when any exporter is `silent` or any
firewall row is `present`; `unknown` when F1 failed or the lookup
is suspect; else `ok`. Conversations do not vote. Coverage:
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
