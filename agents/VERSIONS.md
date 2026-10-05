# Prompt versions

Deployed model is **MiniMax** unless noted.

| Agent | Version | Model |
|-------|---------|-------|
| Network Ops | 3.2.0 | Frontier (operator-selected; GitOps orchestration risk) |
| GitHub GitOps Change | 1.3.1 | MiniMax |
| Pipeline Monitor | 1.2.1 | MiniMax |
| Network Design | 3.2.2 | MiniMax |
| Ops Network Sync | 2.5.4 | MiniMax |
| Ops NetBox SoT | 1.5.2 | MiniMax |
| Ops ServiceNow | 1.5.1 | MiniMax |
| Ops ServiceNow Trends | 1.2.2 | MiniMax |
| Modernization Analysis | 2.0.1 | MiniMax |
| Modernization Lifecycle | 1.4.1 | MiniMax |
| Compliance | 1.1.0 | MiniMax |
| Compliance Intelligence | 2.0.4 | MiniMax |
| Compliance Author | 1.3.1 | MiniMax |
| Compliance Test | 1.5.0 | MiniMax |
| Health Monitor | 2.2.0 | MiniMax |
| Health Logging | 1.0.1 | MiniMax |
| Health Telemetry | 1.0.7 | MiniMax |
| Health Application | 1.0.1 | MiniMax |
| Health Device | 1.12.3 | MiniMax |
| Health ServiceNow | 1.8.1 | MiniMax |
| Health Analyzer | 5.0.0 | MiniMax |
| Relationship agent | 1.2.0 | MiniMax |
| Network Map | 1.0.1 | MiniMax |
| Application Map | 1.0.0 | MiniMax |

Health Device 1.12.3 (skill 1.12.6): each `execute_command` is a new container. `--workspace` is the `file_explorer` directory beside `skills` on the path Studio shows for the script. Notes separate on `=`. Boot times that are the same instant are not a reboot. Only `platform` `iosxe` is collected. Topology map is unchanged.

Health Logging 1.0.1 (skill 1.0.1): annotate accepts the summary `stamp` path. A bare watch id, or a trailing quote, still resolves to `health/splunk/<id>.json`.

workspace-handoff 1.70.3: `unwrap_grafana` pivots Grafana 13 columnar frames. Live NetFlow for the last hour is bucket `network-v2`, measurement `netflow`, five exporters.

Health Telemetry 1.0.7 (skill 1.0.7): the visit also reads the bucket measurement whose fields include `fw_event` and records deny rows. A new, changed, or cleared deny is material and a deny still in the window degrades the plane. Health Telemetry 1.0.6 (skill 1.0.6): same visit as the other nurses. Rewrite the nested board every visit. Stamp only on the first visit, a material row, or coverage that is not complete. Annotate only when `needs_note` is not empty. A flat board already on disk is read, then written in the schema shape. Health Telemetry 1.0.5 (skill 1.0.5): every completed visit updates `health/metadata-netflow.json` in the flat shape already on disk and writes `health/netflow/<stamp>.json` with `vs_prior`. The headline is the opinion, set by annotate. Health Telemetry 1.0.4 (skill 1.0.4): a board whose provenance is `bucket` / `measurement` / `window` is saved as `provenance.netflow`. Health Telemetry 1.0.3 (skill 1.0.3): collect reads a flat `health/metadata-netflow.json` (bucket and measurement at the top level, as in the workspace capture) as well as a nested `netflow` object. Health Telemetry 1.0.2 (skill 1.0.2): a missing `netflow.bucket` is empty, not an error, so collect continues into Grafana discovery. Health Telemetry 1.0.1 (skill 1.0.1): `visit_netflow.py` takes bucket, measurement, and datasource from the board or from optional collect flags. When the board lookup is missing or F1 is empty, and `provenance.netflow` is not `user`, the script lists Influx datasources, lists buckets with `buckets()`, and keeps the measurement whose tags match the flow queries. Health Monitor 2.2.0 is unchanged.
