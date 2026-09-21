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
2. `snow_find_changes(search=<marker>)` for open changes (skip closed
   / cancelled / implemented when the payload says so)
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

`snow_get_incident` / `snow_get_change` only when an **in-scope** find
row is missing number, state, or urgency needed to rank.

Do not dump tables. Rank in-scope rows in memory (High
urgency/impact, then newest). When a metric needs a ticket id,
write `ticket_numbers` (those numbers only, cap 5). Omit it when
the counts are enough. The stamp has no `incidents[]`,
`changes[]`, or `recent[]`.

## Rank

`status` is `ok` when find/get succeeded and `unknown` when
coverage is `unavailable`. Open in-scope tickets do not set
`status`. Record them on `metrics` and, when a count needs an id,
`ticket_numbers`. An empty in-scope set is `ok` with zeros.
Out-of-scope rows stay in `out_of_scope_open`. This plane does not
vote on the health envelope.

`collection_status` is `complete` when find/get succeeded,
`unavailable` on MCP/auth/timeout (counts `null`, never `0`).

Observation `headline` quotes in-scope `open_incidents`,
`open_changes`, `open_p1p2`, kept INC/CHG numbers, and
`out_of_scope_open` — evidence, not SOAP.

Do not file or update a ticket.
