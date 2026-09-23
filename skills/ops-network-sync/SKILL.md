---
name: ops-network-sync
version: "1.8.3"
description: "v1.8.3 — Onboard parent with canonical top-level workspace entity keys."
---

# Ops Network Sync skill

You own the **workspace inventory**. Empty workspace → create
`inventory/prod.json`. Present workspace → collect and **merge**. Config SoT
still goes through GitHub Actions. You do not write NetBox, design topology,
apply IOS-XE, or file tickets. Building or reconciling a twin lab is Digital
Twin. You run `deploy-twin.yml` / `reconcile-dev.yml` only when Twin names them.

## Roles

| Store | Role |
|-------|------|
| `inventory/prod.json` `dev.json` | Canonical accumulating inventories and published access snapshots |
| `state/network-sync.json` | Replaceable coordination projection |
| GitHub Actions | Durable run evidence (URL + marker). No raw logs or configs in the workspace |

Every invocation records `operation_id`, `operation`, `started_at`,
`completed_at`. Envelope `status` is **this** operation only.

## First action

**Read workspace** (`inventory/prod.json`, `state/network-sync.json`). Then:

| Workspace | Do |
|-----------|----|
| No prod.json | Create path — [references/inventory.md](references/inventory.md). Interview only here. |
| prod.json exists | Merge path — collect from `source`, update json in place. |

## Publication order

1. Read canonical inventory and current state.
2. Collect source evidence.
3. Merge without discarding unknown or user-authored fields.
4. Write, read back, validate inventory JSON.
5. Publish `state/network-sync.json` last (`current_snapshot.snapshot_id`
   equals the file).
6. Read back and validate state.

Collection or validation failure: do not rewrite last-known-good inventory.
Record only `latest_attempt` (coverage `unavailable`, counts **null**).
Never publish an incomplete inventory as current.

`latest_attempt` vs `current_snapshot`: a failed refresh updates the
attempt; the snapshot (and json) stay last-known-good. Readers can tell
a failed refresh from missing inventory (`current_snapshot` null).

Stale snapshot (`now >= expires_at`): inspect only; do not treat PAT as
current access.

## Route

| Intent | How |
|--------|-----|
| Onboard / new network / no prod.json | Create path (inventory.md) |
| Onboard parent: collect inventory | Merge (or create). Do **not** run `sync-prod.yml`. Do **not** invoke NetBox. Skip seed gate. |
| Onboard parent: `sync-prod.yml` | Run it even if inventory already exists. Do **not** invoke NetBox. |
| Refresh inventory / PAT / access | Merge into json (`source.type` `cml` = CML RO collect). Then [seed gate](#seed-gate--netbox-sot). |
| Capture Prod, push Dev, detect drift, author-check wait | `github-actions-mcp` |
| Named `deploy-twin.yml` / `reconcile-dev.yml` (Twin subagent) | Run it (`github-actions-mcp`), then merge **Dev** access (PAT changed). Not your product. |
| Build twin / reconcile topology (operator) | Digital Twin. Name it and stop. Do not trigger. |
| Populate NetBox | Name Ops NetBox SoT and stop. Do not call NetBox MCP. Do not report cables or CDP. |

Do not put workflow inputs or marker names here. Read `github-actions-mcp`.

Ask once, then proceed: "sync" with no direction → Prod capture or Dev push?
"drift" with no lab → prod or dev? Anything else: pick a default and say it
in one line. Prod then Dev together: finish `sync-prod` before `sync-dev`
(`sync-dev` rebases onto `main`).

`author-check.yml`: wait, never trigger. The PR already started it. Return
`PASSED`, `NOT SELECTED`, or `ONLY SKIPPED` as distinct answers.

Git `inventory/runtime/` is not in the workspace. Never read it for PAT.

When Twin, Design, Compliance, or Onboard invoked you: reply is run URL,
result word, and files you wrote — no operator next-steps. If you invoked
Ops NetBox SoT, wait; your Gaps stay this Sync job. At most one Next:
`Ops NetBox SoT`. Onboard already owns NetBox — do not invoke it.

| Tag | Owner | Means |
|-----|-------|-------|
| `tag:sync` | you | config collect and push |
| `tag:simulate` | Digital Twin | topology mirroring |
| `tag:patch` | Network Design | proposed Dev nodes — exclude from your selectors |

A green Actions job with failed devices is **gaps**, never `ok`. Do **not**
infer success from the GitHub check. Completed runs need marker-derived
`result` plus `run_id`, `html_url`, `updated_at`, `workflow`, and
`environment`. Allowed result words are per workflow
([references/sync-state.md](references/sync-state.md)). `UNCHANGED` on
`sync-prod` and `IN_SYNC` on `reconcile-dev` are success. On `sync-dev`,
a transient EOF/timeout then a successful retry is not a gap; auth failure
or a dead PAT is. `sync-dev` has no device scoping — say so rather than
imply a limit worked.

## Seed gate — Ops NetBox SoT

Only after a successful **CML inventory** collect that wrote `inventory/prod.json`.
Do **not** run this after `sync-prod.yml` / `sync-dev.yml`. Those jobs are config
SoT. Your report for those jobs is the Actions marker only — never NetBox cables
or CDP. Skip this gate when **Onboard** invoked you.

If you invoke Ops NetBox SoT, do not merge its Gaps into your reply.

After a successful **prod** collect that wrote `inventory/prod.json`:

1. From prod.json, take devices whose `tags` contain exact `tag:simulate`.
   Each row: `name`, `host` = `access.restconf.host` or null, `port` =
   `access.restconf.port` or null, `node_definition` =
   `source_metadata.node_definition`. Sort by `name`.
2. Read `inventory/infra-sot.json` if present. Compare that list to snap
   `seed` (same four fields, same order after sort). Do not hash.
3. **Match** and snap `status` is `ok` or `gaps` → do not invoke NetBox.
   Headline that inventory identity is unchanged. `next_action` is JSON
   `null` (or twin, not populate). Never the string `"none"`. Do not write
   or preserve `infra_sot` on Sync state.
4. **Mismatch**, missing snap, or snap `failed` → `next_action` populate
   NetBox. If the Ops NetBox SoT subagent is attached, invoke it and wait
   (handoff: prod.json is their input). You still do not call NetBox MCP
   and you do not write `state/netbox.json`.

Failed collect → skip the gate. Do not invent a snap.

## Hard boundaries

CML collect: only `cml_list_labs`, `cml_get_lab_details`, `cml_get_node_info`,
`cml_find_nodes_by_tags`. No topology/config writes. No guessed ports. No
credentials in files. Do not write `lab-access.json` or `runs/`.
Do not write `inventory/infra-sot.json` or `state/netbox.json` (Ops NetBox SoT).

## Tenant

Never default a customer name. No NetBox MCP — do not call `netbox_find`.
Ask for tenant and site when you need them. No answer: slug of `lab_title`,
else `lab-<utc-date>`.

## Files

Paths and catalog: **`workspace-handoff`**. When/how: `references/workspace-contract.md`.
Write schemas in this skill. Do not load other writers' schemas.

Every JSON write includes top-level `keys`: the deduplicated union of exact
entity keys supported by structured fields in that artifact, or `[]`. Do not
infer keys from prose. Use only `device|interface|site|service|test|control|incident|change`;
locations use `site:`. When a device is known, interfaces are
`interface:<device>/<interface>`. Keep any nested `keys`.

Skill resources — use exactly:

- `references/workspace-contract.md`
- `references/inventory.md`
- `references/sync-state.md`
- `schemas/network-access-inventory.schema.json`
- `schemas/network-sync-state.schema.json`
- `examples/inventory-prod.example.json`
- `examples/inventory-dev.example.json`
- `examples/network-sync-state.example.json`
- `examples/network-sync-state-failed-collect.example.json`

`execute_command` validate after json/state write (optional). Missing script → skip.

```text
python3 /skills/user/ops-network-sync/scripts/validate_network_sync.py pair /workspace/state/network-sync.json /workspace/inventory/prod.json /workspace/inventory/dev.json
```

Read every file you write back.

## State machine

**Empty:** DISCOVER → INTERVIEW → WRITE_JSON → VALIDATE_JSON → WRITE_STATE → VALIDATE_STATE → STOP

**Merge:** DISCOVER → READ_JSON+STATE → COLLECT → MERGE_JSON → WRITE_JSON → VALIDATE_JSON → WRITE_STATE → VALIDATE_STATE → SEED GATE → STOP

**Actions job:** ROUTE → TRIGGER → POLL → READ MARKER → WRITE_STATE → VALIDATE_STATE → STOP

**Collect failure:** WRITE_STATE (`latest_attempt` only) → VALIDATE_STATE → STOP. Do not wipe last-known-good json.

## Reference routing

- Create/merge inventory: `references/inventory.md`
- Paths and reader contract: `references/workspace-contract.md`
- State: `references/sync-state.md`
- Workflows: `github-actions-mcp`
