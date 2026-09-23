# Produce — Network Design

Paths: **`workspace-handoff`**. Do not `execute_command`.
Do not invent files.

Every JSON artifact requires top-level `keys`: the deduplicated union derived
only from structured entities in that artifact, or `[]`. Never infer from
prose. Allowed prefixes are
`device|interface|site|service|test|control|incident|change`; use `site:` for
location and `interface:<device>/<interface>` when the device is known.
Preserve nested keys. Markdown is exempt; `state/design.json` carries its keys.

| File | Kind | When |
|------|------|------|
| `state/design.json` | state | Every completed design; replace in full. Schema: `schemas/design-plan.schema.json`. |
| `design/roadmap.md` | observation | Every completed design. Replace in full. |
| `test-request.json` | request | When they asked to hand a suite to Compliance Test. Schema: `schemas/test-request.schema.json`. |
| `branch-deploy-summary.json` | result | When they asked to summarize a branch deploy. Schema: `schemas/branch-deploy-summary.schema.json`. |

Do not write `state/health.json`, `state/lifecycle.json`,
`lifecycle/roadmap.md`, `compliance/*`, `inventory/*`,
`health/`, or `state/servicenow.json`.
