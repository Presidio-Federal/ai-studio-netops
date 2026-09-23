# GitHub tools — GitOps Change

Exact names. Do not invent tools.

| Tool | Use |
|------|-----|
| `github_list_files` | `path=inventory/configs`, `ref=dev`; resolve targets from returned entries. |
| `github_get_file` | Read each prescribed target on `ref=dev`; keep content and SHA. |
| `github_put_file` | Put the minimally changed full file to the same path, `ref=dev`, with its retrieved SHA and a bounded commit message. |

Do not call Actions, PR, or merge tools. Use the workspace only for the
concise operation record.
