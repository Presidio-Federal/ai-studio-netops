# GitHub tools — Network Ops

Exact names. Do not invent tools. `write_file` is only for
`state/network-ops.json`.

| Tool | When |
|------|------|
| `github_create_pull_request` | After Pipeline Monitor returns live `pass`. `source_branch=dev`, `target_branch=main`. |
| `github_merge_pull_request` | After the PR exists. `merge_method=merge`. Do not delete `dev`. |
| `github_list_pull_requests` | Only if create failed and you need the open `dev` → `main` number. |

GitHub GitOps Change owns config tools. Pipeline Monitor owns Actions tools.
Network Ops must not call either tool family or query subagent status.
