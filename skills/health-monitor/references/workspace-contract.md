# Produce — Health Monitor

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`. Do not
invent files. Persist with `write_file` on catalog paths.

One named visit writes **one** new observation and updates this
plane’s metadata. Do not write `state/`.

## When to write

| File | Kind | When |
|------|------|------|
| `health/metadata-splunk.json` | metadata | Splunk ids, watermark, or `last_visit_id`. |
| `health/metadata-thousandeyes.json` | metadata | TE ids or `last_visit_id`. |
| `health/splunk/<stamp>.json` | observation | Each Splunk visit; **never overwrite**. |
| `health/thousandeyes/<stamp>.json` | observation | Each TE visit; **never overwrite**. |

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
`watch_id` matches **this** visit’s new file. Never overwrite. At
most **10** stamps per source directory; delete older after write.

Do not write `runs/`, `inventory/`, `trend-analysis.json`, or
`state/network-sync.json`. Do not write under
`automations/schedules/`.

Visit steps: `references/watch.md`.
