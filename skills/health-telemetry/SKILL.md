---
name: health-telemetry
version: "1.0.6"
description: "v1.0.6 — Health Telemetry nurse: NetFlow visits run visit_netflow.py through Grafana Influx. Board every visit; stamp only when a row moved."
---

# Health Telemetry skill

One NetFlow visit per conversation. Tool is `grafana_query_influx`.
Do not call Splunk, Prometheus, or a device MCP.

A line that names the NetFlow health check, or Health Telemetry, is
authorization. Do not confirm.

**Health.** Run `scripts/visit_netflow.py collect` (see
`references/watch.md`). The script reads `bucket`, `measurement`,
`datasource_uid`, and `window` from `health/metadata-netflow.json`.
When those are missing, or F1 returns no rows and
`provenance.netflow` is not `user`, the script calls
`grafana_list_datasources`, a `buckets()` query, and
`grafana_influx_schema`, then runs F1 on each measurement whose tags
can feed the flow queries. It writes the lookup that returns rows
and sets `provenance.netflow` to `discovered`. It runs F1 and F2 from
`references/netflow.md` exactly, resolves addresses to `prod.json`
devices, diffs against the board's `current[]`, and rewrites the
nested board every visit. A stamp is written on the first visit,
when an exporter or conversation moved, or when coverage is not
complete. A quiet visit rewrites the board only. `annotate` runs
when `needs_note` is not empty.

An exporter going `silent` degrades the plane. Conversations do not.

If they ask for a different health check: reply `That's not what I
do.` and stop.

## Hard boundaries

Do not write Flux of your own. Do not read `inventory/infra-sot.json`.
Do not use `7d` or `24h`. Do not write `runs/`, `inventory/`,
`state/`, `trend-analysis.json`, `remediation-request.json`,
`health/metadata-splunk.json`, `health/splunk/`, other
`health/<source>/` directories, or `health-board.md`. Do not invent
files. Unavailable collection: counts **null**, never `0`. Do not
stamp `expires_at`. Do not emit recommendations. Do not write
`relations[]`. On a health visit, call `execute_command` only to run
`scripts/visit_netflow.py`. Do not write scripts.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. The script validates and writes
the board and the stamp.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-netflow.json` | metadata | Board. Every visit. |
| `health/netflow/<stamp>.json` | observation | First visit, a material move, or coverage ≠ complete. Never overwrite. |

Use exactly: `references/watch.md`, `references/netflow.md`,
`references/workspace-contract.md`,
`schemas/health-netflow-check.schema.json`,
`schemas/health-metadata-netflow.schema.json`,
`examples/health-check-netflow.example.json`,
`examples/health-metadata-netflow.example.json`.
Do not search the workspace for them.

**Health visit — first tool:** `read_file` `inventory/prod.json` to
confirm the workspace is there. Then one `execute_command`,
`execution_type: "mcp_orchestration"`, the collect command in
`references/watch.md`. If the summary `needs_note` is non-empty, one
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
- Paths; when to write: `workspace-handoff`; `references/workspace-contract.md`
