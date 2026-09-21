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
`buckets`. Splunk F2 samples stay off the stamp. After
standing-order path-vis, write `path_summary` for the worst test
only (`test_id`, `test_name`, `hops`, `last_error_hop`).

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

`metrics` one row per device that logged a signal. `name` is the
IOS hostname in the message, the same spelling as
inventory when that name exists. `scope` is `device:<name>`. Keys:
`bgp_adjchange` (`BGP-5-ADJCHANGE`), `link_updown`
(`LINEPROTO-5-UPDOWN`), `config_i` (`CONFIG_I`). A window with
none of those is one row `scope` `window`, `name` null, counts 0.
Do not use total event count as the vital. DHCP `NO_LEASE` is not
a signal.

`readings` one row per device and subject this window (`kind`
`bgp` | `link` | `config`). BGP subject is `neighbor <id> Up` or
`Down`. Link subject is the interface and up or down. Cap 24.

There is no baseline until a prior stamp exists. First visit:
`delta` `first`, `changed` []. Store the rows anyway. Later
visit: diff this visit's `metrics` and `readings` against that
prior file. `changed` lists only what moved: the inventory name,
the signal, and the old value to the new value. `headline` is that
diff. Do not copy a name from this skill.

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
rounds dominate, **or** one direction has zero ok rounds. A first
visit with healthy rounds is `ok` and `delta` `first`. Record the
numbers. Do not set `unknown` because there is no prior stamp.
Observation
`headline` must quote rounds, loss, latency, jitter, error types,
and `alerts.firing` — not loss alone.

`metrics` one row per test and agent. `scope` is
`test:<testId>/<agentName>`. `name` is the API `testName`.
`agent` is the result agent name. `server` is `serverIp`. Keys:
`loss_pct` (mean on ok rounds), `latency_ms_avg`, `jitter_ms`,
`ok_rounds`, `error_rounds`. `latency_ms_p95` is null unless this
visit measured p95. Do not store every round.

First visit: `delta` `first`, `changed` []. Later visit: diff
each `scope` against the prior stamp. `changed` is only what
moved: the API test name and the old value to the new value.
`headline` is that diff. Do not copy a name from this skill.

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
