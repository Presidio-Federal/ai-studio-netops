# Health Agents

The watch and chart for the production network. Nurses collect one
telemetry plane per visit. Health Analyzer does not collect — it reads
the latest stamps, folds a metric series, and writes the rollup.

One source per conversation. A Splunk visit does not pull ThousandEyes
or IOS-XE. Correlation is not root cause. “No critical errors” is one
fact; the visit still reports volume, hosts, coverage, and what this
source actually measured.

Live lookup ids and the Splunk watermark live in metadata, not in the
prompt.

## Agents

| Agent | Role | Writes |
|-------|------|--------|
| Health Monitor | Named Splunk **or** ThousandEyes visit | That plane’s stamp and metadata |
| Health Device | IOS-XE RESTCONF GET | `health/iosxe/<stamp>.json` |
| Health ServiceNow | Read-only tickets for this lab | ServiceNow stamp and metadata |
| Health Analyzer | Chart — observation only | `state/health.json` |

Nurses do not write `state/`. Analyzer does not write visit files.

## Health Monitor

One named check. Unnamed invoke asks which and stops.

**Splunk** — syslog for the lab index and sourcetype. Window is the
watermark (`collected_through`), not another rolling 24 hours.
Interprets hosts, volume, flaps, and errors.

**ThousandEyes** — path tests: loss, latency, jitter, errors, alerts,
bounded path vis. Account and test ids come from metadata or a
discover-then-ask resolve.

## Health Device

Device plane only. GET interfaces, BGP, and counters. ACL GET only
when a ranked up port is dropping. Rank from `inventory/prod.json`.
Does not change config. PAT port is on inventory — there is no IOS-XE
metadata file.

## Health ServiceNow

Tickets for **this lab**, scoped by a workspace marker and inventory
labels. Shared-instance rows are out of scope. Open in-scope tickets
do not degrade vital status. This agent does not file or update
cases — that is [ServiceNow Agents](servicenow-agents.md).

## Health Analyzer

The chart. Freshness is 26 hours from `checked_at`. Vital status is
worst of ThousandEyes, Splunk, and IOS-XE. ServiceNow does not vote.
Silent plane is not health.

- **assess-now** — dispatch stale nurses if attached; do not wait;
  chart what is on disk.
- **refresh-then-assess** — wait only for planes that are both stale
  and material (a WAN question does not block on ticket history).

`series` is copied from visit metrics. The headline is regenerated
from the series every invoke. No recommendations.

## Invoke lines

- `Run the Splunk health check only.`
- `Run the ThousandEyes health check only.`
- `Run the network device health check only.`
- `Run the ServiceNow health check only.`
