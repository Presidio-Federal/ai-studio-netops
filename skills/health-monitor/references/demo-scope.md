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

B1 and B2 are for coverage only. They do not become `metrics`.
`metrics` are the per-device signal counts in `references/watch.md`.

**B3 — every host.** Use the IOS hostname in the message as `name`
on the device row. Do not write a host list on the stamp.

```
index=<index> sourcetype=<sourcetype>
| rex field=_raw "\d+: (?<ios_hostname>[A-Za-z0-9._-]+): \*"
| stats count, min(_time) as first_seen, max(_time) as last_seen, values(ios_hostname) as ios_hostname by host
| sort -count
```

**B4 — facility × mnemonic × sev.** `head 25` **after** `stats`. Use
facility and mnemonic in the headline when they explain the window.
Do not write `by_mnemonic` on the stamp. Never store facility inside
the mnemonic token.

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

**F2 — always** for any link, routing, config, or auth bucket,
including `AUTH_PASSED`: host × mnemonic, `head 20`. Samples are
not required. Samples never set a count. SSH-NO_MATCH is a finding
on that device's note. It does not set `degraded` by itself.

**Zero rows:** B1 returning 0 after a successful search is an empty
window (`complete`, zeros allowed). MCP/timeout with no extract is
`unavailable`: counts **null**, never `0`; do not advance the watermark.

The first visit searches from the oldest event still stored, not
`-24h`. Read `inventory/prod.json` and `inventory/infra-sot.json`
before writing rows. One physical device is one row. Match the
parsed hostname and the syslog host address to the same inventory
`name` (`devices[].name`, `interfaces[].cidr`, or `access.*.host`).
Sum the counts. Do not keep both the address and the hostname.
`metrics` is one row per inventory device that logged anything other
than DHCP `NO_LEASE`. `name` and `scope` are `device:<inventory name>`.
Signal counts may be 0. `readings` include BGP
neighbor up/down, interface up/down, config commits, and auth
mnemonics such as `AUTH_PASSED`. Cap 64. `scope` `window` only
when no such device logged. First visit: `delta` `first`,
`changed` [], and the rows are the baseline. Later visit:
`changed` is the diff against the prior stamp. `headline` is the
nurse's opinion of that baseline or that diff. The stamp has no
`by_mnemonic`, `top_hosts`, `buckets`, `samples`, or `summary`.
F2 supplies the subject line for link, routing, config, and auth.
It is not a sample dump. Do not advance `collected_through` until
those device rows are written.

Severity alone does not set `degraded`. SSH-NO_MATCH is a finding.

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
