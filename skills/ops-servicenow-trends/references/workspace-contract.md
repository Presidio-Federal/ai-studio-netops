# Produce — Ops ServiceNow Trends

Paths: **`workspace-handoff`**. Persist with `write_file` on
catalog rows. Do not invent files.

| File | Kind | When |
|------|------|------|
| `servicenow/metadata-trends.json` | metadata | Scope resolve, or last-visit after a successful collect |
| `servicenow/trends/<stamp>.json` | observation | Each visit; **never overwrite** |

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
At most **10** stamps; delete older after write.

Do not write `state/servicenow.json`, `servicenow/cases/`,
`health/`, `trends.json`, or `trend-analysis.json`.
