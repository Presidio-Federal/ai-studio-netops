# GitHub tools — GitOps Change

Exact names. Do not invent tools.

| Tool | Use |
|------|-----|
| `github_list_files` | `path=inventory/configs`, `ref=dev`; resolve targets from returned entries. |
| `github_get_file` | Inspect: read resolved targets/peers. Apply: read each target on `ref=dev` and keep content/SHA. |
| `github_put_file` | Put the minimally changed full file to the same path, `ref=dev`, with its retrieved SHA and a bounded commit message. |

Do not call Actions, PR, or merge tools. Inspect mode never calls workspace
file tools. Apply uses the workspace only for its concise operation record.
