# ThousandEyes extract

Ids come from `health/metadata-thousandeyes.json`. Read that file
before the telemetry MCP. If ids are missing, resolve in
`references/metadata.md` (discover, then ask with options if more
than one fits). Write metadata. Then extract. Do not put test ids in
this file or the prompt. Do not paste raw tool JSON into the check
file.

Splunk visit: `references/splunk.md`, not this file.

## ThousandEyes — network extract

Use on a **ThousandEyes visit** only. Do not call Splunk or IOS-XE.

`aid` and `tests[].test_id` come from `health/metadata-thousandeyes.json` — not from
this file. If they are missing, resolve per `references/metadata.md`
and write metadata before collecting. Write `test_name` from the TE
result. First visit window is `7d` (then `24h` if rejected, then
the metadata window). Later visits use the metadata window or
`1h`.

**Baseline (always):**

1. `te_get_test_results` for each metadata test (`result_type="network"`,
   the first-visit window or the later-visit window above). One
   metrics row per test and agent, including a test that returned
   no result. The note says the loss, latency, jitter, and rounds,
   or that the direction is unknown.
2. `te_list_alerts(state="trigger", window=<that same window>)` —
   always. Empty means no rule is bound, not that the path is healthy.

Listing (`te_tests_get_tests`, `te_manage_account_groups`) only when
resolving metadata. Forbidden: agent listing on a healthy extract,
`result_type=api`, creating tests, `te_raw_api_call`.

**Follow-up** when any test has loss ≥ 5% on an ok round, majority
`errorType`, or zero ok rounds:

- one `te_get_test_results` `result_type="path-vis"` `window="1h"` on
  the worst direction
- one `te_get_alert` if `alerts.firing` > 0
- one `te_agents_get_agents` with `agent_types` (e.g. `["enterprise"]`)
  if `INTERNAL_ERROR` dominates

Write the **lab slip**: `headline`, `coverage`, `metrics` (one row
per test and agent, `scope` `test:<testId>/<agentName>`, `name`
from `testName`), `vs_prior`, `alerts.firing`. Do not store every
round. First visit: `delta` `first`, `changed` []. Later visit:
`changed` is only the diff of `loss_pct`, latency, jitter, and
rounds against the prior stamp. `headline` is that diff. After
standing-order path-vis, write `path_summary` for the worst test
only (`test_id`, `test_name`, `hops`, `last_error_hop`). Do not
dump hops.

Vitals on `metrics[]` come from each network result:

- `loss_pct` from mean loss on ok rounds (null when every round errored)
- `latency_ms_avg`, `jitter_ms` (null when no ok rounds)
- `latency_ms_p95` null unless this visit measured p95
- `ok_rounds`, `error_rounds`

Use `test_name` from the payload’s `test.testName` (do not require
`GET /tests/{id}`; that path 404s here). `first_round_at` /
`last_ok_at` inform the headline; they are not extra stamp arrays.

Live `results[]` rows (agent-to-agent `network`) carry **top-level**
`loss`, `avgLatency`, `jitter`, `date`, `direction`, `agent.agentName`,
`roundId`. They do **not** nest those under `metrics`. Healthy rounds
omit `errorType` — treat missing as ok. A round with `errorType` set is
an error round even when the MCP wrapper returns `ok: true`.

Top-level also needs `alerts` — `{ "firing", "items" }` cap 10.

`ok: true` on the MCP call plus per-round `errorType` means TE measured
a failed round. Check `ok: true` (collector answered) and plane
`status: degraded` when errors dominate.

Plane **degraded:** loss >= 5% on any recent ok round, **or** a
majority of rounds have `errorType`, **or** one direction has zero ok
rounds. A first visit with healthy rounds is `ok` and `delta`
`first`. Record the numbers. Do not set `unknown` because there
is no prior stamp.

Headline must include rounds, loss, latency, jitter, error types, and
`alerts.firing` — not loss alone.

Do not call the other telemetry source. Do not collect another health
source.
