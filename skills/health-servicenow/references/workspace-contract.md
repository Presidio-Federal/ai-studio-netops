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
