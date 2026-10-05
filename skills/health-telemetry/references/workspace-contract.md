# Produce — Health Telemetry

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not invent files.

One visit rewrites the NetFlow board and writes **at most one** new
observation. Do not write `state/`. Do not write the Splunk board
or `health/splunk/`.

## When to write

| File | Kind | When |
|------|------|------|
| `health/metadata-netflow.json` | metadata | **Every** visit: the board, `exporters[]`, `last_collected_at`; `last_visit_id` only when a stamp was written. |
| `health/netflow/<stamp>.json` | observation | First visit, a material move, or coverage ≠ `complete`; **never overwrite**. A quiet visit writes no stamp. |

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
At most **10** stamps; delete older after write.

The script writes these. The nurse does not `write_file` them.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
