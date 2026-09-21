# ServiceNow collect (read only)

Use on a **ServiceNow health visit** only. Prefer dedicated find/get.
`snow_query_table` is the escape hatch when find returns empty or
unusable. Never create or update.

Substitute `servicenow.marker` (and `match_terms` when present) from
metadata. Scope and tagging: `references/demo-scope.md`. Classify
every row before you keep it.

## Labels

Read `inventory/prod.json` first. A device name on a ticket must
match an inventory `name`. Do not invent hosts. In-scope tickets with
no matching label still count when they match metadata marker or
match_terms, or the inventory lab title.

## Baseline

Let `marker` be metadata `servicenow.marker`.

1. `snow_find_incidents(search=<marker>, active_only=true)`
2. `snow_find_changes(search=<marker>)` for changes in this window,
   including implemented and closed. A closed incident that names a
   change is the story.
3. For each metadata `match_terms[]` item, at most one extra find
   (`search=<term>`) if the marker find missed in-scope rows and
   budget remains.
4. If find is still empty or the tool errors: one `snow_query_table`
   on `incident` with `short_descriptionLIKE<marker>` (or
   `descriptionLIKE<marker>`) and `sysparm_limit` ≤ 50. Then at most
   one `change_request` query the same way. Do not query by category
   alone.
5. Recent (correlation, in-scope only):
   `snow_find_incidents(search=<marker>, active_only=false)` and keep
   resolved/closed in-scope rows, newest first, cap 10. Do not pull
   the instance history.

`snow_get_incident` / `snow_get_change` when an in-scope find row is
missing the number, `short_description`, `description`, state,
urgency, `close_code`, `close_notes`, a device name, a related
change number, or the change's `justification`. The note cannot
be written without them.

Do not copy the ServiceNow record onto the stamp. For each in-scope
story write one `threads` row. `keys` is every contract join key
that payload contains: `incident:<number>`, `change:<number>` when a
change number is present, `device:<inventory name>` for each
inventory device the text names, `interface:<name>` when an
interface is named, and the same for `site` `service` `test`
`control` `recommendation` when the payload has them. Write all of
them. Do not invent a key the payload does not have. `note` carries
the issue in the ticket's words, urgency, and state. When the
ticket is closed, include `close_code` and `close_notes`. When a
change is in the payload, include what it was for and whether it
was implemented. Do not write a sentence that only says the ticket
opened or closed. `ticket_numbers` lists those incident and change
numbers. Cap 16 threads.

## Rank

`status` is `ok` when find/get succeeded and `unknown` when
coverage is `unavailable`. Open tickets do not set `status`.
Record counts on `metrics`. Record the judgment on `threads`.
An empty in-scope set is `ok` with zeros and `threads` `[]`.
Out-of-scope rows stay in `out_of_scope_open` and get no thread.

`collection_status` is `complete` when find/get succeeded,
`unavailable` on MCP/auth/timeout (counts `null`, never `0`).

Observation `headline` is the same substance across `threads`:
what was wrong, and what was done about it. Later visit:
`vs_prior.changed` says what moved since `prior_watch_id`,
including the issue and how the state changed. First visit:
`delta` `first`, `changed` `[]`, and the threads still hold the
issue, the state, and any close or change detail.

Do not file or update a ticket.
