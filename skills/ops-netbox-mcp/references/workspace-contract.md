# Produce — Ops NetBox SoT

Paths, envelope, catalog: **`workspace-handoff`**.
Write schemas live in this skill.

## When to write

| File | When |
|------|------|
| `inventory/infra-sot.json` | Every bootstrap, audit, or reconcile — id map (`mode` required) |
| `state/netbox.json` | Every invoke — summary the next agent reads first (`mode` required) |

Do not write `state/network-sync.json`, yaml, `prod.json`, `lab-access.json`,
or `runs/`.

Read-only: `inventory/prod.json` (handoff rely-on). Missing → stop (Ops
Network Sync). Do not open yaml.

Populate writes: `references/populate.md`. Modes: `references/modes.md`.
Board: `references/state.md`.

## After write

`write_file` then validate. Skip if `/skills` empty. Never `find`.

```text
python3 /skills/user/ops-netbox-mcp/scripts/validate_netbox.py snap /workspace/inventory/infra-sot.json
python3 /skills/user/ops-netbox-mcp/scripts/validate_netbox.py state /workspace/state/netbox.json
```
