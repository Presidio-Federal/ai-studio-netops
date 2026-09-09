# Produce — Ops Network Sync

Paths, envelope, catalog: **`workspace-handoff`** (must be attached).
Write schemas live in this skill.

## Roles

| Store | Role |
|-------|------|
| `inventory/prod.json` `inventory/dev.json` | Canonical accumulating inventories and published access snapshots. Merge; keep unknown keys. |
| `state/network-sync.json` | Replaceable coordination projection. Not an inventory. |
| GitHub Actions runs and logs | Durable workflow evidence. Raw logs and workflow configurations do not belong in the workspace. |

## Reader contract (public)

Readers may rely on **only**:

- State envelope (`status` `headline` `next_action`) and latest operation
  (`operation_id` `operation` `started_at` `completed_at`)
- Inventory snapshot `snapshot_id`, `path`, freshness (`collected_at`
  `published_at` `expires_at`; current iff `now < expires_at`), `status`,
  `coverage`
- Documented device identity and access: `name` `platform` `role` `tags`
  `operational_state` `agent_access` `access.restconf` / `ssh` (`host`
  `port` `protocol` `credential_ref`) and CML `source_metadata` ids/tags
- Workflow `result`, `run_id`, `html_url`, `updated_at` (plus `workflow`
  and `environment`)
- `gaps` and `next_action` (`null` when there is no action)

Do not treat extra keys as a reader API. Do not treat stale PAT as
current. Do not treat a failed `latest_attempt` as “zero devices.”

## When to write

| File | When |
|------|------|
| `inventory/prod.json` | Create if missing. **Merge** on collect — do not wipe unknown keys. Never write a failed collect over last-known-good. |
| `inventory/dev.json` | Same for Dev. |
| `inventory/infra-sot.json` | **Not yours.** Ops NetBox SoT writes the id map. After prod collect, compare `seed` only to decide whether to invoke that agent. |
| `state/netbox.json` | **Not yours.** Ops NetBox SoT writes the infra summary. |
| `state/network-sync.json` | After every invocation, **last**, after inventory validate (or failed attempt only). |

Do not write `lab-access.json`, `runs/`, `servicenow/`, or `vuln-report.json`.
Do not run `vuln-scan.yml`. Git `inventory/configs/` is not this workspace.

Create vs merge and interview: `references/inventory.md`.
State fields: `references/sync-state.md`.

## Publication sequence

1. Read canonical inventory and current state.
2. Collect source evidence.
3. Merge without discarding unknown or user-authored fields.
4. Build, write, read back, validate inventory JSON.
5. Publish `state/network-sync.json` last (`snapshot_id` must match the file).
6. Read back and validate state (`pair` when both exist).

## After write

```text
python3 /skills/user/ops-network-sync/scripts/validate_network_sync.py inventory /workspace/inventory/prod.json --as-of <collected_at>
python3 /skills/user/ops-network-sync/scripts/validate_network_sync.py inventory /workspace/inventory/dev.json --as-of <collected_at>
python3 /skills/user/ops-network-sync/scripts/validate_network_sync.py state /workspace/state/network-sync.json
python3 /skills/user/ops-network-sync/scripts/validate_network_sync.py pair /workspace/state/network-sync.json /workspace/inventory/prod.json /workspace/inventory/dev.json --as-of <collected_at>
```

`inventories.*.current_snapshot.path` is workspace-relative (`inventory/prod.json`).
Skip validate if `/skills` is empty. Never `find /`.
