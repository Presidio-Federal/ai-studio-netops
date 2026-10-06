# Prompt versions

Deployed model is **MiniMax** unless noted.

| Agent | Version | Model |
|-------|---------|-------|
| Network Ops | 3.2.0 | Frontier (operator-selected; GitOps orchestration risk) |
| GitHub GitOps Change | 1.3.1 | MiniMax |
| Pipeline Monitor | 2.0.0 | MiniMax |
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
| Compliance Test | 1.7.1 | MiniMax |
| Health Monitor | 2.2.0 | MiniMax |
| Health Logging | 1.0.1 | MiniMax |
| Health Telemetry | 1.0.7 | MiniMax |
| Health Application | 1.2.0 | MiniMax |
| Health Device | 1.12.3 | MiniMax |
| Health ServiceNow | 1.8.1 | MiniMax |
| Health Analyzer | 5.0.0 | MiniMax |
| Relationship agent | 1.2.0 | MiniMax |
| Network Map | 1.0.1 | MiniMax |
| Application Map | 1.0.0 | MiniMax |

Pipeline Monitor 2.0.0 (github-actions skill 4.5.0): the watch is one `execute_command` of `scripts/watch_run.py`, same orchestration as the Splunk and Grafana visit scripts. The script polls, judges the live marker, and writes `operational/runs`. The agent reads the last stdout line.

Compliance Test 1.7.1 (skill 1.11.1): a running summary includes `phase` from the job steps `Static pytest` and `Live pyATS`. The agent says that phase and resumes with `--run-id` and `--phase`. The finished visit is unchanged.

Compliance Test 1.7.0 (skill 1.11.0): `scripts/run_suite.py` dispatches `test.yml`, polls, and writes the visit. A compliance job's static block and live block both land in `compliance-test-visit/v3`. The agent reads the script's last line. Static failures are rows; static passes stay on the count line.

Network Map skill 1.2.1: a container joins a CMDB tier when its name is the tier or a hyphen prefix plus the tier (`dc-api`, `prod-api` → `api`). The label is not renamed. Unmatched containers stay on their own row.

Network Map skill 1.2.0 (agent prompt stays 1.0.1, workspace-handoff 1.70.5): the page keeps a tested-posture percent and a voting-plane health percent in the header, side cards start closed, and a Trend toggle draws the compliance series plus application, NetFlow, and IOS-XE percents. Tiers with no service inherit it along `depends_on`. Check counts and failing-device badges fall back to the compliance series and finding keys when `state/testing.json` does not carry them.

Health Device 1.12.3 (skill 1.12.6, workspace-handoff 1.70.4): a `call_mcp` raise is a failed GET, not a dead visit. Tool-not-found is not retried. Topology map is unchanged.

Health Logging 1.0.1 (skill 1.0.1): annotate accepts the summary `stamp` path. A bare watch id, or a trailing quote, still resolves to `health/splunk/<id>.json`.

workspace-handoff 1.70.3: `unwrap_grafana` pivots Grafana 13 columnar frames. Live NetFlow for the last hour is bucket `network-v2`, measurement `netflow`, five exporters.

Health Application 1.2.0 (skill 1.2.0): probe `duration_ms` is material when it crosses `latency_threshold_ms` (default 500) or moves 3× against the board row. A probe still over that line degrades the plane. The value stays on the board when the move is smaller.

Health Application 1.1.1 (skill 1.1.1): prior visit rows carried a `scope` the board schema does not allow. The script keeps the visit fields and drops the rest, so an older board still saves.

Health Application 1.1.0 (skill 1.1.0): the visit runs `visit_application.py`. The script calls Prometheus targets, the twelve expressions in `references/prometheus.md`, and the annotation list, then diffs the board. Stamp only when a row moved, on the first visit, or when coverage is not complete. Annotate only when `needs_note` is not empty. Health Monitor is unchanged.

Health Telemetry 1.0.7 (skill 1.0.7): the visit also reads the bucket measurement whose fields include `fw_event` and records deny rows. A new, changed, or cleared deny is material and a deny still in the window degrades the plane. Health Telemetry 1.0.6 (skill 1.0.6): same visit as the other nurses. Rewrite the nested board every visit. Stamp only on the first visit, a material row, or coverage that is not complete. Annotate only when `needs_note` is not empty. A flat board already on disk is read, then written in the schema shape. Health Telemetry 1.0.5 (skill 1.0.5): every completed visit updates `health/metadata-netflow.json` in the flat shape already on disk and writes `health/netflow/<stamp>.json` with `vs_prior`. The headline is the opinion, set by annotate. Health Telemetry 1.0.4 (skill 1.0.4): a board whose provenance is `bucket` / `measurement` / `window` is saved as `provenance.netflow`. Health Telemetry 1.0.3 (skill 1.0.3): collect reads a flat `health/metadata-netflow.json` (bucket and measurement at the top level, as in the workspace capture) as well as a nested `netflow` object. Health Telemetry 1.0.2 (skill 1.0.2): a missing `netflow.bucket` is empty, not an error, so collect continues into Grafana discovery. Health Telemetry 1.0.1 (skill 1.0.1): `visit_netflow.py` takes bucket, measurement, and datasource from the board or from optional collect flags. When the board lookup is missing or F1 is empty, and `provenance.netflow` is not `user`, the script lists Influx datasources, lists buckets with `buckets()`, and keeps the measurement whose tags match the flow queries. Health Monitor 2.2.0 is unchanged.
