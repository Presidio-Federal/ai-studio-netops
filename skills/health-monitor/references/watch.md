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

`metrics` one row per device that logged anything other than DHCP
`NO_LEASE`. `name` is the IOS hostname in the message when the
message has one, otherwise the event `host`. Same spelling as
inventory when that name exists. `scope` and `keys` are
`device:<name>`. Counts: `bgp_adjchange` (`BGP-5-ADJCHANGE`),
`link_updown` (`LINEPROTO-5-UPDOWN`), `config_i` (`CONFIG_I`).
Those counts may be 0. The row still exists. `scope` `window` with
`name` null is only when the search succeeded and no device logged
anything but DHCP. Do not use total event count as the vital.

`readings` one row per device and subject (`kind` `bgp` | `link`
| `config` | `auth`). BGP subject is `neighbor <id> Up` or `Down`.
Link subject is the interface and up or down. Config subject is
who changed it. Auth subject is the mnemonic, including
`AUTH_PASSED`. Cap 64. A device that logged `AUTH_PASSED` and no
BGP still gets a reading. DHCP `NO_LEASE` is not a reading.
`keys` on each row is every join key that payload contains:
`device:<inventory name>`, `interface:<name>` when the message
names an interface, and any other contract type present. Write
all of them. `note` on each row is the nurse's opinion for the higher agent.
First visit: what this device did in the history just read,
including a neighbor change, a link change, a config commit, or
an auth mnemonic. Later visit: what changed since the prior
stamp. A sentence that only says the window was quiet is not a
note.

The first visit is the baseline. `delta` `first`, `changed` [].
The rows are that baseline: every device, what it did, and the
note. Do not write an empty `readings` array when any device
logged. Later visit: diff this visit's `metrics` and `readings` against that
prior file. `changed` lists only what moved: the inventory name,
the signal, and the old value to the new value. `headline` is the
opinion across those notes: what recovered, what flapped, and
whether config was committed. Do not copy a name from this skill.

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
| Splunk collection (`splunk_search`) | 6 |
| Splunk listing (resolve only) | 2 |
| ThousandEyes result calls | 6 |
| ThousandEyes listing (resolve only) | 2 |

If over budget: stop querying, write what you have. Do not record a
source as empty if you never collected it.

Unavailable measurements are `null`, never `0`. Quote measurements
in the check `headline`.
