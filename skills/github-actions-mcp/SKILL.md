---
name: github-actions-mcp
version: "4.2.1"
description: "v4.2.1 — Read-only exact-SHA pipeline watches; only an explicit ad-hoc test owner may trigger."
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
| No run yet for a watched commit | List up to three times, then `unknown`; watcher never triggers |
| Explicit ad-hoc `test.yml` | Compliance Test may trigger once, then watch exact run |
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
- Pipeline Monitor is read-only and never calls `github_run_action`.

## Watch

Need workflow, git ref, and commit sha. Missing any input: `unknown`.
Do not read a workspace fallback or pick the newest run.

1. `github_list_action_runs(workflow=<file>, branch=<ref>, limit=5)`
2. Pick the run whose `sha` matches the asked commit. If none,
   repeat step 1 up to three list calls total. Still none → `unknown`;
   do not trigger.
3. `github_get_action_run(run_id=...)` until `status=completed`.
4. `github_get_action_job_logs` on the job that printed the marker
   (`tail_lines=200`).
5. Parse `# Network test report`. Reply with the result word.

## Reference routing

- Tools: `references/tools.md`
- Refs, markers, result words: `references/workflows.md`
