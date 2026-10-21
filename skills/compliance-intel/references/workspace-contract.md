# Produce — Compliance intel

Paths, Kind, catalog: **`workspace-handoff`**.
Write from this skill’s schemas and examples. Do not invent files.

Built-in `read_file` / `write_file`: catalog rows. Do not invent
prefixes. `write_file` creates parents. Never `mkdir`.

`execute_command` on a scan is `scripts/scan_catalog.py scan` under
`mcp_orchestration`. The script gets the job catalog and the bridge.
Do not `write_file` either file. Do not pass the catalog on stdin.

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

The scan script reads `inventory/prod.json` when present and puts
platform, role, and tags on `estate.devices`. It gets
`catalog/job-catalog.json` and `tests/compliance/matrix/test-bridge.yml`
from `main`. Do not `write_file` the job catalog, matrix, bridge, or a
scratch input file.

```text
python3 <skill>/scripts/scan_catalog.py scan --workspace <file_explorer>
```

`Internal directory` is never a script path. Built-in file tools use
workspace-relative paths; `execute_command` uses `/workspace/...`. No
`--output`. Never `find`. Do not run six `family` calls on a standard scan.

Do not write `testing/`, `risk/`, `runs/`, a root `compliance.json`, or `.py`.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
