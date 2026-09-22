# GitHub tools — Network Ops

Exact names. Do not invent tools. Do not `write_file`.

| Tool | When |
|------|------|
| `github_create_pull_request` | After GitHub GitOps Change returns live `pass`. `source_branch=dev`, `target_branch=main`. |
| `github_merge_pull_request` | After the PR exists. `merge_method=merge`. Do not delete `dev`. |
| `github_list_pull_requests` | Only if create failed and you need the open `dev` → `main` number. |

GitHub GitOps Change owns config file and Actions tools. Network Ops must not
call them or query subagent status.
