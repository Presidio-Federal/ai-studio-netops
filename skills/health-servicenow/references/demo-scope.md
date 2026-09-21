# ServiceNow — demo lab scope

Use on a **ServiceNow health visit** only. The instance is shared. Most
rows are not this lab. Interpret **in-scope** records only. Tag
everything else `out_of_scope` and do not use it for consult `status`.

Lookup is `health/metadata-servicenow.json`. Device names and lab title are
`inventory/prod.json`. Do not put marker text, match terms, hostnames,
or lab titles in this skill or the prompt.

## In scope (`scope=demo`)

A record is in scope when **any** of these is true in
`short_description`, `description`, or `work_notes` (and close notes
when present):

1. Contains `servicenow.marker` from metadata.
2. Contains any string in `servicenow.match_terms` from metadata
   (omit this check if the array is missing or empty).
3. Contains an inventory device `name`.
4. Contains the inventory `source.name` or `lab_title`.

Category or a generic table filter alone is **not** in scope.

## Out of scope

Count open out-of-scope INC/CHG in `out_of_scope_open`. Do **not**
put those numbers in `ticket_numbers`. Do not invent numbers.
Headline may quote the count.

## Threads

`threads`, `ticket_numbers`, and the counts use **in-scope** rows
only. Each in-scope payload becomes one thread with every join key
it contains. Empty successful in-scope set → `threads` `[]` and
zeros allowed.
