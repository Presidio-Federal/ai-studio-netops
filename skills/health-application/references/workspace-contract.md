# Produce — Health Application

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`. Do not
invent files. Persist with `write_file` on catalog paths.

One visit rewrites this plane’s board and writes **at most one**
new observation. Do not write `state/`.

## When to write

| File | Kind | When |
|------|------|------|
| `health/metadata-application.json` | metadata | **Every** visit: the board (`current[]`, `annotations[]`, `series[]`, `visits[]`), `lookup`, `last_collected_at`; `last_visit_id` only when a stamp was written. |
| `health/application/<stamp>.json` | observation | First visit, or a row moved materially, or coverage ≠ `complete`; **never overwrite**. A quiet visit writes no stamp. |

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
`watch_id` matches **this** visit’s new file. Never overwrite. At
most **10** stamps in `health/application/`; delete older after
write.

Do not write `runs/`, `inventory/`, `trend-analysis.json`,
`state/network-sync.json`, or anything under `automations/`. Do not
write `health/metadata-splunk.json`, `health/metadata-netflow.json`,
`health/splunk/`, or `health/netflow/`; those are Health Monitor's.
Do not write `inventory/services.json` or
`inventory/applications.json`; the `application:` key on a row is a
label copied from Grafana, not a registry entry.

Visit steps: `references/watch.md`.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
