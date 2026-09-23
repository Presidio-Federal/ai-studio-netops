# Produce — Modernization Analysis

Paths: **`workspace-handoff`**. Do not `execute_command`. Do not
invent files.

| File | Kind | When |
|------|------|------|
| `state/lifecycle.json` | state | Every run. Create if missing. Merge identity; copy through research. Write `guidance`, `assessment`, and `plan`. When they named a SKU, `selected_replacement` on that row. Stamp `updated_at`. Plan invoke also writes `recommendations[]`. |
| `lifecycle/roadmap.md` | observation | Plan/roadmap after `guidance.answers` is non-empty. Replace in full. Follow `references/roadmap.md`. |

Do not write `lifecycle/items/`. Do not write
`state/modernization.json`. Do not write `health/` or
`state/health.json`.

## Canonical keys

Every structured JSON write requires top-level `keys`: an
array, unique, empty allowed. Values match exactly
`^(device|interface|site|service|test|control|incident|change):[^ ].*$`.
Write the deduplicated union supported by explicit payload
identity fields. For `state/lifecycle.json`, derive
`device:<name>` only from `items[].devices`; use `[]` when
there are none. Keep nested identity fields. Do not create keys
for PIDs, recommendation IDs, replacement SKUs, roadmap refs,
prose, or source refs. Never infer a device or site.
