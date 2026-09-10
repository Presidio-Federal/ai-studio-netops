# Dispatch / who can go onsite

This is Operator. Trends only wrote the stamp.

They named a site or group (or “who can go onsite”). That is
a read. Do not require a lab marker. Do not stop after finding
the group. Do not invent filenames, availability tags, or
“field-capable” filters. Every member the tool returns is in
the pool.

## Exact paths

- Metadata: `servicenow/metadata-trends.json`
- Stamp: `servicenow/trends/<last_visit_id>.json`

`last_visit_id` is already `YYYY-MM-DDTHH-MM-SSZ`. That string
**is** the filename. Never `metadata-trends.json`,
`metadata-trends-stamp.json`, `trends.json`, or a path you
invented.

No metadata or stamp: continue on live groups. Say trends are
not on disk.

## Same-turn tools (do not stop between them)

1. `read_file` `servicenow/metadata-trends.json`
2. If `servicenow.last_visit_id` (or `last_visit_id`) is set:
   `read_file` `servicenow/trends/<that id>.json`
3. `snow_find_assignment_groups(search=<site they named>)`.
   Prefer the metro / dispatch pool over a program-management
   row.
4. **Immediately** `snow_list_group_members` on that group’s
   `sys_id` or `name`. If this call is missing, the visit
   failed.
5. Busy: stamp `clusters[].open_consuming[]`, or
   `snow_find_incidents` / `snow_get_incident` for open tickets
   assigned to those members. Busy = on an open INC.
6. If that INC’s number or theme is on a cluster with
   `recommend` `kb`: **required** in the reply — they are
   working a trend case; a KB would free that engineer for
   onsite. Then **ask**: `Draft that KB now? Yes or no.`
   Stop. Do not call `snow_create_knowledge` on this turn.
   Existing `kb_number` → say reuse it; still ask only if
   they want a new draft.
7. Available = a member **not** on an open INC. Reply in
   the prompt block. Draft only after they say yes.

Never dump the instance. Never write `servicenow/trends/`.
