---
name: workspace-handoff
description: "v1.36.0 — Shared workspace catalog: which files exist, who writes each one, and which fields another agent may read. Attach on every agent that reads or writes the workspace."
version: "1.36.0"
---

# Workspace handoff

The shared workspace is the state. This skill is the catalog: which files
exist, who writes each one, and which fields another agent may read.
Each agent updates its **coordination** pages (`state`, `request`, `result`)
with the common envelope (`headline` + `next_action`). Observations,
metadata, and configuration use the writer schema only. Snapshots use the
writer schema except `inventory/infra-sot.json`, which publishes the
envelope.

**Writer skill** owns the write schema, examples, and validator. Load a
schema only when you are that writer, from that skill. Never copy a write
schema into this skill.

**Details** go in that agent’s directory. **Summary** is `state/<name>.json`
(one writer, except `state/lifecycle.json`: Modernization Analysis and
Modernization Lifecycle merge). Health: per-plane metadata and
observations, rollup `state/health.json` (Health Analyzer). Do not
invent other health files.

The file and the delegation are one act:

1. Write the file.
2. If a subagent is attached and this file is their input, invoke them and wait.
3. Never tell the operator to go run the next agent.

**Exception — Health Analyzer:** if a health plane is stale or
missing and that row’s Writer is attached, invoke the named visit
for this workspace. `assess-now`: **do not wait**.
`refresh-then-assess`: wait only for planes both stale and material
to the question. Continue on files already on disk unless that mode
waited. Record `dispatched[]` on `state/health.json`. Do not tell
the operator to run the Writer.

| Plane | Writer | Task line |
|-------|--------|-----------|
| `splunk` | Health Monitor | `Run the Splunk health check only.` |
| `thousandeyes` | Health Monitor | `Run the ThousandEyes health check only.` |
| `iosxe` | Health Device | `Run the network device health check only.` |
| `servicenow` | Health ServiceNow | `Run the ServiceNow health check only.` |

Splunk and ThousandEyes are separate invokes. Do not send an unnamed
Health Monitor line.

**Exception — Modernization Analysis:** if any `state/lifecycle.json` row is
missing EoX or expired and Modernization Lifecycle is attached,
invoke `Run the Modernization Lifecycle check only.` and **do not
wait**. Continue on files already on disk. Record `dispatched[]` on
`state/lifecycle.json`. Do not tell the operator to run the collector.

## Paths (once)

| Tool | Path |
|------|------|
| Built-in file tools | workspace-relative — `inventory/prod.yaml` |
| `execute_command` | `/workspace/inventory/prod.yaml` |
| Skill files | skill-relative; scripts under `/skills/user/<skill>/...` |

`write_file` creates parents. Never `mkdir`. Never `/workspace/` or
`workspace/` on built-in tools. Never `/shared_workspace/` (including
`/shared_workspace/HAI-ASSISTANTS-WAPSPACES/...`), `sessions/`, or
`Internal directory`.

**Exception — Modernization Lifecycle:** MiniMax `read_file` /
`write_file` may be the session sandbox. If Access denied and
Allowed paths include `file_explorer`, retry **once** as
`file_explorer/<catalog row>` (no leading slash, no UUID). Same
catalog, not a new tree. JSON `detail_ref` stays the catalog row
(`lifecycle/items/<pid>.json`). If the item write still fails,
still merge onto `state/lifecycle.json` (same prefix that
worked).

A scheduled invoke may list `automations/schedules/<name>/<timestamp>` as an
allowed `dirPath`. That folder is empty scratch. It is **not** the workspace.
Do not `get_folder_structure` / `lstat` it. Do not write observations there.
Do not prefix catalog paths with it (`…/inventory/prod.json` is wrong;
`inventory/prod.json` is right). Health visits write catalog paths
only (`health/<source>/<stamp>.json` and merge `state/health.json`).
Open catalog names with built-in tools as written in the table below.

The workspace is not the git repo. Config text, the job catalog, and job
logs stay in git or Actions. Read git with `github_get_file`. Never
`write_file` a copy of a git file into the workspace so a script can run.

**Write only catalog paths.** If a path is not a row in the table below for
this agent, do not create it. Do not write helper scripts (`.py`), scratch
dumps (`_git_input.json`), or `prepare_*` files. Do not invent files.
Health: do not invent `health-board.md`. Compliance: do not invent matrix
copies. `inventory/runtime/` is gitignored (CI runner only).

## Envelope

Coordination artifacts use the common envelope when marked **state**,
**request**, or **result** in the catalog. Observations, snapshots,
metadata, and configuration follow their writer-owned schemas. Readers
apply the envelope blocking rule only to **required coordination inputs**;
otherwise they use catalog rely-on fields and report reduced coverage.

```json
{
  "updated_at": "2026-08-20T17:00:00Z",
  "source_agent": "ops-network-sync",
  "status": "ok",
  "headline": "One line a human can read",
  "next_action": "What the next agent or human should do"
}
```

**Blocking (required coordination input only):** missing file, stale
`updated_at`, or failed `status` blocks **that dependent action** — not
the whole run. Alert the operator with artifact path, reason, owner
(catalog Writer), and the next invoke. Continue independent work.
Missing **optional** inputs → `partial` / `unknown` coverage (Health) or
skip that step. Never infer missing workspace data from chat. Quote
`headline` when present. Do not paste the file.

`inventory/infra-sot.json` is a published **snapshot** that **does** carry
this envelope (handoff from Ops NetBox SoT). Health check files under
`health/thousandeyes/`, `health/splunk/`, `health/iosxe/`, and
`health/servicenow/` are
**observations** — not this envelope. `state/health.json` is the Health
Analyzer **state** rollup. Nurses do not write `state/`.

Do not write `lab-access.json`, `vuln-report.json`, `runs/`,
`risk/`, or a root `compliance.json`. Test writes
`testing/YYYY-MM-DDTHH-MM-SSZ.json` (e.g. `2026-08-21T19-56-18Z.json`);
do not invent other files under `testing/`. Do not invent
`lifecycle/` paths other than the catalog rows below.

## Catalog

Writer owns the write schema. Reader uses **rely on** only. For catalog
**state** / **request** / **result**, also the envelope. Catalog change =
one row pointing at the writer — not a new schema file here.

| File | Kind | Writer | Schema | Readers may rely on |
|------|------|--------|--------|---------------------|
| `inventory/prod.json` `inventory/dev.json` | snapshot | Ops Network Sync | `ops-network-sync` `schemas/network-access-inventory.schema.json` | Canonical accumulating inventory and published access snapshot (`network-access-inventory/v3`). Merge in place; extra keys allowed. Rely on `snapshot_id`, `collected_at` `published_at` `expires_at` (current iff now < `expires_at`; stale access is inspect-only), `status` `complete`\|`partial`, `coverage` (not `unavailable`; failed collect is not this file), documented device identity/access (`name` `platform` `role` `tags` `operational_state` `agent_access` `access.restconf`/`ssh` `source_metadata`). `next_action` is not on this file. |
| `inventory/infra-sot.json` | snapshot | Ops NetBox SoT | `ops-netbox-mcp` `schemas/infra-sot.schema.json` | envelope, `mode` (`bootstrap`\|`audit`\|`reconcile`; `refresh` records `audit`), `seed`, `parents.*.id`, `devices[].name` `id` `device_type` `software_version` (IOS-XE `version` or null), `interfaces[]` name/id/`cidr`, `cables[]` names+ids, `counts` |
| `state/network-sync.json` | state | Ops Network Sync | `ops-network-sync` `schemas/network-sync-state.schema.json` | Replaceable projection (`network-sync-state/v2`). Envelope `status` is this operation only. Rely on `operation_id` `operation` `started_at` `completed_at`; `inventories.*.latest_attempt`; `inventories.*.current_snapshot` (`snapshot_id` must match the json file, `path`, freshness, `status`, `coverage`); workflow `result` `run_id` `html_url` `updated_at` (per-workflow result words; not the GitHub check); `gaps`; `next_action` string or JSON `null` — never `"none"`. Failed collect updates `latest_attempt` only. |
| `state/netbox.json` | state | Ops NetBox SoT | `ops-netbox-mcp` `schemas/netbox-state.schema.json` | envelope, `kind` `mode` (`bootstrap`\|`audit`\|`reconcile`; `refresh` records `audit`) `seed_match` `counts` `links[]` `details` |
| `state/workspace.json` | state | Onboard | `workspace-onboard` `schemas/workspace-control.schema.json` | envelope, `planes.inventory` `planes.config_sync` `planes.netbox` (`yes`\|`no`). Reset sets `config_sync` and `netbox` to `no`. Onboard is the only writer. |
| `test-request.json` | request | Network Design | this skill `schemas/test-request.schema.json` | envelope + scope in that schema |
| `testing/YYYY-MM-DDTHH-MM-SSZ.json` | result | Test | `network-test` run schema / this skill `schemas/testing.schema.json` | envelope, `risk` `results` |
| `state/testing.json` | state | Test | this skill `schemas/testing.schema.json` / `network-test` | envelope, `latest` `risk` `run.suites` |
| `compliance/YYYY-MM-DDTHH-MM-SSZ.json` | result | Test | this skill `schemas/compliance.schema.json` / `network-test` run schema | envelope, `risk` `results` — **only** when `suites` includes `compliance` |
| `state/compliance.json` | state | Test | this skill + `network-test` | envelope, `latest` `risk` `run.suites` — **only** a compliance-suite run |
| `compliance/coverage.json` | snapshot | Compliance | this skill `schemas/coverage.schema.json` | writer schema (`updated_at` `source_agent` `rows` `counts`). Built from `github_get_file` catalog + NIST titles — not a workspace copy of git. Not the five-field envelope |
| `compliance/intel.json` | result | Compliance | this skill `schemas/compliance-intel.schema.json` | envelope, `candidates` (Test authoring) |
| `branch-deploy-summary.json` | result | Network Design | this skill `schemas/branch-deploy-summary.schema.json` | envelope + ticket slot (ServiceNow) |
| `remediation-request.json` | request | Observability | this skill `schemas/remediation-request.schema.json` | envelope + ticket slot (ServiceNow) |
| `trend-analysis.json` | observation | Observability | this skill `schemas/trend-analysis.schema.json` | leftover; prefer `state/health.json` |
| `health/metadata-splunk.json` | metadata | Health Monitor (Splunk visit) | `health-monitor` `schemas/health-metadata-splunk.schema.json` | Writer schema. Splunk `index` / `sourcetype` / `collected_through` / `last_visit_id` from the workspace file (not from the skill or prompt). **Not** the five-field envelope. |
| `health/metadata-thousandeyes.json` | metadata | Health Monitor (TE visit) | `health-monitor` `schemas/health-metadata-thousandeyes.schema.json` | Writer schema. TE `account_id`, `tests[]`, `last_visit_id` from the API / workspace file (not from the skill or prompt). **Not** the five-field envelope. |
| `health/metadata-servicenow.json` | metadata | Health ServiceNow | `health-servicenow` `schemas/health-metadata-servicenow.schema.json` | Writer schema. `servicenow.marker` / `match_terms` / `last_visit_id` from the workspace file. Missing marker: ask or stop — do not invent. **Not** the five-field envelope. |
| `health/thousandeyes/<stamp>.json` | observation | Health Monitor | `health-monitor` `schemas/health-thousandeyes-check.schema.json` | One TE visit writes **one** new file. Never overwrite. At most **10** stamps in this directory; writer deletes older after write. `watch_id` `checked_at` `ok` plane `status` `headline` `coverage.state` required `metrics[]`. |
| `health/splunk/<stamp>.json` | observation | Health Monitor | `health-monitor` `schemas/health-splunk-check.schema.json` | One Splunk visit writes **one** new file. Never overwrite. At most **10** stamps; writer deletes older after write. Required `metrics[]`. |
| `health/iosxe/<stamp>.json` | observation | Health Device | `health-device` `schemas/health-iosxe-check.schema.json` | One device visit writes **one** new file. Never overwrite. At most **10** stamps; writer deletes older after write. `devices[]` required `metrics[]`. PAT `port` from `inventory/prod.json` `access.restconf.port`. |
| `health/servicenow/<stamp>.json` | observation | Health ServiceNow | `health-servicenow` `schemas/health-servicenow-check.schema.json` | One ServiceNow visit writes **one** new file. Never overwrite. At most **10** stamps; writer deletes older after write. `incidents[]` `changes[]` `recent[]` required `metrics[]`. Find/get only. Never write `state/servicenow.json`. |
| `state/health.json` | state | Health Analyzer | `health-analyzer` `schemas/health-state.schema.json` | Rollup chart. Envelope `status` is worst of complete/partial **thousandeyes, splunk, iosxe** — ServiceNow does not vote. Rely on `consults.<plane>` (derived from the latest stamp), `freshness` (`current`\|`stale`\|`missing` from `checked_at` + 26h), `series` (`window` 10, `watermark`, `points[]` copied from visit `metrics`), `mode`, `dispatched[]`, `coverage`. `updated_at` is write time. Visit writers do **not** write this file. |
| `state/lifecycle.json` | state | Modernization Analysis **and** Modernization Lifecycle | `modernization-analysis` / `modernization-lifecycle` `schemas/lifecycle-estate.schema.json` | Consolidated estate, one row per evidence product id (`device_type` / `node_definition` / serial PID as written — never hostname-to-SKU). Five-field envelope. Modernization Analysis writes identity, `guidance`, `assessment`, `plan` (cost + timeline), `selected_replacement` when the operator **names** a SKU, `recommendations[]` on a plan invoke, and `roadmap_ref`. Copies through research. Never overwrite higher `source.reliability` with lower unless the operator overrides. Modernization Lifecycle merges hardware EoX, software train, PSIRT, NVD, CCW onto matching `pid`; copies through identity, `guidance`, `roadmap_ref`, `recommendations[]`, and `selected_replacement`; `recommended_replacement` only from Cisco hardware EoX; family-only bulletin → `replacement_ask` / candidates on the **row**; `recommended_software` only from Cisco software EoX / PSIRT Software Checker. CCW prices `selected_replacement` if set, else Cisco `recommended_replacement`. Empty hardware EoX on a virtual PID is `research.eox` `unavailable`. Do not create this file if missing (Lifecycle stops `unknown`). Rely on `items[].pid` `selected_replacement` `recommended_replacement` `replacement_ask` `recommended_software` `list_cost_per_unit` `guidance` `roadmap_ref` `research`. Current if `now < expires_at`. |
| `lifecycle/items/<pid>.json` | observation | Modernization Lifecycle | `modernization-lifecycle` `schemas/lifecycle-item.schema.json` | Per-PID Cisco dump. Replace when that PID is collected. Rely on `eox` `replacement` (`sku` Cisco-only; `family` `candidates` `ask`; costs after CCW) `recommended_software` `psirts` `vulnerabilities` `expires_at`. Do **not** store `selected_replacement` here. Path is `items[].detail_ref`. Do not `ls` `lifecycle/`. MiniMax sandbox: `write_file` `file_explorer/lifecycle/items/<pid>.json` after Access denied. |
| `lifecycle/roadmap.md` | observation | Modernization Analysis | `modernization-analysis` `references/roadmap.md` | Human-readable sequence (order, stage, deploy, schedule, cutover). Written only after `guidance.answers` is non-empty on a plan invoke. Replace in full. Path is `roadmap_ref`. Not a second JSON plan. Lifecycle does not write this file. |
| `state/servicenow.json` | state | ServiceNow | `snow-mcp` `schemas/servicenow-state.schema.json` | envelope, `open` `history[]` `trend` |
| `servicenow/cases/active.json` | snapshot | ServiceNow | `snow-mcp` `schemas/servicenow-cases-active.schema.json` | open cases + `devices[]` |
| `servicenow/cases/index.json` | snapshot | ServiceNow | `snow-mcp` `schemas/servicenow-cases-index.schema.json` | numbers this agent has touched |
| `servicenow/requests/**` | request | ServiceNow (queue) | `snow-mcp` `schemas/servicenow-request.schema.json` | **Not** the five-field envelope. `servicenow-request/v1`: `request_id` `created_at` `requested_by` `operation` `correlation_id` `idempotency_key` `source_refs` `authorization` `record`. Pending file the operator named. |

## Health layout

Lookup: `health/metadata-splunk.json`,
`health/metadata-thousandeyes.json`,
`health/metadata-servicenow.json` (**metadata**, not enveloped).
Dated visits under `health/thousandeyes/`, `health/splunk/`
(Health Monitor), `health/iosxe/` (Health Device), and
`health/servicenow/` (Health ServiceNow)
(`YYYY-MM-DDTHH-MM-SSZ.json`) (**observation**). At most **10**
stamps per source directory; that writer deletes older files after
a new write. Rollup:
`state/health.json` (**state**, Health
Analyzer only). Do not write `health-board.md`. Keep these lowercase
paths. Timestamped observations are never overwritten. `watch_id`
matches **this visit’s** new observation.

On `state/health.json`, readers may use the envelope, `consults`,
`freshness`, `series`, `coverage`, `mode`, `dispatched[]`, and
`next_action`. Envelope `status` is vital worst-of (not ServiceNow).
**Current** when `freshness.<plane>.state` is `current`. **Stale**
when `stale`. **Missing** when `missing`. `updated_at` is write time.
Write schema lives in `health-analyzer`. Do not load a visit writer’s
skill to read the rollup.
`health/thousandeyes|splunk/<stamp>.json` are Health Monitor observations.
`health/iosxe/<stamp>.json` is Health Device.
`health/servicenow/<stamp>.json` is Health ServiceNow.
IOS-XE PAT is `inventory/prod.json` `access.restconf.port`, not
metadata.

Visit writers persist with `write_file` on their catalog rows (same as
before). They do not merge the rollup.

## Lifecycle layout

Primary table: `state/lifecycle.json` (**state**, Modernization
Analysis identity + `guidance` + `assessment` + `plan` +
`selected_replacement` + recommendations
+ Modernization Lifecycle research merge). The operator SKU
lives **only** on the table row. Headline, `next_action`,
`guidance`, `assessment`, `plan`, `recommendations[]`, and
`lifecycle/roadmap.md` **are** the plan. Details: `lifecycle/items/<pid>.json`
(**observation**, Cisco facts; not the operator pick). Roadmap
markdown: Modernization Analysis only, after operator answers. Do not
write `state/modernization.json`.
Do not `ls` `lifecycle/`. Open `detail_ref` from the table. Do not
invent `vuln-report.json` or `inventory/lifecycle.json`.
MiniMax Lifecycle: sandbox `write_file` may need
`file_explorer/` + catalog row; `detail_ref` stays the catalog
row.
Modernization Analysis may **read** `state/health.json` for a plan invoke; it
does not write it.

`testing/YYYY-MM-DDTHH-MM-SSZ.json` and `compliance/YYYY-MM-DDTHH-MM-SSZ.json`
are append-only. Other files
are replaced in full except Sync yaml (merge). One writer per `state/` file
except `state/lifecycle.json` (Modernization Analysis identity; Modernization Lifecycle
research merge).
`state/health.json` is Health Analyzer only.
`state/testing.json` is the latest **any-suite** run. `state/compliance.json`
is the latest **`suites` includes `compliance`** run — not a copy of a
reachability/routing/path run.

Sync yaml is Sync's file. **Ops NetBox SoT reads `inventory/prod.json` only** for
seed. Missing json **blocks bootstrap** (owner: Ops Network Sync) — alert and
continue anything that does not need seed. It writes `inventory/infra-sot.json`
(enveloped snapshot) and `state/netbox.json` (summary). Do not open yaml for
that agent. Do not put NetBox ids in prod.json. Do not write Sync state from
NetBox.

**Onboard** writes `state/workspace.json` only. Reset flips `config_sync`
and `netbox` to `no`. Other agents may read planes; they do not write this
file.

## Writing (you are the writer)

1. Paths and catalog: this skill. Write **only** rows you own. Never invent
   a path so a script has an input file.
2. Field list: **your** skill schema — not another writer's, not this skill.
   Fill from the example in that skill (or this skill’s leftover examples).
3. `write_file`, read back, validate with your skill script if present.
4. If this file is a handoff to an attached subagent, invoke them now.
   Health Analyzer: named health visits are **not** a wait-for-handoff
   in `assess-now`; invoke and continue (see exception above).
   `refresh-then-assess` may wait for material stale planes only.
   Modernization Analysis: named Modernization Lifecycle visits are **not** a
   wait-for-handoff; invoke and continue.

## Reading

1. Open the catalog path. Classify **Kind**.
2. Required **state** / **request** / **result** (and enveloped
   `inventory/infra-sot.json` when that snap is required for the action):
   missing, stale, or failed envelope → block **that action**, alert
   (artifact, reason, owner, next invoke), continue independent work.
   Optional missing → reduced coverage / skip that step. Never invent from
   chat.
3. **observation** / **snapshot** (except infra-sot envelope) /
   **metadata** / **configuration**: rely-on fields only. Do not apply the
   five-field stop rule.
4. Health: `state/health.json` is the analyzer rollup (envelope +
   `consults` `freshness` `series` `coverage` `mode` `dispatched[]`
   `next_action`). Current vs stale vs missing as in the Health
   catalog row. Plane files: envelope + `consult`. Check files:
   observation fields (`watch_id` `coverage.state` `metrics`) — not
   envelope-block. `health/metadata-*.json`: lookup ids — not
   envelope-block.
5. `source_refs` that start with `workspace/` or `/workspace/` → strip and
   read the remainder.
6. Lifecycle: `state/lifecycle.json` is the estate table (envelope +
   `items[]` + `guidance` + `recommendations[]`). Current per row when
   `now < expires_at`. Details: `items[].detail_ref` →
   `lifecycle/items/<pid>.json`. Plan markdown: `roadmap_ref` →
   `lifecycle/roadmap.md`. Do not `ls` `lifecycle/`. Group by
   evidence product id, not hostname. Headline, `next_action`,
   `guidance`, `assessment`, `plan`, `recommendations[]`, and
   the roadmap markdown are the plan. Modernization Analysis may read health state for a plan;
   missing health is optional.
