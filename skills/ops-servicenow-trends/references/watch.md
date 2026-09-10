# Trends visit

Budget: one find of incidents, one find of changes if needed,
bounded gets for cluster samples, one knowledge find per
repeating theme. Do not dump the instance.

## Collect

Use only metadata scope: `assignment_groups[]`, `categories[]`,
`match_terms[]`, `marker` (short_description / work_notes /
correlation text). Rows that do not match are out of scope.

Inventory `name` / `role` / `tags` are the engineering side.
A recommendation may name a device only if that name is in
`prod.json`.

## Cluster

Group in-scope open (and recent closed if useful) by similar
short_description / category. A cluster needs at least two
tickets or a clear repeating alert string.

For each cluster, say:

- theme
- count
- example numbers (from this find, never invented)
- already-have KB? (`snow_find_knowledge` on the theme)
- recommend: `kb` | `restaff` | `problem` | `watch` | `none`
- why

Password-reset-class noise → KB / self-service if no published
article. Same WAN path / same site repeating → problem or
restaff. One-off lab INC → not a trend; Operator owns that.

## Write

One new `servicenow/trends/<stamp>.json`. Never overwrite.
`watch_id` matches the filename. At most 10 stamps; delete
older after write. Then metadata `last_visit_id`.
