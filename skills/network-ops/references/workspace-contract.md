# Produce — Network Ops

Paths, envelope, catalog: **`workspace-handoff`**.
Write schema: `schemas/network-ops-state.schema.json`.

Every completed invoke replaces **`state/network-ops.json`**.
Do not write git configs into the workspace. Do not write
`testing/`, `compliance/`, `design/`, or inventory.

MiniMax sandbox: if Access denied lists `file_explorer`, retry
**once** as `file_explorer/state/network-ops.json` (same file).
Same prefix for inventory reads. Never `/app/state/...`. Never
`/workspace/` on built-in tools.

## When to write

| File | Kind | When |
|------|------|------|
| `state/network-ops.json` | state | Every completed recommend or implement; replace in full. |

Envelope `status`:

| Word | Means |
|------|-------|
| `recommended` | Recommendation only, or implement stopped before commit |
| `committed` | On git `dev`; CI not finished |
| `ci_failed` | Live marker failed or unknown |
| `merged` | PR merged to `main` |
| `blocked` | Test bug, missing SoT, or merge tools failed |
| `failed` | Could not read evidence or git |

`source_agent` is `network-ops`. `next_action` is one line or JSON
`null` — never the string `"none"`.

`finding.kind` is `missing_config`, `test_bug`, or `other`.
`git.ref` is `dev` until merged.

## After write

```text
python3 /skills/user/network-ops/scripts/validate_network_ops.py /workspace/state/network-ops.json
```

Skip if script missing. Never `find /`.
