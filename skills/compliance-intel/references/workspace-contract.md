# Produce — Compliance intel

Paths, Kind, catalog: **`workspace-handoff`**.
Write from this skill’s schemas and examples. Do not invent files.

Built-in `read_file` / `write_file`: catalog rows. Do not invent
prefixes. `write_file` creates parents. Never `mkdir`.

`execute_command` is the query script (stdout). Job catalog is
`github_get_file` — do not `write_file` it. Pass that JSON on
stdin to `unresolved --catalog -`.

Every completed intel run writes **only**:

| File | Kind | When |
|------|------|------|
| `compliance/coverage.json` | snapshot | Every run. Replace in full. Accumulated rows + this run. |
| `compliance/intel/<stamp>.json` | observation | Every run. Append-only visit summary with metrics and `vs_prior`. |
| `compliance/intel.json` | result | Every run, even if `candidates` is empty. |
| `compliance/metadata-intel.json` | metadata | Every run. Replace; points to the latest Intel visit. |

Coverage rows and candidates include all source-supported
`workspace-handoff` `type:name` keys. Use exact identifiers with no whitespace
after `:`; never add device keys to framework/catalog judgments.

Read metadata first and open its `last_visit_id`; do not list
`compliance/intel/`. Write the visit before advancing metadata. Keep ten
stamps and delete older ones only after the new visit and metadata are valid.

Read-only: inventory when present (estate for relevance).
Git `catalog/job-catalog.json` is read with `github_get_file`. Do not
`write_file` the job catalog, matrix, bridge, or a scratch input file.

```text
github_get_file(path="catalog/job-catalog.json", ref="main")
python3 /skills/user/compliance-intel/scripts/query_sources.py unresolved --limit 20 --catalog - --coverage compliance/coverage.json --intel compliance/intel.json
```

No `--output`. Never `find`. Do not run six `family` calls on a standard scan.

Do not write `testing/`, `risk/`, `runs/`, a root `compliance.json`, or `.py`.
