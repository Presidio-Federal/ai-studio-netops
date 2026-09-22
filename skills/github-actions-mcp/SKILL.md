---
name: github-actions-mcp
version: "4.1.0"
description: "v4.1.0 — Separate git refs, workflow triggers, and target environments. Judge job-log markers, not green checks."
---

# GitHub Actions skill

You watch or trigger GitHub Actions. Git refs, workflow triggers, and target
environments are separate concepts. Git `dev` is proposed configs,
`compliance` is candidate tests, and `main` is the published SoT and testbed.
CML Dev and Prod labs are environments — not branches.

Exact tools: [references/tools.md](references/tools.md).
Workflows and markers: [references/workflows.md](references/workflows.md).

## Route

| Intent | How |
|--------|-----|
| Watch / poll a named workflow for a commit | list runs on that ref → get run → job logs → marker |
| No run yet for that commit | `github_run_action` **once** on that ref, then list |
| Ad-hoc `test.yml` | Compliance Test owns the extract files. You may watch. |
| Candidate test push | Automation validates `compliance`; do not manually substitute an ad-hoc run |

## Hard boundaries

- Workflows you may name: `apply.yml`, `test.yml`. No others.
- Do not send a target / environment / lab input to `apply.yml`.
  The ref is CI (`dev`) or CD (`main`).
- `test.yml` environment comes from its verified inputs, not from the git ref.
  Use the ref required by the automation repository; do not infer a lab from it.
- Judge `# Network test report` in the log. A green check with
  failed live tests is `fail`. Static fail is not a live fail.
- Do not commit. Do not merge. Do not `github_put_file`.
- Do not invent a run id. Do not sleep-script; call
  `github_get_action_run` again until `completed`.

## Watch

Need workflow, git ref, and commit sha. Missing sha: read
`state/network-ops.json` `git.commit_sha` once (Access denied →
`file_explorer/state/network-ops.json`). Still missing:
`unknown` — do not pick the newest run.

1. `github_list_action_runs(workflow=<file>, branch=<ref>, limit=5)`
2. Pick the run whose `sha` matches the asked commit. If none,
   `github_run_action(workflow=<file>, ref=<ref>)` once, then list
   again. Still none → `unknown`.
3. `github_get_action_run(run_id=...)` until `status=completed`.
4. `github_get_action_job_logs` on the job that printed the marker
   (`tail_lines=200`).
5. Parse `# Network test report`. Reply with the result word.

## Reference routing

- Tools: `references/tools.md`
- Refs, markers, result words: `references/workflows.md`
