# Workspace contract — Network Map

Paths are `workspace-handoff` catalog rows. Nothing else.

## Reads (by the script, not by you)

| Path | Writer | Required |
|------|--------|----------|
| `inventory/prod.json` | Ops Network Sync | yes |
| `inventory/applications.json` | Application Map | no |
| `inventory/map-layout.json` | operator | no |
| `state/relationships.json` | Relationship agent | no |
| `state/health.json` | Health Analyzer | no |
| `state/compliance.json` | Compliance | no |
| `state/testing.json` | Compliance Test | no |
| `state/network-ops.json` | Network Ops | no |
| `state/servicenow.json` | Ops ServiceNow Operator | no |
| `state/network-sync.json` | Ops Network Sync | no |
| `health/metadata-application.json` | Health Application | no |
| `health/metadata-netflow.json` | Health Monitor | no |
| `health/metadata-splunk.json` | Health Monitor | no |
| `health/metadata-iosxe.json` | Health Device | no |

You, the agent, read at most one file yourself: `state/health.json`
(headline, for the reply). Everything else is the script's business.

## Writes (by the script)

| Path | Kind | Notes |
|------|------|-------|
| `reports/network-map.html` | derived artifact | overwritten every run; no envelope; no `keys`; no other agent reads it |
| `reports/network-map.json` | derived artifact | only with `--json`, for inspection |

No `state/`, no `health/`, no `inventory/` writes. No stamps. No
`relations[]`. Nothing for the Relationship agent to copy.

## Freshness

The page is as fresh as the boards. The footer lists each board's
own timestamp; `missing_boards` lists what was not there. If the
operator wants newer telemetry, the nurse (Health Application,
Health Monitor) runs first and the map is rebuilt after.
