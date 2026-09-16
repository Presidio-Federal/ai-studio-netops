# Produce — Compliance intel

Paths, Kind, catalog: **`workspace-handoff`**.
Write from this skill’s schemas and examples. Do not invent files.

Built-in `read_file` / `write_file`: catalog row
(`compliance/intel.json`). Never `/workspace/` on those tools. Never
`Internal directory`, `/shared_workspace/`, `sessions/`, `/app/`,
or `tool_results`. `write_file` creates parents. Never `mkdir`.

If Access denied and Allowed paths include `file_explorer`, retry
**once** as `file_explorer/<catalog row>` (same file, no UUID).

`execute_command` is only the query script (stdout). If it must see a
catalog file, use `/workspace/compliance/coverage.json` on that command
only — do not `write_file` that prefix.

Every completed intel run writes **only**:

| File | Kind | When |
|------|------|------|
| `compliance/coverage.json` | snapshot | Every run. Replace in full. |
| `compliance/intel.json` | result | Every run, even if `candidates` is empty. |

Read-only: `inventory/prod.json` when present (estate for relevance).
Git `catalog/job-catalog.json` is read with `github_get_file`. Do not
`write_file` the catalog, matrix, bridge, or a scratch `_git_input.json`.

```text
github_get_file(path="catalog/job-catalog.json", ref="main")
python3 /skills/user/compliance-intel/scripts/query_sources.py family AC
```

No `--output`. Never `find`. Never `build_coverage.py` in Studio.

Do not write `testing/`, `risk/`, `runs/`, a root `compliance.json`, or `.py`.
