# Tools — Network Ops

Exact names. Do not invent tools. `write_file` is only for
`state/network-ops.json`. `read_file` for `state/health.json` and the
refs it names.

| Tool | When |
|------|------|
| `github_list_files` | List `inventory/configs` on `dev`; resolve target/peer paths only from returned entries. |
| `github_get_file` | Read the relevant target and passing/canonical peer configs on `dev` to decide exact syntax. |
| `github_create_pull_request` | After Pipeline Monitor returns live `pass`. `source_branch=dev`, `target_branch=main`. |
| `github_merge_pull_request` | After the PR exists. `merge_method=merge`. Do not delete `dev`. |
| `github_list_pull_requests` | Only if create failed and you need the open `dev` → `main` number. |
| `grafana_annotations` | `action="create"` once, only after the PR merged: `text`, `tags=["change:<sha>", "device:<d>", …]`. Never `list`, never in `recommend` / `review`. `references/blast-radius.md`. |

Network Ops may list/get configs but never put them. GitHub GitOps Change owns
`github_put_file`. Pipeline Monitor owns Actions tools. Network Ops must not
query subagent status. The Grafana MCP is attached for the one annotation
write; no other `grafana_*` tool is called. Grafana not attached → the merge
stands, `change.annotation_ref` null, one `Gaps:` line.
