# GitHub Actions tools

Exact names. Do not invent tools.

| Tool | When |
|------|------|
| `github_list_action_runs` | Find the run. Pass `workflow` (`apply.yml` or `test.yml`), `branch` = git ref, `limit=5`. |
| `github_run_action` | Only an explicit ad-hoc workflow owner may dispatch once. Pipeline Monitor never uses it; `apply.yml` watches are trigger-driven. |
| `github_get_action_run` | Poll until `status` is `completed`. Returns jobs (need `id` for logs). |
| `github_get_action_job_logs` | Read the marker. `tail_lines=200`. |

GitHub GitOps Change owns config list/get/put. Network Ops owns PR merge.
