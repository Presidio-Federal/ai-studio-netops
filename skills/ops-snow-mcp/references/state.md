# ServiceNow board (state ledger)

Same idea as Health: `state/servicenow.json` is the **current board plus
history**, not the last ticket number alone.

## When this runs

| Invoke | Action |
|--------|--------|
| Who can go onsite / dispatch | `references/dispatch.md` — live groups + Trends stamp. `last_action=recommended` |
| File / update a ticket from workspace evidence | Mutate **one** record, then rewrite the board |
| Open in-scope lab tickets | Recommend a fix + name assignee — `last_action=recommended`. No create |
| Assign an in-scope INC | They named the person this turn — `last_action=assigned` |
| Draft a KB | They asked this turn — `references/knowledge.md`. `last_action=drafted` |
| Board / status / what is open | Look only — `last_action=board`. No create |
| Nothing actionable | `noop`, still rewrite the board from index + find/get |

Do not dump ServiceNow tables. Open set = **in-scope** cases in
`servicenow/cases/index.json` that find/get still show as not
closed/resolved/cancelled. Out-of-scope shared-instance rows stay
off the board.

## Order

1. Read `servicenow/metadata-lab.json` (`references/metadata.md`). Missing
   marker: resolve, then ask. Do not invent it.
2. Read `inventory/prod.json` for **labels only**. A device name on a
   case must match an inventory label. Do not invent hosts.
3. Read `state/servicenow.json` if present (prior `history`, `open`,
   `run_count`). Old files without `history` = one prior row.
4. Read `servicenow/metadata-trends.json` if present. If
   `last_visit_id` is set, that stamp — read only.
5. Find/get **in-scope** open INC (marker / match terms / inventory
   labels). Shared-instance rows are out of scope. Keep
   `assigned_to` from get.
6. For each in-scope open INC: recommend the fix from the ticket +
   inventory. Name the assignee. If a Trends cluster matches and
   says `kb`, say so. Do not apply config. `last_action=recommended`
   when that is all they asked.
7. Read evidence you will act on (`state/health.json`, `state/testing.json`,
   `state/compliance.json` only if `run.suites` includes `compliance`,
   a pending request). Never overwrite those files.
8. If mutating: authorization, then one of assign / draft KB /
   create or update one record. Read it back.
9. Refresh **your** cases: find/get each index number (or the one you
   just wrote). Drop closed from `active.json`. Keep them on `index.json`.
10. Map each open case to inventory `devices[]` from evidence / short
    description — only names that exist in inventory.
11. Write, in order:
    - `servicenow/cases/active.json` (open only, cap 5)
    - `servicenow/cases/index.json` (all touched)
    - `state/servicenow.json` (`servicenow-state/v1`)
    - `servicenow/metadata-lab.json` (last-visit when find/get succeeded)
    Recompute each file's top-level `keys` from its explicit
    typed case numbers and device arrays. Metadata uses `[]`.
12. Validate. Read back. Stop.

## `state/servicenow.json`

- `status`: `clear` | `open` | `unknown`
- `open.incidents` / `open.changes` / `open.devices`
- `trend.vs_prior`: `first` | `unchanged` | `worse` | `better` from open
  counts (more open = worse)
- `history[]` newest first, cap 20
- `run_count`, `first_run_at`, `last_run_at`
- `last_action`: `created` | `updated` | `assigned` | `drafted` | `recommended` | `noop` | `needs_approval` | `failed` | `board`
