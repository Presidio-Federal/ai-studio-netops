# ServiceNow Health visit

This agent runs the ServiceNow plane only. A schedule line or a chat
that names the ServiceNow health check is authorization. Do not
confirm. Do not call other health MCPs. Do not create or update a
record.

If they ask for a different health check, or to file a ticket: reply
only `That's not what I do.` and stop.

## This plane only

The observation file is **this visit’s plane**. Do not write
`state/`. Do not write `consult`. Do not read other planes.

Tickets do not vote on vitals. Ticket volume does not set
`degraded`. A failed collection (`coverage.state=unavailable`)
sets this plane `unknown`; it does not speak for other planes.
Reply `Trend:` is `vs_prior.delta` vs the prior stamp of **this**
source (`servicenow.last_visit_id`). First visit: `delta` `first`.

The observation is a **lab slip**. Required: `headline`, `coverage`,
`metrics`, `vs_prior`. Do not write `summary` that restates
`metrics`. Do not write `incidents[]` / `changes[]` / `recent[]`
unless a number in `metrics` needs a ticket id — cap 5.

Envelope `headline` is this visit’s check headline.

## Shared order

1. `read_file` `health/metadata-servicenow.json` if present. Follow
   `references/metadata.md`. Never `get_folder_structure`. Never
   `automations/schedules/...`. If `last_visit_id` is set,
   `read_file` `health/servicenow/<last_visit_id>.json` and compare.
   Then `inventory/prod.json`. Device names only from inventory
   labels.
2. Pick stamp `YYYY-MM-DDTHH-MM-SSZ`. If
   `health/servicenow/<stamp>.json` exists, add 1 second. Never
   overwrite. That stamp is `watch_id` on this observation.
3. Collect (`references/query.md`, `references/demo-scope.md`). Write
   the lab slip (`headline`, `coverage`, `metrics`, `vs_prior`), then
   `read_file`.
4. Re-read metadata, write this visit’s `last_visit_id` /
   `last_collected_at` when collection succeeded. Keep **at most
   10** stamps under `health/servicenow/`. Delete older stamp files
   in that directory only (oldest first). Do not overwrite. Do not
   write `health-board.md`. Do not `execute_command`. Persist with
   `write_file` on catalog paths.

`metrics` one row `scope` `lab`. Keys: `open_incidents`,
`open_changes`, `open_p1p2`, `out_of_scope_open`.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 20 |
| ServiceNow find/get | 8 |
| `snow_query_table` | 2 |

If over budget: stop querying, write what you have.
