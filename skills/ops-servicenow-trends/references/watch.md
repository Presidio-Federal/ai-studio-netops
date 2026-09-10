# Trends scan

Lookback and threshold come from metadata
(`lookback_days`, default 14; `min_related_cases`, default 3).
Budget: one in-scope incident find (open + closed in the
lookback), bounded gets for cluster samples, one knowledge
find per repeating theme. Do not dump the instance.

## Collect

Use only metadata scope: `assignment_groups[]`, `categories[]`,
`match_terms[]`, `marker`. Rows that do not match are out of
scope.

`inventory/prod.json` is optional. A recommendation may name a
device only if that name is in the file.

## Cluster

Group in-scope tickets by similar short_description /
category. A cluster needs at least `min_related_cases`.

For each cluster:

- theme, count, example numbers (from this find, never invented)
- `fix_consistent` — true only when close_notes / work notes
  show the same resolution
- already-have KB? (`snow_find_knowledge` on the theme)
- recommend `kb` only when count ≥ threshold **and**
  `fix_consistent` is true
- otherwise `watch` (or `restaff` / `problem` when the same
  class is eating open tickets / repeating on a named device)
- why

Do not create or update Knowledge. This scan writes the stamp
and stops.

## Write

One new `servicenow/trends/<stamp>.json`. Never overwrite.
Never `trends.json`. `watch_id` matches the filename. At most
10 stamps; delete older after write. Then metadata
`last_visit_id`.
