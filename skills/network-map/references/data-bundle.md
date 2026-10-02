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
| `health` | `state/health.json` | `present` `headline` `status` `coverage` `updated_at` `problems[]` (`id` `status` `keys` `hypothesis` `opened_at` `order` `impact` `outcome`) `assessment` `next_action` |
| `compliance` | `state/compliance.json` + `state/testing.json` | `present` `headline` `updated_at` `test_updated` `scores` `findings[]` (`kind` `severity` `summary` `keys` `next_owner`) `counts` (`results.counts_ran`) `risk` `run` `failing_devices` `scanned_devices` (`scope.devices_scanned`) |
| `netops` | `state/network-ops.json` | `present` `headline` `updated_at` `mode` `review[]` (`rank` `devices` `interfaces` `finding` `kind` `proposed` `verified_in_git` `problem_ref`) `change` (`devices` `interfaces` `blast_radius` `annotation_ref`) |
| `snow` | `state/servicenow.json` | `present` `headline` `updated_at` `open` `next_action` |
| `sync` | `state/network-sync.json` + `prod.json` | `headline` `updated_at` `coverage` `device_count` `collected_at` `status` |
| `app.services[]` | `inventory/applications.json` grouped by `service`; tiers joined to `health/metadata-application.json current[]` by `application` (container rows also by `name` with a `dc-` prefix stripped) | per service: `service` `tiers[]` (`name` `depends_on` `hosts` `hosts_unmapped` `status` `probes{site}` `containers[]`) `hosts[]` `host_node` (first host that is an inventory device) `path[]` (BFS over non-mgmt cables from `host_node` to the first IOS-XE edge/wan/cloud/hq/branch device) |
| `app.hosts{}` | application board `kind: host` rows keyed by resolved device, else `host` text | `device` `instance` `state` `boot` `mem` `fs` `ifdown` `role` `site` |
| `syslog{}` | `health/metadata-splunk.json splunk.current[]` summed by resolved device and `kind` | device resolved from `name` / `subject`, else `splunk.hosts[source_ip]` |
| `flows[]` | `health/metadata-netflow.json netflow.current[]` `kind: conversation`, top 25 by `bytes` | `exp` `src` `dst` `port` `proto` `bytes` `state` |
| `exporters[]` | `netflow.exporters[]` | `name` `state` |

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
{"result":"ok","wrote":"reports/network-map.html","bytes":68717,"generated":"2026-10-01T19:25:52Z","nodes":26,"links":38,"link_source":"inventory/prod.json links[]","layout":"auto","edges":70,"problems":6,"findings":10,"review_rows":8,"services":["Order Management"],"hosts_mapped":["DC-APP-HOST-01"],"missing_boards":[]}
```

Failure: exit 1 and one line starting `error:`.
