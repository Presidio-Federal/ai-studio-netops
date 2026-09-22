# GitHub tools — GitOps Change

Exact names. Do not invent tools.

| Tool | Use |
|------|-----|
| `github_list_files` | `path=inventory/configs`, `ref=dev`; resolve targets from returned entries. |
| `github_get_file` | Read each listed target path on `ref=dev`; keep content and SHA. |
| `github_put_file` | Put the minimally changed full file to the same path, `ref=dev`, with its retrieved SHA and a bounded commit message. |
| `github_list_action_runs` | Find `apply.yml` on branch `dev` for the final put SHA. |
| `github_get_action_run` | Poll the exact run until completed. |
| `github_get_action_job_logs` | Read only enough log tail to find `# Network test report`. |

Do not call `github_run_action`, PR tools, merge tools, or workspace file tools.
