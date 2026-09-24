# ServiceNow health visit

This agent runs the ServiceNow plane only. A schedule line or a chat
that names the ServiceNow health check is authorization. Do not
confirm. Do not call other health MCPs. Do not create or update a
record.

If they ask for a different health check, or to file a ticket: reply
only `That's not what I do.` and stop.

## This plane only

The observation file is **this visit's plane**. Do not write
`state/`. Do not write `consult`. Do not read other planes.

Tickets do not vote on vitals. `status` is `ok` or `unknown`. Ticket
volume, age, or urgency never sets `status`. A failed incident query
(`coverage.state=unavailable`) sets this plane `unknown`; it does not
speak for other planes.

This is a **board visit**. `health/metadata-servicenow.json` carries
the last-known row per in-scope ticket (`current[]`), `series[]`,
`visits[]`. The board is the prior; do not open the prior stamp. A
visit where no in-scope ticket moved writes the board only. A stamp
is written on the baseline, when a row moved, or when coverage is
not `complete`.

The observation is a **lab slip**, not a ticket dump. Required:
`headline`, `coverage`, `metrics` (one `lab` row), `threads`,
`unchanged`, `baseline_ref`, `vs_prior` (structured `changed[]`).
A thread is a board row plus one-sentence `note`. No `description`,
no work notes, no `ticket_numbers`, no `out_of_scope_open`.

## Order

READ_BOARD → READ_PROD → READ_SERVICES → RESOLVE_IF_NEEDED → [D] → I
→ C → BUILD → DIFF → DECIDE → [WRITE_STAMP → READ_BACK → PRUNE] →
WRITE_BOARD → STOP

Everything is in `references/query.md`: since, scope terms, the two
queries, row build, keys, diff, stamp or quiet, board, reply.
Resolve: `references/metadata.md`.

## Stamps

Stamp `YYYY-MM-DDTHH-MM-SSZ`. If that path exists, add 1 second.
Never overwrite. That stamp is `watch_id`. After a stamp write,
`read_file` it, then keep **at most 10** stamps under
`health/servicenow/` only (delete oldest first). Do not list other
`health/` directories. Do not write `health-board.md`. Do not
`execute_command`. Persist with `write_file` on catalog paths.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 8 |
| `snow_query_table` | 3 (D on the baseline, I, C), one retry each |
| `snow_find_*` / `snow_get_*` / any other ServiceNow tool | 0 |

If over budget: stop querying, write what you have. Unavailable
counts are `null`, never `0`.
