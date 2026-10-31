---
name: health-application
version: "1.5.0"
description: "v1.5.0 — Health Application nurse: Elasticsearch tiers from lab.service, plus the hosts those containers run on."
---

# Health Application skill

One visit type. Run `scripts/visit_application.py collect`. The
script reads Elasticsearch. An application row is a container tier:
`lab.service`, else the docker service label, else the name after
the first hyphen (`prod-api`, `dc-api`). `lab.application` is the
business name and stays text, not a `service:` key. A container
with no tier is not a row. Host rows are only the hosts those
containers run on. Blackbox probes and Prometheus scrape targets
are not in Elasticsearch, so this visit does not refresh those rows.

Tools on a visit: `elasticsearch_query` against
`metrics-docker.container-prod`, `metrics-docker.cpu-prod`,
`metrics-docker.memory-prod`, `metrics-system.uptime-prod`,
`metrics-system.memory-prod`, and `metrics-system.filesystem-prod`.
Do not call Grafana. Do not call `splunk_search` or a device MCP.

If they ask for a different health check: reply `That's not what I
do.` and stop.

A **board visit**. `health/metadata-application.json` carries
`current[]` (last-known rows), `annotations[]`, `series[]`,
`visits[]`. The board is the prior; do not open the prior stamp.
No material change = **quiet visit**: board only, no stamp.

`references/elastic.md` is the manual order when the script cannot
run. Every application row copies `container.name`, `host.name`,
`lab.service`, `lab.application`, and `lab.site`. `device` is the
`prod.json` spelling when the host matches. Carry unseen board
containers as `gone` and unseen hosts as `unreachable`. Diff
against `current[]`. A stamp is a container restart, appear,
vanish, or CPU crossing 80, or a host reboot or memory or root
disk crossing 10 percent.
The `host` / `device` / `application` / `site` columns are the edge;
write no `relations[]`. Write no `service:` key; the registry owns
service spellings. Do not write a query of your own.

Do not dump the MCP result. Do not write `state/`.

## Hard boundaries

Only the queries `references/elastic.md` prints. No Grafana, no `grafana_get_dashboard`,
`grafana_search_dashboards`, or `grafana_alerts`, no
`grafana_annotations(action="create")`. `window` and `probe_job`
are always from metadata; never `7d` or `24h`. Do not read
`inventory/infra-sot.json` or `inventory/topology-observed.json`. Do
not write `runs/`, `inventory/`, `state/`, `trend-analysis.json`,
`remediation-request.json`, other `health/<source>/` directories,
`health/metadata-splunk.json`, `health/metadata-netflow.json`, or
`health-board.md`. Do not invent files. Do not invent measurements.
Unavailable collection: counts **null**, never `0`. Do not write
under `automations/schedules/`. On a health visit, call
`execute_command` only to run `scripts/visit_application.py`. Do
not write scripts. Do not stamp `expires_at`. Do not emit
recommendations. Do not decide which application a host serves
beyond the labels the datasource attached.

## Files

Paths and catalog: **`workspace-handoff`**. Persist with `write_file`
on catalog paths.

| Path | Kind | Envelope |
|------|------|----------|
| `health/metadata-application.json` | metadata | Board. **Every** visit. Lookup (`probe_job`, `window`, `lookup`), `current[]`, `annotations[]`, `series[]`, `visits[]`. **Not** five-field. |
| `health/application/<stamp>.json` | observation | Only when a row moved materially, on the first visit, or coverage ≠ complete. Never overwrite. |

The stamp requires `metrics`, `readings`, `unchanged`,
`baseline_ref`, `vs_prior` (structured `changed[]`).

Use exactly: `references/watch.md`, `references/prometheus.md`,
`references/metadata.md`, `references/workspace-contract.md`,
`schemas/health-application-check.schema.json`,
`schemas/health-metadata-application.schema.json`,
`examples/health-check-application.example.json`,
`examples/health-metadata-application.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**First tools:** `read_file` `inventory/prod.json`, then one
`execute_command` of `scripts/visit_application.py collect`.

Do not open the prior stamp. Never overwrite a timestamped file.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. A row writes `application:` (the `service` label as-is), `device:` (only when `host_name` matched `prod.json`), `site:`, and `test:probe/<application>@<environment>@<target>@<vantage>` on probe rows; never a `service:` key. The target address stays a column, not a key prefix of its own. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machine

READ_BOARD → READ_PROD → T → [RESOLVE probe_job] → P1 → P2 → P3 →
P4 → P5 → P6 → C1 → C2 → C3 → C4 → C5 → C6 → C7 → C8 → H1 → H2 → H3 → H4 → A → BUILD → CARRY →
DIFF → WRITE_BOARD → DECIDE → [WRITE_STAMP → READ_BACK → PRUNE →
WRITE_BOARD] → STOP

On collection failure of one call: retry once, then keep that
kind's board rows and set coverage `partial`. If C1 and H1 both
fail: `unavailable`, null counts, stamp written, board rows
untouched.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Calls, rows, diff, board, reply: `references/prometheus.md`
- Resolve `probe_job` / window / lookup: `references/metadata.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
