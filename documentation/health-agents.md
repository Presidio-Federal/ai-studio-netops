# Health Agents

Health is the watch and chart for the production network. Four
**nurses** each collect one telemetry plane. **Health Analyzer** does
not collect; it reads the latest stamps and writes the rollup.

One source per conversation. A Splunk visit does not pull ThousandEyes
or IOS-XE. Live lookup ids live in metadata files, not in the prompt.

## Agents in this repo

| Agent | Prompt | Skill | Writes |
|-------|--------|-------|--------|
| Health Monitor | `agents/health-monitor-agent.md` | `health-monitor` | Splunk or ThousandEyes stamp + that plane’s metadata |
| Health Device | `agents/health-device-agent.md` | `health-device` | `health/iosxe/<stamp>.json` |
| Health ServiceNow | `agents/health-servicenow-agent.md` | `health-servicenow` | ServiceNow stamp + `health/metadata-servicenow.json` |
| Health Analyzer | `agents/health-analyzer-agent.md` | `health-analyzer` | `state/health.json` only |

Nurses do not write `state/`. Analyzer does not write `health/`.

## Health Monitor

Runs **one** named check: Splunk or ThousandEyes. An unnamed invoke
asks which check and stops.

- Splunk: search that index/sourcetype; watermark in
  `health/metadata-splunk.json`
- ThousandEyes: test results and alerts; ids in
  `health/metadata-thousandeyes.json`

Writes one new `health/<source>/<stamp>.json`. Keeps at most 10 stamps
per source. Does not write `state/health.json`.

## Health Device

IOS-XE RESTCONF **GET** only. Reads `inventory/prod.json` for the
RESTCONF port. Host and credentials stay on the MCP server.

Writes `health/iosxe/<stamp>.json`. No metadata file — PAT is on
inventory, not `health/metadata-iosxe.json`. Does not list prior
stamps.

## Health ServiceNow

Read-only find/get for **this lab’s** tickets. Scope comes from
`health/metadata-servicenow.json` (`servicenow.marker`) and inventory
labels. Shared-instance rows are out of scope.

Writes `health/servicenow/<stamp>.json`. Open in-scope tickets do not
degrade vital status. This agent does not file or update tickets.

## Health Analyzer

The chart. Reads metadata + latest stamps, folds metric `series`,
judges freshness (26 hours from `checked_at`), and replaces
`state/health.json`.

- Vital rollup is worst of ThousandEyes, Splunk, and IOS-XE.
  ServiceNow does not vote.
- `assess-now` (default): dispatch stale nurses if attached; do not
  wait; chart what is on disk.
- `refresh-then-assess`: wait only for planes that are both stale and
  material to the question.

Observation only. Correlation is not root cause. Does not write
recommendations.

## Shared catalog

Paths, writers, and dispatch lines live in
`skills/workspace-handoff`. Analyzer invoke lines:

- `Run the Splunk health check only.`
- `Run the ThousandEyes health check only.`
- `Run the network device health check only.`
- `Run the ServiceNow health check only.`
