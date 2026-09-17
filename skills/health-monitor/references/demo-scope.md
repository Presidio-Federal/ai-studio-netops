# Health extract

Ids come from `health/metadata-splunk.json` or
`health/metadata-thousandeyes.json`. Read that file before telemetry
MCP. If ids are missing, resolve in `references/metadata.md` (discover,
then ask with options if more than one fits). Write metadata. Then
extract. Do not put live index names or test ids in this file or the
prompt. Do not paste raw tool JSON into the check file.

## Splunk — `splunk-syslog/v2`

Use on a **Splunk visit** only. Do not call ThousandEyes or IOS-XE.

Substitute `index` and `sourcetype` from metadata on every search.
Window from `references/metadata.md` (`collected_through` or bootstrap)
as MCP `earliest_time` / `latest_time`. **Do not** put `earliest=` in
the query. Do not use a rolling `-24h` when `collected_through` is set.
`max_results` 50 for aggregates.

Syslog events have `_raw` and `host`. They do **not** have `severity`
or `log_level`. Facility, severity, and mnemonic come from
`%FACILITY-SEV-MNEMONIC` in `_raw`. Never `stats ... by severity` or
`by log_level`. Never invent SPL.

**B1 — window totals (no rex).** `event_count`, `unique_hosts`, first/last.

```
index=<index> sourcetype=<sourcetype>
| stats count as event_count, dc(host) as unique_hosts, min(_time) as first_event, max(_time) as last_event
```

**B2 — severity including unparsed.** `by_severity` (integer sev only),
`parsed_count`, `critical_error_count` (parsed sev <= 3).

```
index=<index> sourcetype=<sourcetype>
| rex field=_raw "%(?<facility>[A-Z0-9_]+)-(?<sev>\d+)-(?<cisco_mn>[A-Z0-9_]+)"
| eval sev_key=if(isnull(sev),"unparsed",sev)
| stats count as event_count, dc(host) as hosts, min(_time) as first_event, max(_time) as last_event by sev_key
```

`event_count` on the check is the **sum of B2 rows** (includes unparsed).
It must match B1 when B1 succeeded. `parsed_count` is total minus unparsed.

**B3 — every host.** Cap `top_hosts` at 10 in the file after a full
`stats by host`.

```
index=<index> sourcetype=<sourcetype>
| rex field=_raw "\d+: (?<ios_hostname>[A-Za-z0-9._-]+): \*"
| stats count, min(_time) as first_seen, max(_time) as last_seen, values(ios_hostname) as ios_hostname by host
| sort -count
```

**B4 — facility × mnemonic × sev.** `head 25` **after** `stats`. Write
`facility` and `mnemonic` (`cisco_mn`) separately — never store facility
in `mnemonic`. `hosts` on `by_mnemonic` is a string array of IPs, or
**omit** the field. Never put `host_count` in `hosts`.

```
index=<index> sourcetype=<sourcetype>
| rex field=_raw "%(?<facility>[A-Z0-9_]+)-(?<sev>\d+)-(?<cisco_mn>[A-Z0-9_]+)"
| stats count, dc(host) as host_count, max(_time) as last_seen by facility, cisco_mn, sev
| sort -count
| head 25
```

**F1 — signal buckets. Always run** after B4.

```
index=<index> sourcetype=<sourcetype>
| rex field=_raw "%(?<facility>[A-Z0-9_]+)-(?<sev>\d+)-(?<cisco_mn>[A-Z0-9_]+)"
| eval bucket=case(
  match(facility,"LINEPROTO|LINK") OR cisco_mn="UPDOWN", "link",
  match(facility,"BGP|OSPF|EIGRP|DUAL") OR match(cisco_mn,"ADJCHANGE|ADJCHG|NBRCHANGE|NBR_RESET"), "routing",
  cisco_mn="CONFIG_I" OR match(cisco_mn,"SYNC_NEEDED|SYNC_START|SYNC_COMPLETE"), "config",
  match(facility,"SEC_LOGIN|SSH|AAA|SECURE") OR match(cisco_mn,"AUTH_PASSED|LOGIN"), "auth",
  match(cisco_mn,"CPUHOG|MEMORY|STACKLOW"), "resource",
  isnull(facility), "unparsed",
  1=1, "other")
| stats count, dc(host) as hosts by bucket
```

Do not classify all `DMI` as auth. `SYNC_*` is NETCONF config-sync.
`flap_count` = link + routing bucket counts. Never set `flap_count`
from a sample.

**F2 — only if** a bucket is interesting (link, routing, resource, or
auth that is not routine SSH-NO_MATCH): (a) host×mnemonic for routing
or link only, `head 20`; or (b) up to 5 truncated `_raw` samples from
that bucket. Samples never set `event_count` or `flap_count`.

**Zero rows:** B1 returning 0 after a successful search is an empty
window (`complete`, zeros allowed). MCP/timeout with no extract is
`unavailable`: counts **null**, never `0`; do not advance the watermark.

Write the **lab slip**: `headline`, `coverage`, `metrics` (one
row `scope` `window`), `vs_prior`. Do **not** write `by_mnemonic`,
`top_hosts`, `buckets`, `samples`, or a `summary` that restates
metrics. F2 is for your judgment of `headline` / `status` only.

Severity alone does not set `degraded`. SSH-NO_MATCH is a finding.

## ThousandEyes — network extract

Use on a **ThousandEyes visit** only. Do not call Splunk or IOS-XE.

`aid` and `tests[].test_id` come from `health/metadata-thousandeyes.json` — not from
this file. If they are missing, resolve per `references/metadata.md`
and write metadata before collecting. Write `test_name` from the TE
result. Window from metadata or `1h`. Never `24h`.

**Baseline (always):**

1. `te_get_test_results` for each metadata test (`result_type="network"`,
   window from metadata or `1h`)
2. `te_list_alerts(state="trigger", window="1h")` — always. Empty means
   no rule is bound, not that the path is healthy.

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
per test `scope` `test:<id>`), `vs_prior`, `alerts.firing`. Do
**not** write a `tests[]` dump of every round. After standing-order
path-vis, you may add `tests[]` with **only** the worst test’s
`test_id`, `test_name`, and `path_summary` (`hops`,
`last_error_hop`). Cap; do not dump hops.

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
rounds. First visit: record the numbers; do not treat empty as `ok`.

Headline must include rounds, loss, latency, jitter, error types, and
`alerts.firing` — not loss alone.

Do not call the other telemetry source. Do not collect another health
source.
