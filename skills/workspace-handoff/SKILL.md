---
name: workspace-handoff
description: "v1.54.0 — Every structured workspace record carries canonical source-supported relationship keys."
version: "1.54.0"
---

# Workspace handoff

The shared workspace is the state. This skill is the catalog: which files
exist, who writes each one, and which fields another agent may read.
Coordination files (`state`, `request`, `result`) use the envelope.
Observations, metadata, and configuration use the writer schema.
Snapshots use the writer schema, except `inventory/infra-sot.json`,
which publishes the envelope.

The writer skill owns the schema, the example, and the procedure.
Load a schema only when you are that writer. Do not copy a schema
into this skill.

One writer per file. `state/lifecycle.json` is the exception:
Modernization Analysis and Modernization Lifecycle both write it.
Details live in that agent's directory. The summary is
`state/<name>.json`. The health rollup is `state/health.json`
(Health Analyzer).

The file and the delegation are one act:

1. Write the file.
2. If a subagent is attached and this file is their input, invoke them and wait.
3. Never tell the operator to go run the next agent.

**Health Analyzer.** If a plane is clock-stale (`checked_at` + 26h) or
missing, and that Writer is attached, invoke the task line. A stamp
inside 26h is current, including `coverage` `unavailable`.
`assess-now`: do not wait. `refresh-then-assess`: wait only for planes
that are both stale and material. Record `dispatched[]` on
`state/health.json`.

| Plane | Writer | Task line |
|-------|--------|-----------|
| `splunk` | Health Monitor | `Run the Splunk health check only.` |
| `thousandeyes` | Health Monitor | `Run the ThousandEyes health check only.` |
| `iosxe` | Health Device | `Run the network device health check only.` |
| `servicenow` | Health ServiceNow | `Run the ServiceNow health check only.` |

Splunk and ThousandEyes are separate invokes.

**Modernization Analysis.** If any `state/lifecycle.json` row is missing
EoX or expired, and Modernization Lifecycle is attached, invoke
`Run the Modernization Lifecycle check only.` and do not wait. Record
`dispatched[]` on `state/lifecycle.json`.

**Compliance Analyzer.** Intel and Testing evidence is current for 24 hours.
`assess-now` dispatches stale attached specialists without waiting.
`refresh-then-assess` waits only for stale material planes, then rereads
metadata. Record dispatches on `state/compliance.json`.

| Plane | Writer | Task line |
|-------|--------|-----------|
| `intel` | Compliance Intelligence | `Run the compliance intelligence scan only.` |
| `testing` | Compliance Test | `Run the compliance suite only on the Dev twin.` |

Writing Intel evidence does not invoke Author. Only operator-selected
`INTEL-*` ids authorize Compliance Author.

**Network Design.** Read the chart already on disk. Missing or stale
inputs are reduced coverage; still write `state/design.json`. Warehouse
check uses this agent's ServiceNow tools. Do not collect Splunk,
ThousandEyes, or Cisco. Do not write other agents' state files.

## Paths

| Tool | Path |
|------|------|
| Built-in file tools | a catalog row, as written below |
| `execute_command` | those same files on the mount the file tool already has |
| Skill files | skill-relative; scripts under `/skills/user/<skill>/...` |

`write_file` creates parents. Never `mkdir`. Do not invent a prefix
or a second tree.

A scheduled invoke may list `automations/schedules/<name>/<timestamp>`
as an allowed `dirPath`. That folder is empty scratch. It is not the
workspace. Do not list it, write there, or prefix a catalog path with it.

The workspace is not the git repo. Read git with `github_get_file`.
Do not `write_file` a copy of a git file. `inventory/runtime/` is
gitignored (CI runner only).

Write only catalog paths. Do not write helper scripts, scratch dumps,
or `prepare_*` files. Do not invent `health-board.md`,
`lab-access.json`, `vuln-report.json`, a root `runs/`, `risk/`,
`trend-analysis.json`, `remediation-request.json`, a root
`compliance.json`, or extra `lifecycle/` and `design/` paths.
Compliance Test writes general testing rows and, for compliance suites, its
cataloged compliance-testing visit and metadata only.

## Envelope

```json
{
  "updated_at": "2026-08-20T17:00:00Z",
  "source_agent": "<writer>",
  "status": "ok",
  "headline": "One line a human can read",
  "next_action": "What the next agent or human should do"
}
```

Use this on **state**, **request**, and **result**, and on
`inventory/infra-sot.json`. Apply the blocking rule only when that
file is a required coordination input.

Missing file, stale `updated_at`, or failed `status` blocks that
dependent action. Alert with the path, the reason, the catalog Writer,
and the next invoke. Continue independent work. A missing optional
input is reduced coverage. Do not infer workspace data from chat.
Quote `headline`. Do not paste the file.

Health stamps are observations. Nurses do not write `state/`.

## Entity reference

Every structured JSON catalog record requires a top-level `keys` array.
It is the deduplicated union of every source-supported entity in that record
and its nested rows. Write `keys: []` when the source identifies none. Keep
nested row `keys` so each data point remains independently joinable.
The externally owned, currently absent Onboard contract for
`state/workspace.json` is deferred.

When a writer names a thing another agent joins on, use these fields.
Writer schemas copy this shape. Do not copy the referenced object.
Do not invent an id. Do not put topology, edges, or cause here.

- `type` (required) — `device` `interface` `site` `service` `test` `control` `incident` `change`
- `name` (required) — the spelling already in `inventory/prod.json` or `inventory/infra-sot.json`, or the ticket number or API id the tool returned
- `id` — the source-native id when the file you opened has one; otherwise null
- `source_ref` — the catalog path or ticket id, not a payload

The join key is `type:name`. Use `site:` for locations. When a device is known,
qualify an interface as `interface:<device>/<interface>` to avoid collisions.
When a tool payload contains several entities, write every one on that row's
`keys` and in the top-level union. A later file joins by sharing the same
string. Do not invent a key the payload does not contain. Do not drop one.

Recommendations remain required agent outputs wherever the owning skill calls
for them. Only recommendation ids are excluded from relationship `keys`;
findings, PIDs, product SKUs, prose, source refs, and record ids likewise stay
in their own fields. The future relationship map joins `(timestamp, catalog
path, shared keys[])`; it does not copy payloads between records.

Extend `type` only when a write cannot proceed with this list.
Do not add a catalog file for entities.

## Catalog

Reader uses **rely on**. Writer procedure stays in the writer skill.
For **state**, **request**, and **result**, also use the envelope.
For every JSON row below except deferred `state/workspace.json`, readers may
rely on top-level `keys` being present; `[]` means no supported entity.

Observation stamps are `YYYY-MM-DDTHH-MM-SSZ.json`, append-only.
Open the prior stamp from that source's metadata `last_visit_id`.
Do not list the directory. The writer keeps 10 and deletes older
after the write.

| File | Kind | Writer | Schema | Readers may rely on |
|------|------|--------|--------|---------------------|
| `inventory/prod.json` `inventory/dev.json` | snapshot | Ops Network Sync | `ops-network-sync` `schemas/network-access-inventory.schema.json` | `snapshot_id` `collected_at` `published_at` `expires_at` (current iff now < `expires_at`) `status` `coverage` `name` `platform` `role` `tags` `operational_state` `agent_access` `access.restconf` `access.ssh` `source_metadata`. Missing prod.json blocks NetBox bootstrap. |
| `inventory/infra-sot.json` | snapshot | Ops NetBox SoT | `ops-netbox-mcp` `schemas/infra-sot.schema.json` | envelope, `mode` `seed` `parents.*.id` `devices[].name` `id` `device_type` `software_version` `interfaces[]` `cables[]` `counts` |
| `state/network-sync.json` | state | Ops Network Sync | `ops-network-sync` `schemas/network-sync-state.schema.json` | envelope, `operation_id` `operation` `started_at` `completed_at` `inventories.*.latest_attempt` `inventories.*.current_snapshot` `gaps` `next_action` |
| `state/netbox.json` | state | Ops NetBox SoT | `ops-netbox-mcp` `schemas/netbox-state.schema.json` | envelope, `kind` `mode` `seed_match` `counts` `links[]` `details` |
| `state/workspace.json` | state | Onboard | `workspace-onboard` `schemas/workspace-control.schema.json` | envelope, `planes.inventory` `planes.config_sync` `planes.netbox` |
| `test-request.json` | request | Network Design | `network-design` `schemas/test-request.schema.json` | envelope, scope |
| `operational/testing/YYYY-MM-DDTHH-MM-SSZ.json` | result | Compliance Test | `compliance-test-runner` `schemas/testing-run.schema.json` | envelope, `risk` `results`, row `keys` |
| `operational/runs/YYYY-MM-DDTHH-MM-SSZ.json` | result | Pipeline Monitor or GitHub GitOps Change | `github-actions-mcp` `schemas/operation-run.schema.json` | envelope, `operation` `git` `workflow` `result` `devices` `files` `summary` `keys`; never config bodies, patches, or full logs |
| `state/testing.json` | state | Compliance Test | `compliance-test-runner` `schemas/testing-state.schema.json` | envelope, `latest` `risk` `run.suites` |
| `compliance/metadata-testing.json` | metadata | Compliance Test | `compliance-test-runner` `schemas/compliance-test-metadata.schema.json` | `last_visit_id` `last_collected_at` |
| `compliance/testing/<stamp>.json` | observation | Compliance Test | `compliance-test-runner` `schemas/compliance-test-visit.schema.json` | `visit_id` `checked_at` `status` `coverage` via results, `metrics` `vs_prior` `results` row `keys` `risk` |
| `state/compliance.json` | state | Compliance | `compliance-analyzer` `schemas/compliance-state.schema.json` | envelope, `mode` `freshness` `consults` `series` `scores` `findings` `assessment` `trend_analysis` `soap` `dispatched`; `next_action` is `soap.plan` |
| `compliance/coverage.json` | snapshot | Compliance Intelligence | `compliance-intel` `schemas/coverage.schema.json` | `updated_at` `source_agent` `rows` `counts`, row `keys` |
| `compliance/intel.json` | result | Compliance Intelligence | `compliance-intel` `schemas/compliance-intel.schema.json` | envelope, `delta` `candidates[]` `skipped_non_network` `why_network`, candidate `keys` |
| `compliance/metadata-intel.json` | metadata | Compliance Intelligence | `compliance-intel` `schemas/compliance-intel-metadata.schema.json` | `last_visit_id` `last_collected_at` |
| `compliance/intel/<stamp>.json` | observation | Compliance Intelligence | `compliance-intel` `schemas/compliance-intel-visit.schema.json` | `visit_id` `checked_at` `status` `coverage` `metrics` `candidates[].keys` `vs_prior` |
| `branch-deploy-summary.json` | result | Network Design | `network-design` `schemas/branch-deploy-summary.schema.json` | envelope, ticket slot |
| `state/design.json` | state | Network Design | `network-design` `schemas/design-plan.schema.json` | envelope, `assessment` `hardware[]` `software[]` `configuration[]` `compliance[]` `timeline[]` `warehouse` `asks[]` `answers` `horizon` `coverage` `read[]` `roadmap_ref` |
| `design/roadmap.md` | observation | Network Design | `network-design` `references/roadmap.md` | path is `roadmap_ref` |
| `state/network-ops.json` | state | Network Ops | `network-ops` `schemas/network-ops-state.schema.json` | envelope, `mode` `finding` `change` including `operational_ref`, `git` `ci` `pr` `keys` |
| `health/metadata-splunk.json` | metadata | Health Monitor | `health-monitor` `schemas/health-metadata-splunk.schema.json` | `index` `sourcetype` `collected_through` `last_visit_id` |
| `health/metadata-thousandeyes.json` | metadata | Health Monitor | `health-monitor` `schemas/health-metadata-thousandeyes.schema.json` | `account_id` `tests[]` `last_visit_id` |
| `health/metadata-servicenow.json` | metadata | Health ServiceNow | `health-servicenow` `schemas/health-metadata-servicenow.schema.json` | `marker` `match_terms` `last_visit_id` |
| `health/metadata-iosxe.json` | metadata | Health Device | `health-device` `schemas/health-metadata-iosxe.schema.json` | `last_visit_id` `last_collected_at`. RESTCONF port stays on `inventory/prod.json`. |
| `health/thousandeyes/<stamp>.json` | observation | Health Monitor | `health-monitor` `schemas/health-thousandeyes-check.schema.json` | `headline` `coverage` `metrics` `keys` `vs_prior` `alerts` `path_summary` |
| `health/splunk/<stamp>.json` | observation | Health Monitor | `health-monitor` `schemas/health-splunk-check.schema.json` | `headline` `coverage` `metrics` `readings` `keys` `vs_prior` |
| `health/iosxe/<stamp>.json` | observation | Health Device | `health-device` `schemas/health-iosxe-check.schema.json` | `headline` `coverage` `metrics` `readings` `keys` `vs_prior` `concerns` |
| `health/servicenow/<stamp>.json` | observation | Health ServiceNow | `health-servicenow` `schemas/health-servicenow-check.schema.json` | `headline` `coverage` `metrics` `threads` (`keys` + `note`) `vs_prior` `ticket_numbers` |
| `state/health.json` | state | Health Analyzer | `health-analyzer` `schemas/health-state.schema.json` | envelope, `soap` `consults` `freshness` `series` `coverage` `mode` `dispatched`. `next_action` is `soap.plan`. |
| `state/lifecycle.json` | state | Modernization Analysis and Modernization Lifecycle | `modernization-analysis` / `modernization-lifecycle` `schemas/lifecycle-estate.schema.json` | envelope, `items[].pid` `selected_replacement` `recommended_replacement` `replacement_ask` `recommended_software` `list_cost_per_unit` `guidance` `roadmap_ref` `research`. Current iff now < `expires_at`. |
| `lifecycle/items/<pid>.json` | observation | Modernization Lifecycle | `modernization-lifecycle` `schemas/lifecycle-item.schema.json` | `eox` `replacement` `recommended_software` `psirts` `vulnerabilities` `expires_at`. Path is `items[].detail_ref`. |
| `lifecycle/roadmap.md` | observation | Modernization Analysis | `modernization-analysis` `references/roadmap.md` | path is `roadmap_ref` |
| `servicenow/metadata-lab.json` | metadata | Ops ServiceNow Operator | `ops-snow-mcp` `schemas/servicenow-metadata-lab.schema.json` | `marker` `match_terms` `last_visit_id` |
| `servicenow/metadata-trends.json` | metadata | Ops ServiceNow Trends | `ops-servicenow-trends` `schemas/servicenow-metadata-trends.schema.json` | `groups` `categories` `match_terms` `marker` `lookback_days` `min_related_cases` `last_visit_id` |
| `servicenow/trends/<stamp>.json` | observation | Ops ServiceNow Trends | `ops-servicenow-trends` `schemas/servicenow-trend.schema.json` | `clusters` `metrics` |
| `state/servicenow.json` | state | Ops ServiceNow Operator | `ops-snow-mcp` `schemas/servicenow-state.schema.json` | envelope, `open` `history` `trend` |
| `servicenow/cases/active.json` | snapshot | Ops ServiceNow Operator | `ops-snow-mcp` `schemas/servicenow-cases-active.schema.json` | open cases, `devices[]` |
| `servicenow/cases/index.json` | snapshot | Ops ServiceNow Operator | `ops-snow-mcp` `schemas/servicenow-cases-index.schema.json` | numbers this agent has touched |
| `servicenow/requests/**` | request | Ops ServiceNow Operator | `ops-snow-mcp` `schemas/servicenow-request.schema.json` | `request_id` `created_at` `requested_by` `operation` `correlation_id` `idempotency_key` `source_refs` `authorization` `record` |

## Writing

1. Write only catalog rows you own.
2. Fill fields from your skill schema.
3. `write_file`, read back, validate with your skill script when it has one.
4. If this file is input for an attached subagent, invoke them now.
   Health Analyzer and Modernization Analysis do not wait.
   Network Design writes from files already on disk.
   Network Ops invokes GitHub GitOps Change once, consumes its final compact
   response without polling subagent status, creates/merges the PR on pass,
   then replaces `state/network-ops.json`.
   Compliance Intelligence writes its files and stops. Compliance Analyzer
   writes only `state/compliance.json`. Invoke Author only for
   operator-selected INTEL ids.

## Reading

1. Open the catalog path. Use its Kind.
2. A required **state**, **request**, or **result** (and `inventory/infra-sot.json` when that snap is required): missing, stale, or failed envelope blocks that action. Alert and continue independent work. Optional missing is reduced coverage.
3. An **observation**, **snapshot** (except infra-sot), **metadata**, or **configuration** file: rely-on fields only.
4. A `source_ref` that starts with `workspace/` or `/workspace/`: strip that prefix and read the remainder.
