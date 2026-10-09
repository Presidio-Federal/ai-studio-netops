# GitHub Actions tools

`scripts/watch_run.py` calls these. Do not invent tools. The agent
runs that script. These rows are the manual fallback when stderr says
`hai_mcp unavailable`.

| Tool | When |
|------|------|
| `github_list_action_runs` | Find the run. Pass `workflow` (`apply.yml` or `test.yml`), `branch` = git ref, `limit=5`. |
| `github_run_action` | Only an explicit ad-hoc workflow owner may dispatch once. Pipeline Monitor never uses it; `apply.yml` watches are trigger-driven. |
| `github_get_action_run` | Poll until `status` is `completed`. Returns jobs (need `id` for logs). |
| `github_get_action_job_logs` | Read the marker. The script passes `tail_lines=20000` and an integer job id, never the run id. |

GitHub GitOps Change owns config list/get/put. Network Ops owns PR merge.
