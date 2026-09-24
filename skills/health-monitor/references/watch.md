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
`te_list_alerts`. Do not call Splunk or other health MCPs.

## This plane only

The observation file is **this visit’s plane** (`ok` / `degraded` /
`unknown`). Do not write `state/`. Do not read or write another
plane.

Check `headline` quotes this plane’s measurements. `vs_prior` is
required: compare to the prior stamp of **this** source
(`last_visit_id`). First visit: `prior_watch_id` null, `delta`
`first`, `changed` [].

The observation is a **lab slip**, not a MCP dump. Required:
`headline`, `coverage`, `metrics`, `vs_prior`. The stamp has no
`summary`, `tests[]`, `by_mnemonic`, `samples`, `top_hosts`, or
`buckets`. After standing-order path-vis, write `path_summary` for
the worst test only (`test_id`, `test_name`, `hops`,
`last_error_hop`).

Required `metrics` on the observation: same keys every visit;
explicit `null` when not collected.

## Splunk visit

Everything is in `references/splunk.md`: three reads, two searches
(three on the baseline), resolve hosts, diff against the board on
`health/metadata-splunk.json`, stamp or quiet, rewrite the board.

Order: READ_BOARD → READ_PROD → READ_TOPOLOGY → [S0] → S1 → S2 →
RESOLVE → DIFF → DECIDE → [WRITE_STAMP → READ_BACK → PRUNE] →
WRITE_BOARD → STOP.

The board's `current[]` is the prior state; do not open the prior
stamp. A window with no S2 rows is **quiet**: no stamp, board only,
watermark advanced. A failed S1 is `unavailable`: null counts,
watermark **not** advanced, stamp written. SSH NO_MATCH and
successful auth are counts, never readings. Do not collect another
source.

## ThousandEyes visit — shared order

1. `read_file` `health/metadata-thousandeyes.json`. Never
   `get_folder_structure`. Follow `references/metadata.md`.
2. If `last_visit_id` is set, `read_file`
   `health/thousandeyes/<last_visit_id>.json` and compare.
3. Pick stamp `YYYY-MM-DDTHH-MM-SSZ`. If that path exists, add 1
   second. Never overwrite. That stamp is `watch_id`.
4. Collect (`references/demo-scope.md`). Write the **lab slip**
   (`headline`, `coverage`, `metrics`, `vs_prior`), then
   `read_file`. Do not paste the tool JSON into extra arrays.
5. Write this visit’s metadata (`last_visit_id`). Keep **at most
   10** stamps under `health/thousandeyes/`. After the new write,
   delete older stamp files in **that directory only** (oldest
   first) so 10 remain. Do not overwrite. Do not list other
   `health/` directories. Do not write `health-board.md`. Do not
   `execute_command`. Persist with `write_file` on catalog paths.

## ThousandEyes visit

First visit (no `last_visit_id`): `te_get_test_results` window
`7d`. If the tool rejects it, `24h`, then the metadata window.
Later visits: window from `health/metadata-thousandeyes.json` or
`1h`. Baseline:
`te_get_test_results` `result_type=network` for each metadata test,
then `te_list_alerts(state="trigger", window=<that same window>)`.
Empty alerts means no rule bound, not a healthy path. Every test
and agent is a row, including a test that returned no result.

Follow-up when any test has loss ≥ 5%, majority `errorType`, or
zero ok rounds: one `path-vis` on the same window as the results,
on the worst direction;
one `te_get_alert` if firing; one `te_agents_get_agents` with
`agent_types` (e.g. `["enterprise"]`) if `INTERNAL_ERROR`
dominates. Listing agents without `agent_types` is rejected. MCP
`ok: true` plus per-round errors is a failed path, not a failed
tool.

Later visits do not use a 24h window. No listing tests when metadata already has ids. No
`te_raw_api_call`. Do not create tests.

Plane `degraded` when: loss ≥ 5% on an ok round, **or** error
rounds dominate, **or** one direction has zero ok rounds. A first
visit with healthy rounds is `ok` and `delta` `first`. Record the
numbers. Do not set `unknown` because there is no prior stamp.
Observation
`headline` must quote rounds, loss, latency, jitter, error types,
and `alerts.firing` — not loss alone.

`metrics` one row per test and agent. `scope` is
`test:<testId>/<agentName>`. `keys` lists every join key that
result contains, including `test:<testId>` and `device:<inventory
name>` when the payload names an inventory device. `note` on each row is the nurse's opinion: loss, latency, jitter, ok and error rounds, and what moved since the prior stamp. If path-vis ran on this test, say where it failed. A sentence that only says loss rose is not a note. `name` is the API `testName`.
`agent` is the result agent name. `server` is `serverIp`. Keys:
`loss_pct` (mean on ok rounds), `latency_ms_avg`, `jitter_ms`,
`ok_rounds`, `error_rounds`. `latency_ms_p95` is null unless this
visit measured p95. Do not store every round.

First visit: `delta` `first`, `changed` []. Later visit: diff
each `scope` against the prior stamp. `changed` is only what
moved: the API test name and the old value to the new value.
`headline` is the opinion across those notes, quoting the rounds,
loss, latency, and jitter. Do not copy a name from this skill.

Do not collect another source. Set `last_visit_id` on TE metadata
after a successful write of the stamp.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 20 |
| Splunk collection (`splunk_search`) | 3 (4 on the baseline) |
| Splunk listing (resolve only) | 2 |
| ThousandEyes result calls | 6 |
| ThousandEyes listing (resolve only) | 2 |

If over budget: stop querying, write what you have. Do not record a
source as empty if you never collected it.

Unavailable measurements are `null`, never `0`. Quote measurements
in the check `headline`.
