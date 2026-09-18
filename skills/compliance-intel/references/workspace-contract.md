# Produce — Compliance intel

Paths, Kind, catalog: **`workspace-handoff`**.
Write from this skill’s schemas and examples. Do not invent files.

Built-in `read_file` / `write_file`: catalog row
(`compliance/intel.json`). Never `/workspace/` on those tools. Never
`Internal directory`, `/shared_workspace/`, `sessions/`, `/app/`,
or `tool_results`. `write_file` creates parents. Never `mkdir`.

If Access denied and Allowed paths include `file_explorer`, retry
**once** as `file_explorer/<catalog row>` (same file, no UUID).

`execute_command` is fingerprint then (when `framework_rescan`) the
query script. Stdout only. If fingerprint must see a catalog file,
use `/workspace/compliance/coverage.json` or
`/workspace/compliance/metadata.json` or
`/workspace/inventory/prod.json` on that command — do not
`write_file` those prefixes. Catalog JSON is stdin (`--catalog -`).

Write when that artifact changed this visit:

| File | Kind | When |
|------|------|------|
| `compliance/coverage.json` | snapshot | Framework rescan, estate rejudge, or catalog join. Replace in full. |
| `compliance/intel.json` | result | Candidates or delta changed (including reconcile/refill). Replace in full. Skip if unchanged. |
| `compliance/metadata.json` | metadata | After a successful evaluation. Fingerprints only. Replace in full. |

Read-only: `inventory/prod.json` when present (estate for relevance).
Git `catalog/job-catalog.json` is read with `github_get_file`. Do not
`write_file` the catalog, matrix, bridge, or a scratch `_git_input.json`.

```text
github_get_file(path="catalog/job-catalog.json", ref="main")
python3 /skills/user/compliance-intel/scripts/fingerprint_inputs.py --estate /workspace/inventory/prod.json --prior /workspace/compliance/metadata.json --coverage /workspace/compliance/coverage.json --catalog -
python3 /skills/user/compliance-intel/scripts/query_sources.py family AC
```

Family queries only when fingerprint stdout `work.framework_rescan`
is true. No `--output`. Never `find`. Never `build_coverage.py` in Studio.

Do not write `testing/`, `risk/`, `runs/`, a root `compliance.json`, or `.py`.
