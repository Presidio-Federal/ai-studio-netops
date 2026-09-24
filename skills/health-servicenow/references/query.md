# ServiceNow visit — ticket board

Use on a **ServiceNow health visit** only. The one tool is
`snow_query_table` (read-only Table API, `sysparm_display_value=all`
on the server side, limit ≤ 50). `snow_find_incidents` and
`snow_get_incident` are **not used** on this visit: their fixed field
lists omit the typed entity columns, `rfc`, and `resolved_at`, and
`get` returns the whole work-notes journal. Never `snow_create_*` or
`snow_update_*`. Do not read other planes' metadata or stamps.

The instance is shared: tens of thousands of tickets belong to other
tenants. Scope is decided **in the query**, by the terms below, so
the payload you receive is already this lab's. Do not pull a wider
set and classify it yourself. Do not query by category, caller, or
assignment group alone.

`marker`, `match_terms`, `lookback_days`, `entity_fields` come from
`health/metadata-servicenow.json`. Device names come from
`inventory/prod.json`. Service names come from
`inventory/services.json` when it exists. Do not put any of them in
this file or the prompt.

## Setup (reads, before any ServiceNow call)

1. `read_file` `health/metadata-servicenow.json` — lookup and the
   **board** (`servicenow.current[]`, `series[]`, `visits[]`).
   Missing `marker` or `entity_fields` → `references/metadata.md`
   (resolve), write metadata, then continue.
2. `read_file` `inventory/prod.json` — `devices[].name`.
3. `read_file` `inventory/services.json` if it exists —
   `services[].name` and `aliases[]`. Missing is fine: then no
   `service:` key is written and `service` on a row comes only from
   the platform's own columns.

Do not open the prior stamp; the board is the prior.

## Since

`since` is a `YYYY-MM-DD HH:MM:SS` string (UTC, space, no `T`, no
`Z`):

- No `baseline_visit_id` → `checked_at` minus `lookback_days`.
- Otherwise → board `last_collected_at` minus 1 day (a day of slack
  covers instance time-zone display and a visit that ran long).

## Scope terms

Build one list `terms` = every `prod.json` `devices[].name` + `marker`
+ every `match_terms[]` item. For each term `t` write three clauses
(no spaces around operators; `<dev>` is `entity_fields.device`):

```
short_descriptionLIKE<t>^ORdescriptionLIKE<t>^OR<dev>=<t>
```

When `entity_fields.device` is null, write only the two `LIKE`
clauses. Join every term's clauses with `^OR`. Call the result
`SCOPE`. It is long (≈ 900 characters for ten terms); that is
expected.

ServiceNow groups consecutive `^OR` conditions with the condition
before them, so the query below reads
`(active OR updated since) AND (term1 OR term2 OR …)`.

## Calls

**D — dictionary (baseline only, or when `entity_fields` is
missing).** See `references/metadata.md`.

**I — incidents. Every visit.**

```
snow_query_table(
  table="incident",
  query="active=true^ORsys_updated_on>=<since>^<SCOPE>",
  fields="number,short_description,state,active,urgency,priority,opened_at,sys_updated_on,resolved_at,close_code,close_notes,rfc,cmdb_ci,business_service,<entity columns>",
  limit=50)
```

`<entity columns>` = the non-null values of `entity_fields`
(`device`, `interface`, `ip`, `service`), comma-separated, in that
order. Omit the trailing comma when there are none. Do not request
`description`, `work_notes`, or `comments`: they are prose, they are
large, and they are not columns on the row.

**C — changes. Every visit.**

```
snow_query_table(
  table="change_request",
  query="active=true^ORsys_updated_on>=<since>^<SCOPE>",
  fields="number,short_description,state,active,urgency,priority,opened_at,sys_updated_on,closed_at,close_code,close_notes,cmdb_ci,type,<entity columns>",
  limit=50)
```

The same typed columns exist on `change_request` on an instance that
has them on `incident`. If C returns `ok: false` naming an unknown
field, retry once without `<entity columns>`.

Order: setup → [D] → I → C → build → diff → write. Nothing else. No
`snow_find_*`, no `snow_get_*`, no second page, no query on
`sys_journal_field`, `cmdb_ci`, or `sys_user`. A call that fails is
retried **once**. I failing twice → `unavailable`, null metrics, no
watermark move. C failing twice with I good → `partial`, incident
rows only.

## Build rows

Each returned row is one board row. Values arrive as display values
(`state` `"In Progress"`, `urgency` `"2 - Medium"`); reference fields
arrive as `{sys_id, display}` or a plain string — take `display`.
Empty string → `null`. Timestamps arrive as `YYYY-MM-DD HH:MM:SS`;
write them `YYYY-MM-DDTHH:MM:SSZ`.

| Column | From |
|--------|------|
| `type` | `incident` for I rows, `change` for C rows |
| `number` | `number` |
| `scope` | `<type>:<number>` |
| `state` `active` `urgency` `priority` `opened_at` | copied; `active` as boolean |
| `updated_at` | `sys_updated_on` |
| `resolved_at` | `resolved_at` (I) / `closed_at` (C); null when empty |
| `issue` | `short_description` verbatim |
| `close_code` | copied or null |
| `close_notes` | first sentence, or null |
| `rfc` | `rfc` display (I); null on C rows |
| `ci` | `cmdb_ci` display or null |
| `service` | `entity_fields.service` column when set, else `business_service` display, else the registry `services[].name` whose `name` or an alias appears in `issue` (case-insensitive), else null |
| `device` `interface` `ip` | the `entity_fields` columns, copied as returned; null when the column is null or empty |

**`keys`** — in this order, at most 8, no duplicates:

1. `incident:<number>` or `change:<number>`.
2. `device:<name>` — when `device` equals a `prod.json` name
   case-insensitively, write the `prod.json` spelling. Otherwise, for
   each `prod.json` name that appears in `issue` as a whole word
   (case-insensitive), write it. Nothing else produces a device key:
   not `description`, not `ip`, not a name you recognise.
3. `interface:<device>/<interface>` — only when `interface` is set
   and step 2 produced exactly one device key.
4. `service:<name>` — only when `services.json` exists and `service`
   (after the column rule above) equals a `services[].name`.
5. `change:<rfc>` — when `rfc` is set.

Never a `site:`, `test:`, or `control:` key: this payload has no
column for them.

## Diff against the board

Match each built row to `current[]` by `scope`. Every field below
that differs is one `changed[]` item `{keys, field, prior, current,
at}` with `at` = the row's `updated_at`, `prior` = the board value
(null for a new row), `current` = this row's value:

| Field | `changed[].field` |
|-------|-------------------|
| scope not on the board | `row` (`current` = `state`) |
| `state` | `state` |
| `urgency` | `urgency` |
| `device` `interface` `ip` `service` `rfc` | that name |
| `issue` | `issue` |
| none of the above moved but `updated_at` did | `updated` (`prior`/`current` = the two timestamps) |

`updated` means someone wrote on the ticket (a work note, a field
not on the row). It is material — the higher agent wants to know the
ticket is being worked — but it is never `worse`.

**Delta.** `first` on the baseline. `worse` when any item is a new
active row, a `state` moving from Resolved/Closed/Canceled back to an
active state, or `urgency` whose leading number decreased (1 is
highest). `better` when items exist, none is worse, and at least one
`state` moved to Resolved/Closed/Canceled. `changed` for any other
non-empty set. `unchanged` when there are no items.

## Stamp or quiet

- Baseline (no `baseline_visit_id`): stamp; every returned row is a
  thread; `delta` `first`; `changed` `[]`; `unchanged` 0;
  `prior_watch_id` null.
- `changed[]` non-empty, or coverage not `complete`: stamp; threads
  = the rows that moved.
- Otherwise **quiet**: no stamp. Board only.

Plane `status`: `ok` when I succeeded; `unknown` when coverage is
`unavailable`. Open, old, or urgent tickets never change `status`.

## Write

**Stamp** (schema `health-servicenow-check`). Top-level fields, these
names and no others:

```json
{
  "keys": [], "schema": "health-servicenow-check/v3", "source": "servicenow",
  "watch_id": "<YYYY-MM-DDTHH-MM-SSZ>", "checked_at": "<ISO Z>", "ok": true,
  "status": "ok|unknown", "headline": "...",
  "window": "<since>",
  "coverage": { "state": "complete|partial|unavailable", "detail": "..." },
  "metrics": [ { "at": "...", "scope": "lab", "rows": 3, "open_incidents": 3, "open_p1p2": 0,
                 "open_changes": 0, "resolved_rows": 0, "typed_rows": 1 } ],
  "threads": [ { "...row columns...", "note": "..." } ],
  "unchanged": 0, "baseline_ref": null,
  "vs_prior": { "prior_watch_id": null, "delta": "first", "changed": [] },
  "concerns": [ { "type": "incident", "name": "<number>" } ]
}
```

`threads` = moved rows + `note`; a thread has exactly the row
columns plus `note`. `note` is one sentence against the board row:
what moved, how long the ticket has been open (`opened_at` to
`checked_at`), whether a device or a change is now attached. On the
baseline: how long open and whether it names a device or a change.
Not the columns again; never a cause; never text from `description`.
`metrics` = one `lab` row: `rows` returned, `open_incidents`
(incident rows with `active` true), `open_p1p2` (open incidents
whose `priority` or `urgency` starts with `1` or `2`),
`open_changes`, `resolved_rows` (rows with `active` false),
`typed_rows` (rows with a non-null `device`). `unchanged` = board
rows not replaced. `baseline_ref` =
`health/servicenow/<baseline_visit_id>.json`. `headline`: which
tickets moved and how; how long the open ones have been open;
whether any names a device or a change; then rows unchanged.
`concerns`: one `{type: incident, name}` per active row with
`priority` or `urgency` starting `1` or `2`.

**Board** (schema `health-metadata-servicenow`) — every visit:

- `current[]` ← built rows replace rows with the same `scope`; rows
  not returned this visit are kept as they were; over 32, drop
  `active` false rows oldest `updated_at` first.
- `series[]` ← append the lab metric row; keep 10.
- `visits[]` ← append `{watch_id (null when quiet), checked_at,
  status, coverage, delta, stamp_written, since}`; keep 10.
- `entity_fields` ← rewritten only when call D ran.
- `last_collected_at` ← `checked_at` (not on `unavailable`).
  `last_visit_id` ← this `watch_id` only when a stamp was written.
  `baseline_visit_id` ← this `watch_id` on the first visit.
- `keys` ← union of keys on `current[]`.

Write the stamp first (when due), `read_file` it, prune to 10 stamps
in `health/servicenow/` only, then write the board.

## Budget

| Item | Max |
|------|----:|
| Workspace reads | 3 |
| Workspace writes | 3 (stamp, board, prune) |
| `snow_query_table` | 2 per visit (I, C) + 1 on the baseline (D), one retry each |
| `snow_find_*` / `snow_get_*` | 0 |

## Reply

Stamp written:

```text
Visit: servicenow
Result: <ok | unknown>
Coverage: <complete|partial|unavailable>
Since: <since>
Wrote: health/servicenow/<stamp>.json
Trend: <delta>
Findings:
- <number> <state> (<urgency>): <issue, first 60 chars> — open since <opened_at>; device <device or none>; change <rfc or none>
Next: none
```

Quiet:

```text
Visit: servicenow
Result: ok
Coverage: complete
Since: <since>
Wrote: health/metadata-servicenow.json (no material change)
Trend: unchanged
Board: <n> rows, <k> open, last stamp <last_visit_id>
Next: none
```
