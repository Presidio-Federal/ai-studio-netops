---
name: compliance-test-runner
version: "1.8.2"
description: "v1.8.2 — Write test and compliance evidence directly without Code Execution."
---

# Compliance test runner skill

You run the suite and report. You do not sync configs, deploy topology, or
file tickets.

## Route

| Intent | How |
|--------|-----|
| Run live/static/compliance tests | `github-actions-mcp` — `test.yml` |
| Status of a run | list/get — do not trigger |
| Author a new check | not this skill — Compliance Author |

## Hard boundaries

Do not call `actions_run_trigger`, `get_file_contents`, or
`repository_dispatch`. This MCP uses `github_run_action`,
`github_list_action_runs`, `github_get_action_run`,
`github_get_action_job_logs`.

Do not write `runs/`, `servicenow/`, `inventory/`, `risk/`, or `lab-access.json`.
Do not invent a run id. Do not treat a green job as a pass.
Write every JSON record directly with the built-in workspace file tool. Never
use Code Execution, `execute_command`, helper/build scripts, shell commands,
or `Internal directory`. Do not generate or transform workspace records
indirectly.

Default lab is **dev**. A Dev pass is not production evidence.

## Files

Paths and catalog: **`workspace-handoff`**. When/how: `references/workspace-contract.md`.

Skill resources — use exactly:

- `references/workspace-contract.md`
- `references/scope.md`
- `references/run.md`
- `schemas/testing-run.schema.json`
- `schemas/testing-state.schema.json`
- `schemas/compliance-test-visit.schema.json`
- `schemas/compliance-test-metadata.schema.json`
- `examples/testing-run.example.json`
- `examples/testing-state.example.json`
- `examples/compliance-test-visit.example.json`
- `examples/compliance-test-metadata.example.json`

Every `results.ran[]` and `results.not_applicable[]` row carries `keys`:
`test:<check-id>` and exact `device:<inventory-name>`. The report may render
the check as `suite/check-id`; use the final `check-id` so it joins the
catalog and coverage rows. Add `control:<id>` only when the report or
published catalog supplies that mapping. No whitespace after `:`. Do not
infer entities.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machine

READ_INVENTORY → TRIGGER → LIST_RUN → POLL → READ_MARKER → WRITE_RUN →
WRITE_TESTING_STATE → WRITE_COMPLIANCE_VISIT_IF_SCOPED → STOP

Never skip READ_INVENTORY. Never invent or prefix a hostname (`WAN-01` stays
`WAN-01`). `test-request.json` is optional. Missing → continue.

## Reference routing

- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
- Lab, mode, tags: `references/scope.md`
- Trigger/poll/extract: `references/run.md`
- Workflows: `github-actions-mcp`
