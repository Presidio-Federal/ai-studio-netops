# Produce — Health Monitor

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`. Do not
invent files. Persist with `write_file` on catalog paths.

One named visit rewrites this plane’s board and writes **at most
one** new observation. Do not write `state/`.

## When to write

| File | Kind | When |
|------|------|------|
| `health/metadata-splunk.json` | metadata | **Every** Splunk visit: the board (`current[]`, `series[]`, `visits[]`), watermark, `last_collected_at`; `last_visit_id` only when a stamp was written. |
| `health/metadata-thousandeyes.json` | metadata | **Every** ThousandEyes visit: the board (`current[]`, `series[]`, `visits[]`), `agents[]`, `last_collected_at`; `last_visit_id` only when a stamp was written. |
| `health/splunk/<stamp>.json` | observation | First visit, or S2 returned rows, or coverage ≠ `complete`; **never overwrite**. A quiet window writes no stamp. |
| `health/thousandeyes/<stamp>.json` | observation | First visit, or a row moved materially, or coverage ≠ `complete`; **never overwrite**. A quiet visit writes no stamp. |

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
`watch_id` matches **this** visit’s new file. Never overwrite. At
most **10** stamps per source directory; delete older after write.

Do not write `runs/`, `inventory/`, `trend-analysis.json`, or
`state/network-sync.json`. Do not write under
`automations/schedules/`.

Visit steps: `references/watch.md`.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
