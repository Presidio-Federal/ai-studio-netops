---
name: health-logging
version: "1.1.0"
description: "v1.1.0 — Health Logging nurse: Splunk syslog visits run visit_splunk.py. Board every visit; stamp only when a material event or incomplete search."
---

# Health Logging skill

One Splunk visit per conversation. Tool is `splunk_search`
(`splunk_get_indexes` only when S1 returns zero rows). Do not call
Grafana, NetFlow, or other health MCPs.

A line that names the Splunk health check, or Health Logging, is
authorization. Do not confirm.

**Health.** Run `scripts/visit_splunk.py collect` (see
`references/watch.md`). The script reads `splunk.index` and
`splunk.sourcetype` from `health/metadata-splunk.json`, runs S1 and
S2 from `references/splunk.md` exactly, resolves each `dev` to a
`prod.json` device, diffs against `splunk.current[]`, and writes the
board every visit. A stamp is written on the first visit, when S2
returned a row, or when coverage is not complete. S1 counts use the
bounded `window`. S2 collects from the watermark. A bgp or link row
with `count` ≥ 2 is a flap and degrades the plane even when `state`
reads `Up`. Silence is not device health and is not a pipeline
failure unless `source_registry` says that device is expected to report.

If they ask for a different health check: reply `That's not what I
do.` and stop.

## Hard boundaries

Do not search Splunk `index=*`. Do not write SPL of your own. Do not
read `inventory/infra-sot.json`. Do not write `runs/`, `inventory/`,
`state/`, `trend-analysis.json`, `remediation-request.json`,
`health/metadata-netflow.json`, `health/netflow/`, other
`health/<source>/` directories, or `health-board.md`. Do not invent
files. Unavailable collection: counts **null**, never `0`. Do not
stamp `expires_at`. Do not emit recommendations. Do not write
`relations[]`. On a health visit, call `execute_command` only to run
`scripts/visit_splunk.py`. Do not write scripts.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. The script validates and writes
the board and the stamp.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-splunk.json` | metadata | Board. Every visit. |
| `health/splunk/<stamp>.json` | observation | First visit, S2 returned rows, or coverage ≠ complete. Never overwrite. |

Use exactly: `references/watch.md`, `references/splunk.md`,
`references/workspace-contract.md`,
`schemas/health-splunk-check.schema.json`,
`schemas/health-metadata-splunk.schema.json`,
`examples/health-check-splunk.example.json`,
`examples/health-check-unavailable.example.json`,
`examples/health-metadata-splunk.example.json`.
Do not search the workspace for them.

**Health visit — first tool:** `read_file` `inventory/prod.json` to
confirm the workspace is there. Then one `execute_command`,
`execution_type: "mcp_orchestration"`, the collect command in
`references/watch.md`. If the summary `needs_note` is non-empty, one
`annotate` command under `execution_type: "standard"`. Reply from the
summary line. If stderr says `hai_mcp unavailable`, follow the manual
order in `references/splunk.md`.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machines

Health: READ_PROD → COLLECT_SCRIPT → [ANNOTATE] → STOP. Manual fallback, only when hai_mcp is unavailable: the order in `references/splunk.md`.

On collection failure the script still writes the check (`unavailable`, null facts) and leaves the watermark where it was.

## Reference routing

- Health visit steps, reply: `references/watch.md`
- Searches, resolve, what is material: `references/splunk.md`
- Paths; when to write: `workspace-handoff`; `references/workspace-contract.md`
