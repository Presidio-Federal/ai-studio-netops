# Produce — Ops ServiceNow Operator

Paths, envelope, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Board procedure: `references/state.md`.
Marker: `references/metadata.md`.

## When to write

| File | When |
|------|------|
| `servicenow/metadata-lab.json` | Marker resolve, or last-visit after a successful find/get |
| `servicenow/cases/active.json` | Every invoke — open in-scope cases you filed/updated, cap 5 |
| `servicenow/cases/index.json` | Every invoke — all cases you have touched |
| `state/servicenow.json` | Every invoke — current board + `history[]` (cap 20) |
| `servicenow/requests/**` | Mutation queue only |

Read other agents' evidence. Never overwrite it. Never copy
ServiceNow tables into the workspace. Do not write `health/`,
`servicenow/trends/`, or top-level `cases/`. Do not write
under `automations/schedules/`.

`write_file` creates parents. Never `mkdir`.

Device names on a case must match inventory labels in
`inventory/prod.json`.

## Queue (mutations)

1. At most one request per invoke unless they asked otherwise.
2. Claim: move `pending/` → `claimed/`. Do not edit pending in place.
3. Validate claimed request. Read every `source_refs` (workspace-relative).
4. Missing auth → `needs-approval/`. Success → `completed/`. Failure → `failed/`.
5. Refresh cases + rewrite `state/servicenow.json`.
6. Read final files back before reporting.

## After write

```text
python3 /skills/user/ops-snow-mcp/scripts/validate_handoff.py request /workspace/servicenow/requests/claimed/req-123.json
python3 /skills/user/ops-snow-mcp/scripts/validate_handoff.py state /workspace/state/servicenow.json
python3 /skills/user/ops-snow-mcp/scripts/validate_handoff.py active /workspace/servicenow/cases/active.json
python3 /skills/user/ops-snow-mcp/scripts/validate_handoff.py index /workspace/servicenow/cases/index.json
```

Skip if the script is missing. Never `find /`.
`source_refs` must be workspace-relative. Strip `workspace/` or `/workspace/`.
