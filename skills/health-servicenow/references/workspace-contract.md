# Produce — Health ServiceNow

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`. Do not
invent files. Persist with `write_file` on catalog paths.

One visit writes **one** new `health/servicenow/<stamp>.json`.
Do not write `state/`. Update `health/metadata-servicenow.json`
only. Do not write other `health/<source>/` directories.

## When to write

| File | Kind | When |
|------|------|------|
| `health/metadata-servicenow.json` | metadata | Marker resolve, or last-visit stamps after a successful collection. |
| `health/servicenow/<stamp>.json` | observation | Each ServiceNow visit; **never overwrite**. |

Do not write `health-board.md`, `servicenow/`, or `state/servicenow.json`.

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
`watch_id` matches **this** visit’s new file. Never overwrite. At
most **10** stamps under `health/servicenow/`; delete older after
write.

Do not write `runs/`, `inventory/`, `trend-analysis.json`, or
`state/network-sync.json`. Do not write under
`automations/schedules/`.

Visit steps: `references/watch.md`.

Unavailable counts are null.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
