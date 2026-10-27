# Data bundle (`D`)

`scripts/build_map.py` compiles this object from the workspace and
injects it at `__DATA__` in `references/template.html`. The template
reads only these fields. Change both together.

| Field | From | Notes |
|-------|------|-------|
| `generated` | script clock | UTC stamp |
| `lab`, `environment` | `prod.json` `lab_title` / `source.name`, `environment` | page title |
| `sources{}` | each board's `updated_at` / `compiled_at` / `collected_at`; nurse boards `last_collected_at` | footer |
| `missing[]` | boards not present | footer, summary |
| `layout` | `override`, then `cml` (every node has `source_metadata.position`), else `auto` | footer |
| `link_source` | `inventory/prod.json links[]`, `state/relationships.json connected_to`, or `none` | footer |
| `nodes[]` | `prod.json devices[]` minus `external_connector` / `unmanaged_switch` | `label` `platform` (`iosxe` `l2` `nxos` `asa` `linux` …) `role` `site` (`site:` tag) `tags` (no `pat:` / `synced:`) `access` `state` `mgmt` (name `OOB*` or `oob` tag) `x` `y` |
| `links[]` | `prod.json links[]`; fallback compiled `connected_to` edges | `a` `ai` `b` `bi` `mgmt`; both ends must resolve to a node (case-insensitive) |
| `edges[]` | `relationships.json edges[]` | `from` `to` `rel` `basis` `status` `sources` `last_seen` |
| `rel_head`, `rel_updated`, `drift[]` | `relationships.json` | |
| `health` | `state/health.json` | `present` `headline` `status` `score` `coverage` `updated_at` `problems[]` (`id` `status` `keys` `hypothesis` `opened_at` `closed_at` `order` `impact` `outcome` `evidence_refs`) `assessment` `next_action` `trend.points[]` |
| `compliance` | `state/compliance.json` + `state/testing.json` | `present` `headline` `updated_at` `test_updated` `scores` `findings[]` (`kind` `status` `severity` `summary` `keys` `next_owner`) `trend` (`direction` `environment` `newly_passing` `newly_failing` `still_failing` `narrative` `points[]` `{at, pct}` `flips[]`) `counts` `risk` `run` `failing_devices` `scanned_devices` |
| `netops` | `state/network-ops.json` | `present` `headline` `updated_at` `mode` `review[]` (`rank` `devices` `interfaces` `finding` `kind` `proposed` `verified_in_git` `problem_ref`) `change` (`devices` `interfaces` `blast_radius` `annotation_ref`) |
| `snow` | `state/servicenow.json` | `present` `headline` `updated_at` `open` `next_action` |
| `sync` | `state/network-sync.json` + `prod.json` | `headline` `updated_at` `coverage` `device_count` `collected_at` `status` |
| `lifecycle` | `state/lifecycle.json` | `present` `headline` `updated_at` `cost_low` `cost_high` `currency` `notes` `psirts` (count of advisories on the estate) `by_device` (hostname → pid) `items[]` (`pid` `qty` `devices` `support` `window` `replacement` `candidates` `offers` `lead_time` `software` `psirts`). `window` is `overdue` when support is past, `soon` within 90 days, `later`, or `undated`. `offers[]` is `sku` `list_cost_per_unit` `currency` `lead_time` `availability`. Each item keeps five advisories (`id` `title` `severity` `cve` `cvss`), critical first. `cost_low` / `cost_high` are min and max list price × quantity across priced offers. `approaching_cost_low` / `approaching_cost_high` are that sum for `window: soon` only. `advisory_counts` is Critical / High / Medium / Low across every advisory. `advisories[]` is every advisory, with `pid` and `devices`. |
| `app.services[]` | `inventory/applications.json` grouped by `service`. A tier with no `service` inherits it from a tier that `depends_on` it. Probe rows join a tier when `application` equals the tier name. A container joins that tier when its `application` or `name` equals the tier, or ends with `-<tier>` (`dc-api` and `prod-api` join `api`). The container keeps its own name. A container that matches no tier is still emitted under its Grafana label | per service: `service` `tiers[]` (`name` `depends_on` `hosts` `hosts_unmapped` `status` `probes{site}` `containers[]`) `hosts[]` `host_node` (first host that is an inventory device; `hosts_unmapped` is resolved against the current `prod.json` and used when it matches) `path[]` (BFS over non-mgmt cables from `host_node` to the first IOS-XE edge/wan/cloud/hq/branch device). `app.score` is probes up / probes. |
| `app.hosts{}` | application board `kind: host` rows keyed by resolved device, else `host` text | `device` `instance` `state` `boot` `mem` `fs` `ifdown` `role` `site`. A tier's `containers[]` carry the cAdvisor columns the board stored: `name` `image` `state` `cpu` `mem` `rx` `start` `host` `device` |
| `syslog{}` | `health/metadata-splunk.json splunk.current[]` summed by resolved device and `kind` | device from a `device:` key, else `name` when it is an inventory device (case-insensitive) or a `splunk.hosts` / access-host pin. An address left in `name` is not a device. `source_ip` is the client on an ACL row, not the logger |
| `syslog_unresolved[]` | the same rows whose device did not resolve | `name` `kinds` |
| `flows[]` | `netflow.current[]` `kind: conversation`, not `absent`, top 25 by `bytes` | `exp` `src` `dst` (endpoint names) `src_device` `dst_device` (set only when the name is an inventory device) `port` (service token or port) `proto` (`tcp` `udp` `scan`) `bytes` `flows` `state` |
| `flow_arcs[]` | those conversations whose `src` and `dst` both resolve to inventory devices and `state` is `present` | `src` `dst` `scan`. The NetFlow toggle draws these. A name such as `prod-api` is not an arc |
| `denies[]` | `kind: firewall`, `state` not `absent`, top 15 by `flows` | same path columns. Not an arc |
| `exporters[]` | `netflow.exporters[]`, state from `current[]` `kind: exporter` on the same `source` | `name` `source` `state` `device` |
| `telemetry` | counts before the top-N cut | `conversations` `denies` `arcs` |

## Scores and trend

`health.score` is 100 × voting consults with `status: ok` / voting consults that exist. Voting planes are `application`, `netflow`, `splunk`, `iosxe`. ServiceNow does not vote. `degraded` is not ok. Null when no voting consult is present. The envelope `status` is shown beside the number and is not folded into it.

`compliance.trend.points[]` is checks passed / (passed + failed + errored) from `series.testing.points` (`pass` / `fail` / `error`, or `checks_*_all`). `{at, pct, pass, fail, method}`. When the same point also has `verified_tests` and `failing_tests`, those ride along as `tests_verified` and `tests_failing` and are not the percent. A point with neither check counts nor verified-test counts is omitted. The header and the Compliance card use the newest trend point. Hover and click show the check counts and, when present, how many canonical tests are fully green.

`counts` prefer `state/testing.json` `results.counts_ran`. When that object is absent, the newest series point that has `pass` / `fail` / `error` supplies them. `failing_devices` prefers the testing board list; otherwise `device:` keys on `test_failure` findings that are not `remediated`. `worst_devices` is those devices ranked by finding count, cap 10.

`health.trend.points[]` is built from `problems[]` only. Each `opened_at` and `closed_at` is a point. `pct` is problems closed by that moment / problems opened by that moment. The point carries `open`, `closed`, `event`, and `open_ids`. The newest point also carries `assessment.opinion` and `trend_analysis.narrative`. Probe counts, exporter silence, and IOS-XE flags are not a line. A flip is drawn on the trend only when it is an object with `at`; prose flips stay as text.

## Layout

Precedence, first that covers every included node:

1. `inventory/map-layout.json` (operator-authored) → `layout: override`.
2. `prod.json` `devices[].source_metadata.position` (`{x, y}` from the
   CML canvas, written by Ops Network Sync) → `layout: cml`.
3. Otherwise `layout: auto`: one column per `site` (order: cloud, wan,
   core, datacenter, hq, branch, then alphabetical; devices without a
   site are `core`). Rows inside a column: IOS-XE edge/wan/cloud first,
   then hq/branch IOS-XE, then ASA, then NX-OS / L2, then Linux;
   management devices last. Deterministic.

A partial set never mixes: one node without a position drops the whole
source and the next one is tried.

```json
{ "nodes": { "AI-DC-EDGE": { "x": 480, "y": 0 }, "DC-APP-HOST-01": { "x": 480, "y": 390 } } }
```

## Summary line (stdout)

```json
{"result":"ok","wrote":"reports/network-map.html","bytes":68717,"generated":"2026-10-01T19:25:52Z","nodes":26,"links":38,"link_source":"inventory/prod.json links[]","layout":"auto","edges":70,"problems":6,"findings":10,"review_rows":8,"lifecycle_items":11,"psirts":63,"lifecycle_cost_low":"636359.28","lifecycle_cost_high":"872838.81","services":["Order Management"],"hosts_mapped":["DC-APP-HOST-01"],"missing_boards":[]}
```

Failure: exit 1 and one line starting `error:`.
