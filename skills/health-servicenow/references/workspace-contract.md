# Produce — Health ServiceNow

Paths, Kind, catalog: **`workspace-handoff`**. Write schemas live in
this skill. Do not `execute_command`. Do not invent files. Persist
with `write_file` on catalog paths.

## When to write

| File | Kind | When |
|------|------|------|
| `health/metadata-servicenow.json` | metadata | **Every** visit (it is the board): after resolve, and at the end with `current[]`, `series[]`, `visits[]`, `last_collected_at`. `last_visit_id` only when a stamp was written. Not advanced on `unavailable`. |
| `health/servicenow/<stamp>.json` | observation | Baseline, a moved row (`vs_prior.changed[]` non-empty), or coverage ≠ `complete`. **Never overwrite.** A quiet visit writes no stamp. |

Do not write `state/`, `health-board.md`, `servicenow/`,
`state/servicenow.json`, `servicenow/cases/`, `runs/`, `inventory/`,
`trend-analysis.json`, `remediation-request.json`,
`state/network-sync.json`, other `health/<source>/` directories, or
anything under `automations/schedules/`.

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1 s.
`watch_id` matches **this** visit's new file. At most **10** stamps
under `health/servicenow/`; delete older after write.

Order: stamp (when due) → `read_file` it → prune → board.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
