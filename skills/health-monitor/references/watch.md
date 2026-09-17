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
`headline`, `coverage`, `metrics`, `vs_prior`. Do not write
`summary` that restates `metrics`. Do not write `tests[]`,
`by_mnemonic`, `samples`, `top_hosts`, or `buckets` unless a
standing-order follow-up produced **one** extra fact (TE:
`tests[]` with only the worst test’s `path_summary` after
path-vis). Splunk F2 samples stay off the stamp.

Required `metrics` on the observation: same keys every visit;
explicit `null` when not collected.

## Shared order

1. `read_file` this visit’s metadata
   (`health/metadata-splunk.json` or
   `health/metadata-thousandeyes.json`). Never
   `get_folder_structure`. Follow `references/metadata.md`.
2. If `last_visit_id` is set, `read_file`
   `health/<source>/<last_visit_id>.json` and compare.
3. Pick stamp `YYYY-MM-DDTHH-MM-SSZ`. If that path exists, add 1
   second. Never overwrite. That stamp is `watch_id`.
4. Collect (`references/demo-scope.md`). Write the **lab slip**
   (`headline`, `coverage`, `metrics`, `vs_prior`), then
   `read_file`. Do not paste the tool JSON into extra arrays.
5. Write this visit’s metadata (`last_visit_id`, Splunk watermark
   when applicable). Keep **at most 10** stamps under
   `health/<this source>/`. After the new write, delete older stamp
   files in **that directory only** (oldest first) so 10 remain.
   Do not overwrite. Do not list other `health/` directories. Do
   not write `health-board.md`. Do not `execute_command`. Persist
   with `write_file` on catalog paths.

## Splunk visit

Window from `health/metadata-splunk.json` (`collected_through` or
bootstrap) — not another rolling `-24h`. Run B1–B4 then **always
F1**. F2 only if a bucket is interesting.

Host set change is coverage, not by itself `degraded`. Missing a
quiet host is not a down device. Severity alone does not set
`degraded`. SSH-NO_MATCH is a finding, not `degraded`. Do not
collect another source.

Empty successful window → `complete`, zeros allowed, advance
watermark to `checked_at`. MCP/timeout → `unavailable`, null
counts, **do not** advance the watermark.

`metrics` one row `scope` `window`. Keys: `event_count`,
`critical_error_count`, `flap_count`, `unique_hosts`.

## ThousandEyes visit

Window `1h` from `health/metadata-thousandeyes.json`. Baseline:
`te_get_test_results` `result_type=network` for each metadata test,
then `te_list_alerts(state="trigger", window="1h")`. Empty alerts
means no rule bound, not a healthy path.

Follow-up when any test has loss ≥ 5%, majority `errorType`, or
zero ok rounds: one `path-vis` `window=1h` on the worst direction;
one `te_get_alert` if firing; one `te_agents_get_agents` with
`agent_types` (e.g. `["enterprise"]`) if `INTERNAL_ERROR`
dominates. Listing agents without `agent_types` is rejected. MCP
`ok: true` plus per-round errors is a failed path, not a failed
tool.

No 24h windows. No listing tests when metadata already has ids. No
`te_raw_api_call`. Do not create tests.

Plane `degraded` when: loss ≥ 5% on an ok round, **or** error
rounds dominate, **or** one direction has zero ok rounds. First
visit: record the numbers; empty history is not `ok`. Observation
`headline` must quote rounds, loss, latency, jitter, error types,
and `alerts.firing` — not loss alone.

`metrics` one row per test `scope` `test:<id>`. Keys: `loss_pct`,
`latency_ms_p95` (null unless this visit measured p95 — do not
invent from avg), `latency_ms_avg`, `jitter_ms`, `ok_rounds`,
`error_rounds`.

Do not collect another source. Set `last_visit_id` on TE metadata
after a successful write of the stamp.

## Call budget

| Item | Max |
|------|----:|
| Workspace file read/write | 20 |
| Splunk collection (`splunk_search`) | 6 |
| Splunk listing (resolve only) | 2 |
| ThousandEyes result calls | 6 |
| ThousandEyes listing (resolve only) | 2 |

If over budget: stop querying, write what you have. Do not record a
source as empty if you never collected it.

Unavailable measurements are `null`, never `0`. Quote measurements
in the check `headline`.
