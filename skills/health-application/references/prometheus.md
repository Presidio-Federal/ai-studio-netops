# Application visit — probes, containers, hosts

The only visit this skill has. Tools are `grafana_query_prometheus`
(instant, one expression per call), `grafana_prometheus_targets`
(once), `grafana_annotations` (list, once), and — on the baseline
only — `grafana_prometheus_labels`. `probe_job`, `window`, and
`lookup` come from `health/metadata-application.json`. Do not put a
datasource uid, a host name, a service name, or a target address in
this file. Do not call `grafana_query_influx`; flows are Health
Monitor's plane.

Twelve expressions, copied exactly. One call per message. Copy
numbers; do not reason about the platform. A call that fails is
retried once; a second failure leaves that kind's board rows as
they were and sets coverage `partial`.

## Setup (reads, before any Grafana call)

1. `read_file` `health/metadata-application.json` — lookup and the
   **board** (`application.current[]`, `annotations[]`, `series[]`,
   `visits[]`). Missing `probe_job` → `references/metadata.md`
   (resolve), write metadata, then continue.
2. `read_file` `inventory/prod.json` — `devices[].name`. A
   `host_name` label that equals a device name case-insensitively
   resolves to that device; write the `prod.json` spelling.

Do not open the prior stamp; the board is the prior state. Do not
read `inventory/topology-observed.json` or `inventory/infra-sot.json`.

**Window.** `application.window` from metadata (default `1h`). It
is the `[<window>]` range in P4, the `timerange` on the annotations
call, and the `timerange` argument on every query. Do not use `7d`
or `24h`. Do not change `window`.

## Reading a result

Every `grafana_query_prometheus` result is `series[]`; each entry
has `labels` (the Prometheus labels of that series) and `rows[]`
with one row on an instant query. The row's value is the numeric
column that is not `Time` (named `Value` or the metric name). Match
series across calls by their labels as stated per kind below. A
series whose labels do not carry the matching label is skipped, not
guessed.

## Calls

**T — scrape targets. Always, first.** `grafana_prometheus_targets()`.
Each `targets[]` item: `health`, `lastScrape`, `lastError`,
`scrapeUrl`, `labels` (`job`, `instance`, and whatever the scrape
config attached: `host_name`, `service`, `site`, `vantage_point`,
`role`, `application`).

**Probes** — substitute `<probe_job>` from metadata; match series
by `instance`.

- **P1** `probe_success{job="<probe_job>"}`
- **P2** `probe_http_status_code{job="<probe_job>"}`
- **P3** `probe_duration_seconds{job="<probe_job>"}`
- **P4** `avg_over_time(probe_success{job="<probe_job>"}[<window>]) * 100`

**Containers** — match series by `name` + `instance`.

- **C1** `container_start_time_seconds{image!=""}`
- **C2** `sum by (name, host_name, service, application, site, instance) (rate(container_cpu_usage_seconds_total{image!=""}[5m])) * 100`
- **C3** `container_memory_working_set_bytes{image!=""}`
- **C4** `sum by (name, host_name, service, application, site, instance) (rate(container_network_receive_bytes_total{image!=""}[5m]))`

**Hosts** — match series by `host_name` (fall back to `instance`
when `host_name` is absent).

- **H1** `node_boot_time_seconds`
- **H2** `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100`
- **H3** `node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100`
- **H4** `node_network_up{device!~"lo|veth.*|docker.*|br-.*"}`

**A — change annotations. Always, last.**
`grafana_annotations(action="list", timerange=<window>)`. Keep the
items that carry at least one tag starting `change:`; copy `time`
as returned, `tags`, `text`. A failed A leaves the board's
`annotations[]` alone and does not touch coverage.

**L — label spellings (baseline only, or when `lookup` is empty).**
`grafana_prometheus_labels(label="service")`, then `"site"`,
`"vantage_point"`, `"host_name"`. Write the values to `lookup`
(`provenance: discovered`). Never call L otherwise. `lookup` is a
record of the spellings seen; it does not filter the queries.

Order: setup → T → P1 → P2 → P3 → P4 → C1 → C2 → C3 → C4 → H1 → H2
→ H3 → H4 → A → build → carry → diff → write. Nothing else: no
range queries, no `grafana_get_dashboard`, no `grafana_alerts`
(no rules are bound; it would prove nothing), no expression of
your own.

## Build the rows

Four kinds. `at` is `checked_at` on every row. `device` is the
`prod.json` device the `host_name` resolved to, else null.

**Probe row** (kind `probe`) — one per P1 series.

| Column | From |
|--------|------|
| `scope` | `probe:<service>@<vantage_point>` (labels on the P1 series; `none` when a label is absent) |
| `application` | `service` label |
| `vantage_site` | `vantage_point` label |
| `site` | `site` label |
| `target` | `instance` label |
| `success` | P1 value (0 or 1) |
| `http_code` | P2 value for the same `instance`, else null |
| `duration_ms` | P3 value × 1000, whole number, else null |
| `success_pct_window` | P4 value, whole number, else null |
| `state` | `up` when `success` = 1; `down` when 0; `unknown` when P1 failed (row copied from the board) |
| `keys` | `application:<service>`; `site:<site>` when set; `test:probe/<service>@<vantage_point>` |

**Container row** (kind `container`) — one per C1 series.

| Column | From |
|--------|------|
| `scope` | `container:<host_name>/<name>` |
| `name` | `name` label |
| `host` | `host_name` label (else `instance`) |
| `device` | resolved from `host` |
| `application` | `service` label, else null |
| `service` | `application` label copied as text, else null (no key; the registry decides service spellings) |
| `site` | `site` label |
| `image` | `image` label |
| `started_epoch` | C1 value, whole number |
| `cpu_pct` | C2 value for the same `name` + `instance`, one decimal, else null |
| `mem_bytes` | C3 value, whole number, else null |
| `rx_bytes_s` | C4 value, whole number, else null |
| `state` | `running` |
| `keys` | `application:<service>` when set; `device:<device>` when resolved; `site:<site>` when set |

A board container row with **no** C1 series this visit is carried
with `state` `gone`, numbers kept, `at` `checked_at`. Drop a `gone`
row after 7 days.

**Host row** (kind `host`) — one per H1 series.

| Column | From |
|--------|------|
| `scope` | `host:<host_name>` |
| `host` | `host_name` label (else `instance`) |
| `device` | resolved from `host` |
| `site` `role` | labels |
| `boot_epoch` | H1 value, whole number |
| `mem_available_pct` | H2 value for the same `host_name`, whole number, else null |
| `fs_root_avail_pct` | H3 value, whole number, else null |
| `interfaces_down` | the H4 `device` labels for this `host_name` whose value is 0, sorted; `[]` when none; null when H4 failed |
| `interfaces_up` | count of H4 series for this host with value 1; null when H4 failed |
| `state` | `up` |
| `keys` | `device:<device>` when resolved; `site:<site>` when set |

A board host row with **no** H1 series this visit is carried with
`state` `unreachable`, numbers kept.

**Target row** (kind `target`) — one per T item whose `scrapeUrl`
is not the Prometheus server itself.

| Column | From |
|--------|------|
| `scope` | `target:<job>/<instance>` |
| `scrape_pool` `instance` | labels `job`, `instance` |
| `host` | `host_name` label when present |
| `device` | resolved from `host` |
| `health` | `health` (`up` / `down` / `unknown`) |
| `last_error` | `lastError`, or null when empty |
| `last_scrape` | `lastScrape` |
| `state` | = `health` |
| `keys` | `device:<device>` when resolved; else `[]` |

Rows carry no `service:` key: the registry owns those spellings.
Do not merge two `service` label spellings into one application.

## Diff against the board

Match rows to `application.current[]` by `scope`. Only these move a
row onto the stamp:

| Kind | Material when | `changed[].field` |
|------|---------------|-------------------|
| probe | `success` differs | `success` |
| probe | `http_code` differs | `http_code` |
| container | `started_epoch` differs by more than 60 (restart) | `started_epoch` |
| container | `state` differs (`running` ↔ `gone`) | `state` |
| container | `cpu_pct` crossed 80 in either direction | `cpu_pct` |
| host | `boot_epoch` differs by more than 60 (reboot) | `boot_epoch` |
| host | `interfaces_down` differs | `interfaces_down` |
| host | `mem_available_pct` crossed 10 | `mem_available_pct` |
| host | `fs_root_avail_pct` crossed 10 | `fs_root_avail_pct` |
| host | `state` differs (`up` ↔ `unreachable`) | `state` |
| target | `health` differs | `health` |
| any | scope not on the board | `row` |

Not material: `duration_ms`, `success_pct_window`, `mem_bytes`,
`rx_bytes_s`, `interfaces_up`, `last_scrape`, small moves. Those
land on the board only.

`changed[]` item: `{keys, field, prior, current, at}` — `prior` from
the board row (null when new), `current` from this row; for
`interfaces_down` join the lists with `,`.

**Delta.** `first` on the baseline. `worse` when any item is a
probe `success` 1 → 0, a container `gone` or restarted, a host
reboot, `unreachable`, or a new interface down, a target leaving
`up`, or a threshold crossed downward. `better` when items exist,
none is worse, and at least one is a recovery. `changed` for new
rows, `http_code` moves with `success` still 1, or thresholds
crossed upward. `unchanged` when none.

## Stamp or quiet

- Baseline (no `baseline_visit_id`): stamp; every row is a reading;
  `delta` `first`; **`changed` `[]`**; `unchanged` 0;
  `prior_watch_id` null.
- `changed[]` non-empty, or coverage not `complete`: stamp; readings
  = the rows that moved.
- Otherwise **quiet**: no stamp. Board only.

Plane `status`: `degraded` when any probe is `down`, any container
is `gone` or restarted this visit, any host is `unreachable`,
rebooted this visit, or has an interface down, or any target is not
`up`; `unknown` when P1, C1, and H1 all failed; else `ok`. Coverage:
`complete` when every call from T through H4 returned; `partial`
when some failed (that kind's rows kept from the board);
`unavailable` when P1, C1, and H1 all failed (stamp with a single
all-null estate metric row, `readings` `[]`, board rows untouched,
`last_collected_at` still advanced).

## Write

**Stamp** (schema `health-application-check`). Top-level fields,
these names and no others:

```json
{
  "keys": [], "schema": "health-application-check/v1", "source": "application",
  "watch_id": "<YYYY-MM-DDTHH-MM-SSZ>", "checked_at": "<ISO Z>", "ok": true,
  "status": "ok|degraded|unknown", "headline": "...",
  "window": "1h",
  "coverage": { "state": "complete|partial|unavailable", "detail": "..." },
  "metrics": [ { "at": "...", "scope": "estate", "probes": 3, "probes_down": 0, "containers": 4, "containers_restarted": 0, "containers_gone": 0,
                 "hosts": 2, "hosts_rebooted": 0, "interfaces_down": 0, "targets": 7, "targets_down": 0, "change_annotations": 0 } ],
  "readings": [ { "...row columns...", "note": "..." } ],
  "unchanged": 0, "baseline_ref": null,
  "vs_prior": { "prior_watch_id": null, "delta": "first", "changed": [] },
  "concerns": [ { "type": "application", "name": "<service>" } ]
}
```

`metrics` = one `estate` row: counts across every row this visit;
`containers_restarted` and `hosts_rebooted` count this visit's
`started_epoch` / `boot_epoch` items; `interfaces_down` sums the
host lists; `change_annotations` = items kept from A. `readings` =
moved rows + `note`. `unchanged` = board rows not replaced.
`baseline_ref` = `health/application/<baseline_visit_id>.json`
(null on the baseline). `headline`: which application probe is
down from which vantage and since when, which container restarted
or vanished on which host, which host rebooted or lost an
interface; then rows unchanged and whether a `change:` annotation
fell inside the window. `concerns`: one `{type: application, name}`
per probe `down` or container `gone` / restarted whose
`application` is set; one `{type: device, name}` per host that is
`unreachable`, rebooted, or has an interface down and resolved to
a device.

`note` is one or two sentences about **this row against its board
row**: down since which visit, how many restarts on this board,
whether the reboot lines up with a `change:` annotation in
`annotations[]` (name the tag, nothing more), whether the other
vantage points agree. Not the columns again. Do not name a cause
outside this board. Do not conclude across kinds. On the baseline
the note is `Baseline.` unless the row is `down`, `gone`,
`unreachable`, or has an interface down.

**Board** (schema `health-metadata-application`) — every visit:
- `current[]` ← built rows replace rows with the same `scope`;
  carried rows (`gone`, `unreachable`) keep their scope; rows of a
  kind whose calls failed are kept as they were; cap 96.
- `annotations[]` ← the items kept from A this visit replace the
  list; keep 20, newest first.
- `series[]` ← append the estate metric row; keep 10.
- `visits[]` ← append `{watch_id (null when quiet), checked_at,
  status, coverage, delta, stamp_written, window}`; keep 10.
- `lookup` ← rewritten only when L ran.
- `last_collected_at` ← `checked_at`. `last_visit_id` ← this
  `watch_id` only when a stamp was written. `baseline_visit_id` ←
  this `watch_id` on the first visit.
- `keys` ← union of keys on `current[]`.

Write the board as soon as the rows exist, then the stamp (when
due), `read_file` it, prune to 10 stamps in `health/application/`
only, then rewrite the board with `last_visit_id`.

## Budget

| Item | Max |
|------|----:|
| Workspace reads | 2 |
| Workspace writes | 4 (board, stamp, prune, board) |
| `grafana_prometheus_targets` | 1 (plus one retry) |
| `grafana_query_prometheus` | 12 (plus one retry each) |
| `grafana_annotations` | 1 |
| `grafana_prometheus_labels` | 4 (baseline only) |

## Reply

Stamp written:

```text
Visit: application
Result: <ok | degraded | unknown>
Coverage: <complete|partial|unavailable>
Window: <window>
Wrote: health/application/<stamp>.json
Trend: <delta>
Findings:
- probe <application> from <vantage_site>: <up|down>, HTTP <http_code>, <success_pct_window>% ok over <window>
- container <name> on <device or host>: <running|gone|restarted>, cpu <cpu_pct>%
- host <device or host>: <up|unreachable|rebooted>, down interfaces <list or none>, fs <fs_root_avail_pct>% free
- target <scrape_pool>/<instance>: <health> <last_error>
Annotations: <n> change tags in window
Next: none
```

Quiet:

```text
Visit: application
Result: <ok | degraded>
Coverage: complete
Window: <window>
Wrote: health/metadata-application.json (no material change)
Trend: unchanged
Board: <p> probes (<d> down), <c> containers, <h> hosts, <t> targets, last stamp <last_visit_id>
Next: none
```
