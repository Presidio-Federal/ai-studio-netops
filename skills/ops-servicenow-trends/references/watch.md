# Trends visit

A schedule line or a chat that names trends /
ServiceNow-Trend-Analysis is authorization. Do not confirm.

## Shared order

1. `read_file` `servicenow/metadata-trends.json`. Never
   `get_folder_structure`. Never `automations/schedules/...`.
   Follow `references/metadata.md`.
2. If `last_visit_id` is set, `read_file`
   `servicenow/trends/<last_visit_id>.json` and compare. Do
   **not** list `servicenow/trends/` to find a prior stamp.
3. Pick stamp `YYYY-MM-DDTHH-MM-SSZ`. If
   `servicenow/trends/<stamp>.json` exists, add 1 second.
   Never overwrite. That stamp is `watch_id`.
4. Collect. `write_file` **`servicenow/trends/<stamp>.json`**
   (including `metrics`), then `read_file` that same path.
   Set top-level `keys` to the deduplicated union from explicit
   cluster incident-number and device fields.
   Never `2026-….json` at the workspace root or under
   `automations/schedules/`.
5. `write_file` **`servicenow/metadata-trends.json`**
   (`last_visit_id` when collection succeeded). Keep **at
   most 10** stamps under `servicenow/trends/`. After the new
   write, delete older stamp files in **that directory only**.
   Set metadata top-level `keys` to `[]` when it has no
   explicit entity identity.
   If Access denied lists `file_explorer`, retry once
   `file_explorer/` + the catalog row. Do not `execute_command`.

On collection failure: still write that check
(`coverage.state=unavailable`; counts `null`). Do not
advance `last_visit_id`.

## Collect

Lookback and threshold from metadata (`lookback_days`,
default 14; `min_related_cases`, default 3). One in-scope
incident find (open + closed in the lookback), bounded gets
for cluster samples, one knowledge find per repeating theme.

Use only metadata scope: `assignment_groups[]`,
`categories[]`, `match_terms[]`, `marker`. Rows that do not
match are out of scope.

`inventory/prod.json` is optional. A recommendation may name
a device only if that name is in the file.

## Cluster

Group in-scope tickets by similar short_description /
category. A cluster needs at least `min_related_cases`.

For each cluster:

- theme, count, example numbers (from this find, never invented)
- `open_consuming[]` — open tickets in the cluster with
  `assigned_to` (from get). Empty if none are open.
- `fix_consistent` — true only when close_notes / work notes
  show the same resolution
- already-have KB? (`snow_find_knowledge` on the theme)
- recommend `kb` only when count ≥ threshold **and**
  `fix_consistent` is true
- otherwise `watch` (or `restaff` / `problem` when the same
  class is eating open tickets / repeating on a named device)
- why

Do not create or update Knowledge.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 20 |
| ServiceNow find/get | 12 |

If over budget: stop querying, write what you have.

Unavailable measurements are `null`, never `0`.
