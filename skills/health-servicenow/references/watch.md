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

## Health visit — run the script

One `execute_command`, `execution_type: "mcp_orchestration"`. Use the
path Studio shows for the attached
`health-servicenow/scripts/visit_servicenow.py`. Copy it. Do not
retype a path from memory. The transcript may render it as
`Internal directory`; that is the real path.

Each `execute_command` is a new container. In that container the
workspace is the `file_explorer` folder beside `skills` on the path
Studio shows for `visit_servicenow.py`. Copy that directory. Pass it
as `--workspace`. Do not pass the relative name `file_explorer`, and
do not `cd`.

```text
python3 <skill>/scripts/visit_servicenow.py collect --workspace <file_explorer>
```

The last stdout line is the summary. Ignore any runtime line above it.

If `needs_note` is non-empty, one `execute_command` with
`execution_type: "standard"`, same copied path:

```text
python3 <copied script path> annotate --workspace <copied file_explorer directory> --stamp health/servicenow/2026-10-09T14-57-46Z.json --headline "<one sentence>" --note "incident:NUMBER=<one sentence>"
```

`--stamp` is the summary field `stamp`, copied exactly. It starts
with `health/servicenow/` and ends with `.json`. The date in the
example is the shape, not a path to reuse. Do not pass the bare
`watch_id`. Do not put a quote on the end of `--stamp`.

One `--note` per `needs_note` item. The separator is `=`. Several
keys on one note are joined with `+` before that `=`. The note is
one sentence: what moved, how long the ticket has been open, whether
a device or a change is attached. Not the columns again. Never a
cause. If stderr says `hai_mcp unavailable`, follow the manual order
below. Any other failure: report that line and stop. Do not collect
by hand.

Reply from the summary line. Do not open the stamp or the board to
fill it.

## Manual order

Use this only when the script reports `hai_mcp unavailable`.

READ_BOARD → READ_PROD → READ_SERVICES → RESOLVE_IF_NEEDED → [D] → I
→ C → BUILD → DIFF → DECIDE → [WRITE_STAMP → READ_BACK → PRUNE] →
WRITE_BOARD → STOP

Everything is in `references/query.md`: since, scope terms, the two
queries, row build, keys, diff, stamp or quiet, board, reply.
Resolve: `references/metadata.md`. Do not `execute_command` on this
path. Persist with `write_file`.

## Stamps

Stamp `YYYY-MM-DDTHH-MM-SSZ`. If that path exists, add 1 second.
Never overwrite. That stamp is `watch_id`. After a stamp write,
`read_file` it, then keep **at most 10** stamps under
`health/servicenow/` only (delete oldest first). Do not list other
`health/` directories. Do not write `health-board.md`. On this
manual path, do not `execute_command`. Persist with `write_file`
on catalog paths. The script path prunes inside `visit_servicenow.py`.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 8 |
| `snow_query_table` | 3 (D on the baseline, I, C), one retry each |
| `snow_find_*` / `snow_get_*` / any other ServiceNow tool | 0 |

If over budget: stop querying, write what you have. Unavailable
counts are `null`, never `0`.
