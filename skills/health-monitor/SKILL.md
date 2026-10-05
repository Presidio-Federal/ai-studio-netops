---
name: health-monitor
version: "2.2.0"
description: "v2.2.0 — Health Monitor nurse: Splunk (IOS-XE, NX-OS, ASA syslog) and NetFlow (Grafana / InfluxDB) visits. Board on metadata, stamp only on change; prod.json coverage with silent and unresolved devices; no relations[]."
---

# Health Monitor skill

One telemetry source per conversation. The invoke must name Splunk or
NetFlow. If it does not, ask which check and stop. Do not pick a
default.

Named Splunk → `splunk_search` (`splunk_get_indexes` only to
resolve or on S1 zero rows). Named NetFlow → `grafana_query_influx`
(`grafana_influx_schema` on the baseline, for an unknown exporter,
or in the lookup check; `grafana_list_datasources` in the lookup
check only).

**Empty is a lookup question first.** Zero F1 rows (NetFlow) or
zero S1 rows (Splunk) → check that the bucket / index still holds
the data before any row goes `silent` or the watermark moves
(`references/netflow.md` "Empty F1", `references/splunk.md` "S1 zero
rows"). The operator's correction beats metadata: confirm the named
value, write it with `provenance` `user`, continue. Never re-run a
query that already came back empty; never argue it is right. Do not call the other source
on this visit. Do not call `grafana_query_prometheus`; probes,
containers, and hosts are Health Application's plane. Do not call
other health MCPs.

If they ask for a different health check: reply `That's not what I
do.` and stop.

Both planes are **board visits**. The metadata file carries
`current[]` (last-known rows), `series[]`, `visits[]`. The board is
the prior; do not open the prior stamp. No material change = **quiet
visit**: board only, no stamp.

**Splunk.** `references/splunk.md` is the whole visit: read the board
(`health/metadata-splunk.json`), `prod.json`, and
`topology-observed.json` if present; run S1 and S2 exactly as
printed (baseline window `-7d`); Splunk already groups by device —
you only look up the `prod.json` spelling; write the board, then
the stamp; every S2 row is a reading and a `changed[]` item. A bgp
or link row with `count` ≥ 2 in one window is a flap: it degrades
even when `latest(state)` reads `Up`. Do not write SPL of your own.

**NetFlow.** `references/netflow.md` is the whole visit: read the
board (`health/metadata-netflow.json`), `prod.json`, and
`topology-observed.json` if present; run F1 (exporters) and F2
(conversations) exactly as printed with `timerange` = the metadata
`window`; the queries already exclude collector traffic and
ephemeral-port reverse flows — you only resolve addresses to
`prod.json` spellings; build one `exporter` row per source and one
`conversation` row per F2 row; carry unseen board rows as `silent`
/ `absent`; diff against `current[]` — only a state flip, a new
row, or a bytes move by 4× is material. The exporter and the
resolved `src_device` / `dst_device` are the edge; write no
`relations[]`. Do not name an application from a port. Do not write
Flux of your own.

Both: do not dump the MCP result. Do not write `state/`.

## Hard boundaries

Do not search Splunk `index=*`. Do not `stats` by `severity` or
`log_level`. Only the SPL `references/splunk.md` prints — no
sampling raw events, no extra searches. Only the Flux
`references/netflow.md` prints — no per-flow drill-down, no
`app_id` follow-up, no dashboards, no `grafana_get_dashboard` on a
visit. Do not read `inventory/infra-sot.json`. NetFlow `timerange`
is always the metadata `window`; never `7d` or `24h`. Do not write
`runs/`, `inventory/`, `state/`, `trend-analysis.json`,
`remediation-request.json`, `state/network-sync.json`, other
`health/<source>/` directories, or `health-board.md`. Do not invent
files. Do not invent measurements. Unavailable collection:
counts/bytes **null**, never `0`. Do not write under
`automations/schedules/`. Do **not** call `execute_command`. Do not
write scripts. Do not stamp `expires_at`. Do not emit
recommendations.

## Files

Paths and catalog: **`workspace-handoff`**. Persist with `write_file`
on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-splunk.json` | metadata | Board. **Every** Splunk visit. Lookup, watermark, `current[]`, `series[]`, `visits[]`. **Not** five-field. |
| `health/metadata-netflow.json` | metadata | Board. **Every** NetFlow visit. Lookup (`bucket`, `measurement`, `window`, `exporters[]`), `current[]`, `series[]`, `visits[]`. **Not** five-field. |
| `health/splunk/<stamp>.json` | observation | Only when S2 returned rows, on the first visit, or coverage ≠ complete. Never overwrite. |
| `health/netflow/<stamp>.json` | observation | Only when a row moved materially, on the first visit, or coverage ≠ complete. Never overwrite. |

Both stamps require `metrics`, `readings`, `unchanged`,
`baseline_ref`, `vs_prior` (structured `changed[]`).

Use exactly: `references/watch.md`, `references/splunk.md`,
`references/netflow.md`, `references/workspace-contract.md`,
`references/metadata.md`.
Splunk: `schemas/health-splunk-check.schema.json`,
`schemas/health-metadata-splunk.schema.json`,
`examples/health-check-splunk.example.json`,
`examples/health-check-unavailable.example.json`,
`examples/health-metadata-splunk.example.json`.
NetFlow: `schemas/health-netflow-check.schema.json`,
`schemas/health-metadata-netflow.schema.json`,
`examples/health-check-netflow.example.json`,
`examples/health-metadata-netflow.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**Named Splunk — first tools:** `read_file`
`health/metadata-splunk.json` (the board), then `inventory/prod.json`,
then `inventory/topology-observed.json` if it exists.

**Named NetFlow — first tools:** `read_file`
`health/metadata-netflow.json` (the board), then `inventory/prod.json`,
then `inventory/topology-observed.json` if it exists.

Neither opens the prior stamp. Never overwrite a timestamped file.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. A NetFlow row writes `device:` and `site:` keys only; never a port, an address, or an application. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machine

If the invoke does not name Splunk or NetFlow: ASK_WHICH → STOP.

Splunk: READ_BOARD → READ_PROD → READ_TOPOLOGY → RESOLVE_IF_NEEDED →
S1 → [S1 zero rows: INDEX_CHECK → (moved: ASK → STOP)] → S2 →
RESOLVE_DEVS → DIFF → WRITE_BOARD → DECIDE → [WRITE_STAMP →
READ_BACK → PRUNE → WRITE_BOARD] → STOP

NetFlow: READ_BOARD → READ_PROD → READ_TOPOLOGY → RESOLVE_IF_NEEDED →
[SCHEMA] → F1 → [F1 zero rows: LOOKUP_CHECK → (moved: rewrite
bucket, F1 | suspect: unavailable stamp, ASK → STOP)] → F2 →
RESOLVE_ADDRS → BUILD → CARRY → DIFF → WRITE_BOARD → DECIDE →
[WRITE_STAMP → READ_BACK → PRUNE → WRITE_BOARD] → STOP

On collection failure: still write that check (`unavailable`, null
counts). Do not advance the Splunk watermark.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Splunk searches, resolve, diff, board: `references/splunk.md`
- NetFlow queries, resolve, rows, diff, board: `references/netflow.md`
- Resolve ids / windows: `references/metadata.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
