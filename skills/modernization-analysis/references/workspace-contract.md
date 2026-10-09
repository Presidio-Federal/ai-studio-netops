# Produce — Modernization Analysis

Paths: **`workspace-handoff`**. The script writes
`state/lifecycle.json`. You write `inventory/assets/roadmap.md` after
answers exist. Do not invent files.

| File | Kind | When |
|------|------|------|
| `state/lifecycle.json` | state | Every run. Create if missing. Merge identity from `inventory/assets/devices.json` `product_id` when set, else SoT / prod. Copy through research. |
| `inventory/assets/devices.json` | configuration | Every run. Seed from `inventory/prod.json`. Copy `product_id` and `serial` through. |
| `inventory/assets/roadmap.md` | observation | Plan/roadmap after `guidance.answers` is non-empty. Replace in full. Follow `references/roadmap.md`. |

Do not write `inventory/assets/<pid>.json`. Do not write
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
