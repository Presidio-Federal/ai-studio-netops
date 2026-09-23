# Produce — Ops ServiceNow Trends

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`.
Do not invent files. Persist with `write_file` on catalog
paths (`servicenow/metadata-trends.json`,
`servicenow/trends/<stamp>.json`). Never a bare filename.
If Access denied lists `file_explorer`, retry once
`file_explorer/<catalog row>`. Never write under
`automations/schedules/`.

One visit writes **one** new observation and updates
metadata. Do not write `state/`.

## When to write

| File | Kind | When |
|------|------|------|
| `servicenow/metadata-trends.json` | metadata | Scope resolve, or last-visit after a successful collect |
| `servicenow/trends/<stamp>.json` | observation | Each visit; **never overwrite** |

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump
1s. `watch_id` matches **this** visit’s new file. Never
overwrite. At most **10** stamps; delete older after write.

Do not write `state/servicenow.json`, `servicenow/cases/`,
`health/`, `trends.json`, or `trend-analysis.json`. Do not
write under `automations/schedules/`.

## Canonical keys

Every JSON write has required top-level `keys`: an array,
unique, empty allowed. Values match exactly
`^(device|interface|site|service|test|control|incident|change):[^ ].*$`.
Metadata has `[]` unless explicit entity fields are added.
For a trend observation, write the deduplicated union of
`incident:<number>` from `clusters[].example_numbers` and
`clusters[].open_consuming[].number`, plus `device:<name>`
from `clusters[].devices`. Keep the nested fields. Never key KB
numbers, themes, assignees, recommendations, prose, or source
refs. Explicit locations use `site:`; never infer one.

Visit steps: `references/watch.md`.
