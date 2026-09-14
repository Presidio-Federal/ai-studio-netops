# GitHub tools — Network Ops

Exact names. Do not invent tools.

| Tool | When |
|------|------|
| `github_list_files` | List `inventory/configs` **`ref=dev`**. Match hostname to `entries[].name`. Use `entries[].path`. |
| `github_get_file` | Read that listed path. **`ref=dev` first.** Keep `sha`. |
| `github_put_file` | Same listed path. Full file text. **`ref=dev` always.** `message` required. Pass `sha` from get. |
| `github_create_pull_request` | After live CI pass. `source_branch=dev`, `target_branch=main`. |
| `github_merge_pull_request` | After the PR exists. `merge_method=merge`. Do not delete `dev`. |
| `github_list_pull_requests` | Only if create failed and you need the open `dev` → `main` number. |

Pipeline Monitor owns Actions list/run/logs.
