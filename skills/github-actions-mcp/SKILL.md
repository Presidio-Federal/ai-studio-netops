---
name: github-actions-mcp
version: "4.5.0"
description: "v4.5.0 — watch_run.py checks apply.yml or test.yml once per command and writes the operation-run. running means the same command with --run-id."
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
| Watch a named workflow for a commit | `scripts/watch_run.py watch` under `mcp_orchestration` |
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
- Do not invent a run id. Do not put `sleep`, `for`, or `while` in the
  agent command. The script checks the run once. `running` is the same
  command plus `--run-id`.
- Pipeline Monitor is read-only and never calls `github_run_action`.

## Operations record

After a terminal watch result, Pipeline Monitor writes one concise
`operational/runs/YYYY-MM-DDTHH-MM-SSZ.json`. GitOps Change writes a separate
commit-only record with `result=submitted`; it never watches Actions. Follow
`schemas/operation-run.schema.json` and
`examples/operation-run.example.json`.

Write the result, run URL, one marker line, commit SHA, and top-level `keys`
equal to the deduplicated union of exact keys supported by structured fields,
or `[]`; never infer from prose. Allowed prefixes are
`device|interface|site|service|test|control|incident|change`. Location is
`site:`. When a device is known, use `interface:<device>/<interface>`. Keep
any nested `keys`.
The GitOps Change record may include changed paths, a one-line summary, and
`interfaces[]` — `<device>/<interface>` for every interface stanza the
prescription's Scope named on a written device (empty for a global scope);
each adds an `interface:` key. With `devices[]` and `git.commit_sha` that is
the change → device / interface edge as columns; the record carries no
`relations[]`.
Never write config bodies, patches, or full logs. Do not write root `runs/`.
Map result to envelope status: `pass` → `ok`; `fail` / `failed` → `failed`;
`submitted` → `ok`; `blocked`, `unknown`, and `no_change` keep the same word.

## Watch

`scripts/watch_run.py` owns the tool calls. Copy the Studio path.
`--workspace` is the `file_explorer` directory. `execution_type` is
`mcp_orchestration`. `timeout` is 60. One `python3`. The last stdout
line is the result.

```text
python3 <skill>/scripts/watch_run.py watch --workspace <file_explorer> --workflow <apply.yml|test.yml> --ref <dev|main> --sha <sha>
```

`running` → the same command plus `--run-id`. That call writes nothing.
A finished call writes `operational/runs/<stamp>.json`.

Need workflow, git ref, and commit sha. Missing any input: `unknown`.
Do not read a workspace fallback or pick the newest run.

If stderr says `hai_mcp unavailable`, do this by hand. Any other
failure: stop. Do not poll by hand.

1. `github_list_action_runs(workflow=<file>, branch=<ref>, limit=5)`
2. Pick the run whose `sha` matches the asked commit. If none,
   repeat step 1 up to three list calls total. Still none → `unknown`;
   do not trigger.
3. `github_get_action_run(run_id=<integer>)` once. Still running →
   return `running` and call again later. Do not sleep in the command.
4. `github_get_action_job_logs` on the job id (`tail_lines=20000`).
   A run id is not a job id.
5. Parse `# Network test report`. Live fail → `fail`. A live pass
   with a static fail is still `pass`. No live block → `unknown`.

## Reference routing

- Tools: `references/tools.md`
- Refs, markers, result words: `references/workflows.md`
