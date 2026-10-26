---
name: health-elastic
version: "1.1.2"
description: "v1.1.2 — Health Elastic nurse: NetFlow visits run visit_netflow.py. Baseline is named paths; stamp a surge, a loud new path, or an exporter change."
---

# Health Elastic skill

One NetFlow visit per conversation. Tool is `elasticsearch_query`.
Do not call Grafana, Splunk, Prometheus, or a device MCP.
Do not create or edit a Kibana rule on this visit.

A line that names the NetFlow health check, or Health Telemetry, is
authorization. Do not confirm.

**Health.** Run `scripts/visit_netflow.py collect` (see
`references/watch.md`). The script reads `data_stream` and `window`
from `health/metadata-netflow.json`. When the stream is missing, or
F1 returns no rows and `provenance.netflow` is not `user`, the script
calls `elasticsearch_list_data_streams` and runs F1 on each `logs-*`
stream whose name contains `netflow`. It writes the stream that
returns rows and sets `provenance.netflow` to `discovered`. It runs
F1, F2, and F3 from `references/netflow.md` exactly, resolves
addresses to `prod.json` devices, diffs against the board's
`current[]`, and rewrites the nested board every visit. A stamp is
written on the first visit, when an exporter or conversation moved,
or when coverage is not complete. A quiet visit rewrites the board
only.

F2 collapses flows into named paths: source device, destination
device, and service. A path that holds steady is not a finding.
The first stamp is the baseline: reporting exporters and the five
largest paths, each note `Baseline.` The rest of the profile stays
on the board. A later stamp is a path whose bytes or flows moved
by 4×, a new path with a bunch of flows, a deny that surged, or
an exporter that went silent or returned. The note on a surge says
to research that path. It does not paste flow records.

F3 keeps rows whose `netflow.firewall_event` is `3` (Cisco NSEL
denied). A deny that matches the board is quiet. A deny count that
surges is material. Zero deny rows is a quiet firewall result, not
a failed query. The stream does not carry the old Grafana
`fw_event` text.

An exporter going `silent` degrades the plane. That silence is a
collection gap, not a forwarding failure. A path missing from the
query is `not_in_top_n`, not absent, and not a stamp. A new path
is traffic, including traffic a security test generated. It is a
stamp only when the flow count is a bunch for the window. Device
identity comes only from fresh exact-interface, access-host, or
exporter-name evidence. `observer.ip` is the exporter address.
`observer.name` is the display name when the stream has one.

If they ask for a different health check: reply `That's not what I
do.` and stop.

## Hard boundaries

Do not write ES|QL of your own. Do not read `inventory/infra-sot.json`.
Do not use `7d` or `24h`. `window` is `15m`, `1h`, or `1d` (default
`1h`). Do not write `runs/`, `inventory/`, `state/`,
`trend-analysis.json`, `remediation-request.json`,
`health/metadata-splunk.json`, `health/splunk/`, other
`health/<source>/` directories, or `health-board.md`. Do not invent
files. Unavailable collection: counts **null**, never `0`. Do not
stamp `expires_at`. Do not emit recommendations. Do not write
`relations[]`. On a health visit, call `execute_command` only to run
`scripts/visit_netflow.py`. Do not write scripts. Do not call
`elasticsearch_create_rule`, `elasticsearch_update_rule`,
`elasticsearch_set_rule_enabled`, or `elasticsearch_delete_rule`.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. The script validates and writes
the board and the stamp.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-netflow.json` | metadata | Board. Every visit. |
| `health/netflow/<stamp>.json` | observation | First visit, a material move, or coverage ≠ complete. Never overwrite. |

Use exactly: `references/watch.md`, `references/netflow.md`,
`references/tools.md`, `references/workspace-contract.md`,
`schemas/health-netflow-check.schema.json`,
`schemas/health-metadata-netflow.schema.json`,
`examples/health-check-netflow.example.json`,
`examples/health-metadata-netflow.example.json`.
Do not search the workspace for them.

**Health visit — first tool:** `read_file` `inventory/prod.json` to
confirm the workspace is there. Then one `execute_command`,
`execution_type: "mcp_orchestration"`, the collect command in
`references/watch.md`. Do not set `timeout`. The call is the
command and `execution_type` only. If the summary `needs_note` is non-empty, one
`annotate` command under `execution_type: "standard"`. Reply from the
summary line. If stderr says `hai_mcp unavailable`, follow the manual
order in `references/netflow.md`.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. A NetFlow row writes `device:` and `site:` keys only. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machines

Health: READ_PROD → COLLECT_SCRIPT → [ANNOTATE] → STOP. Manual fallback, only when hai_mcp is unavailable: the order in `references/netflow.md`.

On F1 failure the script writes an `unavailable` check and leaves board rows untouched.

## Reference routing

- Health visit steps, reply: `references/watch.md`
- Queries, resolve, what is material: `references/netflow.md`
- Tool names: `references/tools.md`
- Paths; when to write: `workspace-handoff`; `references/workspace-contract.md`
