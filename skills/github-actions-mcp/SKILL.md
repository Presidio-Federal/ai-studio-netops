---
name: github-actions-mcp
version: "4.0.2"
description: "v4.0.2 — GitHub Actions by git ref: apply.yml (CI=dev, CD=main) and test.yml. Judge the job-log marker, not the green check. Require commit sha."
---

# GitHub Actions skill

You watch or trigger GitHub Actions. CI vs CD is the **git ref**,
not a lab/target input. Git `dev` is proposed configs. git `main`
is Prod SoT. CML Dev and Prod labs are topologies — not branches.

Exact tools: [references/tools.md](references/tools.md).
Workflows and markers: [references/workflows.md](references/workflows.md).

## Route

| Intent | How |
|--------|-----|
| Watch / poll a named workflow for a commit | list runs on that ref → get run → job logs → marker |
| No run yet for that commit | `github_run_action` **once** on that ref, then list |
| Ad-hoc `test.yml` | Compliance Test owns the extract files. You may watch. |

## Hard boundaries

- Workflows you may name: `apply.yml`, `test.yml`. No others.
- Do not send a target / environment / lab input to `apply.yml`.
  The ref is CI (`dev`) or CD (`main`).
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
