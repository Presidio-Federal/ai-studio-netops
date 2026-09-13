# GitHub Actions tools

Exact names. Do not invent tools.

| Tool | When |
|------|------|
| `github_list_action_runs` | Find the run. Pass `workflow` (`apply.yml` or `test.yml`), `branch` = git ref, `limit=5`. |
| `github_run_action` | Dispatch **once** if no run for that commit yet. `workflow` + `ref`. No target input on `apply.yml`. |
| `github_get_action_run` | Poll until `status` is `completed`. Returns jobs (need `id` for logs). |
| `github_get_action_job_logs` | Read the marker. `tail_lines=200`. |

Network Ops owns `github_get_file` / `github_put_file` / PR merge.
