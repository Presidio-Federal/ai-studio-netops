# Trends visit

A schedule line or a chat that names trends /
ServiceNow-Trend-Analysis is authorization. Do not confirm.

## Trend visit — run the script

One `execute_command`, `execution_type: "mcp_orchestration"`. Use the
path Studio shows for the attached
`ops-servicenow-trends/scripts/visit_trends.py`. Copy it. Do not
retype a path from memory. The transcript may render it as
`Internal directory`; that is the real path.

Each `execute_command` is a new container. In that container the
workspace is the `file_explorer` folder beside `skills` on the path
Studio shows for `visit_trends.py`. Copy that directory. Pass it as
`--workspace`. Do not pass the relative name `file_explorer`, and do
not `cd`.

```text
python3 <skill>/scripts/visit_trends.py collect --workspace <file_explorer>
```

Add `--schedule` when the task is a schedule line. The last stdout
line is the summary. Ignore any runtime line above it.

If `needs_scope` is true, ask with the summary `options` and stop.
Do not collect by hand.

If `needs_note` is non-empty, one `execute_command` with
`execution_type: "standard"`, same copied path:

```text
python3 <copied script path> annotate --workspace <copied file_explorer directory> --stamp servicenow/trends/2026-10-09T15-00-00Z.json --headline "<one sentence>" --why "incident:NUMBER=<one sentence>" --theme "incident:NUMBER=<short theme>"
```

`--stamp` is the summary field `stamp`, copied exactly. It starts
with `servicenow/trends/` and ends with `.json`. The date in the
example is the shape, not a path to reuse. One `--why` and one
`--theme` per `needs_note` item. The key is `incident:` plus that
item's `example`. A `locked` item keeps `recommend` `kb`. For an
unlocked item, `--recommend incident:NUMBER=<watch|restaff|problem|none>`
may replace the script's choice. Do not set `kb` yourself.

The why is one sentence: the class, whether the resolutions match,
and the recommendation. Not the ticket list again.

If stderr says `hai_mcp unavailable`, follow the manual order below.
Any other failure: report that line and stop.

Reply from the summary line. Do not open the stamp to fill it.

## Manual order

Use this only when the script reports `hai_mcp unavailable`.

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

The script groups by category plus the normalized
short_description (lowercase, punctuation collapsed). A cluster
needs at least `min_related_cases`. `fix_consistent` is true only
when at least two close notes share the same first sentence.
`recommend` is `kb` only then. The model rewrites `theme` and
`why` in `annotate`, and may change `recommend` when it is not
`kb`.

Manual fallback, when the script cannot run: group in-scope
tickets by similar short_description / category. A cluster needs
at least `min_related_cases`.

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
