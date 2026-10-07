---
name: compliance-test-runner
version: "1.12.6"
description: "v1.12.6 — Write the compliance visit as counts plus failures by device, and keep passes on the counts."
---

# Compliance test runner skill

You run the suite and report. You do not sync configs, deploy topology, or
file tickets.

## Route

| Intent | How |
|--------|-----|
| Run live/static/compliance tests | `scripts/run_suite.py run` under `mcp_orchestration` |
| Status of a run already started | same script with `--run-id` — do not dispatch again |
| Author a new check | not this skill — Compliance Author |

## Hard boundaries

Do not call `actions_run_trigger`, `get_file_contents`, or
`repository_dispatch`. This MCP uses `github_run_action`,
`github_list_action_runs`, `github_get_action_run`,
`github_get_action_job_logs`.

Do not write `runs/`, `servicenow/`, `inventory/`, `risk/`, or `lab-access.json`.
Do not invent a run id. Do not treat a green job as a pass.
Do not write a script and do not hand-parse the job log. Run the pre-built
`scripts/run_suite.py`. It dispatches, polls, and writes the records.
If stderr says `hai_mcp unavailable`, follow `references/run.md` by hand.

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

## Run script

Copy the path Studio shows for `compliance-test-runner/scripts/run_suite.py`.
Do not retype it and do not `cd`. `execution_type` is `mcp_orchestration`.
`timeout` is 60. Not 300. Not 400. The script checks once and returns.
One command is one `python3` invocation. No `for`, no `while`, no
`sleep`. A `running` line is answered with one new command, still
timeout 60.

```text
python3 <skill>/scripts/run_suite.py run --workspace <file_explorer> --environment <dev|prod> --suites <suites> --devices <names> --tags <tags> --mode live --allow-all <true|false> --production-authorized <true|false> --reason <why>
```

A compliance suite stays `--mode live` and `--suites compliance`. The job
prints a static report and a live report. The script writes both into the
visit. A `running` line includes `github_status` from that one check.
It includes `phase` only for `running static tests` or `running live tests`.
There is no poll loop. A finished run writes the visit before the
script returns. The next command repeats the same flags and adds
`--run-id`. Do not drop `--workspace` or `--suites`. Pass `--phase`
only when the line has one of those two phases. Do not invent a phase.
The last stdout line is the result. Do not read the files to fill the reply.

The visit is filled from `NETWORK_TEST_RESULT_JSON`, the line the emit
step prints at the end of the job. The job summary on the Actions page
and the uploaded artifact are the same result in the other two places.
The log tool is how this script reads that line.

Every `results.ran[]` and `results.not_applicable[]` row carries `keys`:
`test:<check-id>` and exact `device:<inventory-name>`. A compliance row
also carries `plane` `live` or `static`. The report may render
the check as `suite/check-id`; use the final `check-id` so it joins the
catalog and coverage rows. Add `control:<id>` only when the report or
published catalog supplies that mapping. No whitespace after `:`. Do not
infer entities.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## State machine

The script runs TRIGGER → LIST_RUN → POLL → READ_MARKER → WRITE_RUN →
WRITE_TESTING_STATE → WRITE_COMPLIANCE_VISIT_IF_SCOPED. The agent only
resolves scope, then reads the summary line.

Never skip READ_INVENTORY. Never invent or prefix a hostname (`WAN-01` stays
`WAN-01`). `test-request.json` is optional. Missing → continue.

## Reference routing

- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
- Lab, mode, tags: `references/scope.md`
- Trigger/poll/extract: `references/run.md`
- Workflows: `github-actions-mcp`
