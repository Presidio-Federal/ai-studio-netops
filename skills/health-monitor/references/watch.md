# Named visit procedure

If the invoke does not name Splunk or ThousandEyes, ask which and
stop. Do not default. Do not collect.

```text
Which check: Splunk or ThousandEyes?
```

A line that names Splunk or ThousandEyes is authorization to run that
visit. Do not confirm.

If they ask for a different health check: reply `That's not what I
do.` and stop.

Splunk visit: `splunk_search`. Do not call ThousandEyes or other
health MCPs. ThousandEyes visit: `te_get_test_results` /
`te_list_alerts` (and `te_agents_get_agents` on the baseline). Do
not call Splunk or other health MCPs.

## This plane only

The observation file is **this visit’s plane** (`ok` / `degraded` /
`unknown`). Do not write `state/`. Do not read or write another
plane.

Both planes are **board visits**: the metadata file carries the
last-known state (`current[]`), `series[]`, `visits[]`. The board is
the prior; do not open the prior stamp. A visit with no material
change writes the board only. A stamp is written on the baseline,
when something material moved, or when coverage is not `complete`.

The observation is a **lab slip**, not a MCP dump. Required:
`headline`, `coverage`, `metrics`, `readings`, `unchanged`,
`baseline_ref`, `vs_prior` (structured `changed[]`). No `summary`,
`tests[]`, `by_mnemonic`, `samples`, `top_hosts`, `buckets`, or
rounds.

Required `metrics` on the observation: same keys every visit;
explicit `null` when not collected.

## Splunk visit

Everything is in `references/splunk.md`: three reads, two searches
grouped by device in Splunk, a spelling lookup per device, diff
against the board on `health/metadata-splunk.json`, board written
first, stamp when due. Baseline window `-7d`.

Order: READ_BOARD → READ_PROD → READ_TOPOLOGY → S1 → S2 → RESOLVE →
DIFF → WRITE_BOARD → DECIDE → [WRITE_STAMP → READ_BACK → PRUNE →
WRITE_BOARD] → STOP.

A window with no S2 rows is **quiet**. A failed S1 is
`unavailable`: null counts, watermark **not** advanced, stamp
written. SSH NO_MATCH and successful auth are counts, never
readings.

## ThousandEyes visit

Everything is in `references/thousandeyes.md`: two reads, one
network-results call per metadata test (one per message), one
alerts call, build one row per test + agent, diff against the board
on `health/metadata-thousandeyes.json`, stamp or quiet, rewrite the
board.

Order: READ_BOARD → READ_TOPOLOGY → [AGENTS] → (per test: NETWORK)*
→ ALERTS → BUILD → DIFF → DECIDE → [WRITE_STAMP → READ_BACK →
PRUNE] → WRITE_BOARD → STOP.

Window is always `thousandeyes.window` from metadata (default `1h`);
no `7d`, no `24h`. State per row comes from the fixed rule (majority
of rounds with loss ≥ 5, mean loss ≥ 5, or no ok round). Loss moves
under 10 points are board-only. `alerts.firing` 0 is not proof of
health. No path-vis, no `te_get_alert`, no `te_raw_api_call`.

## Stamps

Stamp `YYYY-MM-DDTHH-MM-SSZ`. If that path exists, add 1 second.
Never overwrite. That stamp is `watch_id`. After a stamp write,
`read_file` it, then keep **at most 10** stamps under this source's
directory only (delete oldest first). Do not list other `health/`
directories. Do not write `health-board.md`. Do not
`execute_command`. Persist with `write_file` on catalog paths.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 12 |
| Splunk collection (`splunk_search`) | 2 (plus one retry each) |
| Splunk listing (resolve only) | 2 |
| ThousandEyes `te_get_test_results` | one per metadata test, one retry each |
| ThousandEyes `te_list_alerts` | 1 |
| ThousandEyes `te_agents_get_agents` | 1 (baseline / unknown agent) |
| ThousandEyes listing (resolve only) | 2 |

If over budget: stop querying, write what you have. Do not record a
source as empty if you never collected it.

Unavailable measurements are `null`, never `0`. Quote measurements
in the check `headline`.
