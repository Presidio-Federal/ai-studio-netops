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
| Ops ServiceNow Trends | 1.3.0 | MiniMax |
| Modernization Analysis | 2.5.0 | MiniMax |
| Modernization Lifecycle | 1.7.0 | MiniMax |
| Compliance | 1.2.1 | MiniMax |
| Compliance Intelligence | 2.0.4 | MiniMax |
| Compliance Author | 1.3.1 | MiniMax |
| Compliance Test | 1.8.1 | MiniMax |
| Health Monitor | 2.2.0 | MiniMax |
| Health Logging | 1.1.0 | MiniMax |
| Health Telemetry | 1.1.0 | MiniMax |
| Health Application | 1.3.0 | MiniMax |
| Health Device | 1.13.0 | MiniMax |
| Health ServiceNow | 1.9.0 | MiniMax |
| Health Analyzer | 5.1.0 | MiniMax |
| Relationship agent | 1.3.0 | MiniMax |
| Network Map | 1.0.2 | MiniMax |
| Application Map | 1.0.0 | MiniMax |

Network Ops skill 3.3.0 (agent prompt stays 3.2.0 until the Gate 3 rewrite): `network-ops-state/v3.3` adds `change.prescription`, `ci.passed_sha`, and `release`. GitOps Change skill 1.4.0: `scripts/submit_change.py` applies that prescription on `dev`.

Pipeline Monitor 2.0.0 (github-actions skill 4.5.0, workspace-handoff 1.70.16): `scripts/watch_run.py watch` is one `execute_command`, timeout 60. The script checks the run once. `running` is the same command plus `--run-id` and writes nothing. A finished watch writes `operational/runs`. Compliance Test skill stays 1.12.7. Its runner was not changed.

Modernization Analysis 2.5.0 (skill 2.5.0): assess writes the budget and the order windows from support dates, lead times, and every CCW offer. The opinion cites those figures.

Modernization Analysis 2.4.0 (skill 2.4.0): `state/lifecycle.json` items may carry `lead_time` and `offers` from Lifecycle. The analysis schema accepts them and `assess_estate.py` copies them through.

Modernization Lifecycle 1.7.0 (skill 1.7.0): `cisco_psirt_software` is called with `mode` `OSType`, `osType` (`iosxe` or `asa`), and the stored software version. Every EoX replacement candidate is priced, with lead time, in `offers`.

Modernization Lifecycle skill 1.6.2: one hardware EoX call and one software release per PID, then PSIRT and NVD. Cisco calls wait 0.6s. CCW lead time is stored on the estate row. A missing PSIRT list is not treated as finished.

Modernization Lifecycle skill 1.6.1: `collect` takes `product_id` from `inventory/assets/devices.json` and researches those PIDs. An estate that still lists only CML node types is not treated as current.

workspace-handoff 1.70.19: Cisco research and the roadmap moved from `lifecycle/` to `inventory/assets/`. The operator product list is `inventory/assets/devices.json`. `state/lifecycle.json` stays the rollup.

workspace-handoff 1.70.18: `inventory/assets.json` is the operator product-id overlay. Analysis seeds it from `inventory/prod.json` and copies `product_id` through. Lifecycle calls MCP only for those product ids.

workspace-handoff 1.70.17: Modernization Lifecycle `scripts/visit_lifecycle.py collect` runs under `mcp_orchestration` (Cisco EoX, PSIRT, NVD, CCW). `annotate` sets only the family ask. Modernization Analysis `scripts/assess_estate.py` runs under `standard` and does not call MCP.

workspace-handoff 1.70.15: `unwrap_github` reads `github_list_files`, `github_get_file`, and `github_put_file`. The tool dict is `{ok, entries}` or `{ok, content, sha}` or `{ok, sha, commit_sha}`. `result` on `call_mcp` is a list; `result[0]` is that dict.

Relationship agent 1.3.0 (skill 1.3.0): `scripts/compile_graph.py compile` copies nurse columns, CMDB declarations, and asserted relations into `state/relationships.json`. No MCP. Unchanged watermarks write nothing.

Health Analyzer 5.1.0 (skill 5.1.0): `scripts/assess_health.py assess` writes `state/health.json` from the five boards under `execution_type: standard`. It does not call MCP. `annotate` sets the verdict, hypotheses, relations, and Network Ops orders. Impact, freshness, and problem status stay on the script.

Ops ServiceNow Trends 1.3.0 (skill 1.3.0, workspace-handoff 1.70.12): the visit is one `execute_command` of `scripts/visit_trends.py collect` under `mcp_orchestration`. The script groups the same category and normalized title, writes the stamp, and the agent annotates theme and why. Empty scope asks unless `--schedule` is set. `kb` stays locked when close notes match.

Health ServiceNow 1.9.0 (skill 2.1.0, workspace-handoff 1.70.11): the visit is one `execute_command` of `scripts/visit_servicenow.py collect` under `mcp_orchestration`. The script queries, diffs, and writes the board and the stamp. The agent reads the last stdout line and runs `annotate` only when `needs_note` is set. `unwrap_snow` reads `{ok, rows}`.

Compliance 1.2.1 (skill 1.2.1): the chart scores come from the visit `metrics`. Findings still come from the failing rows.

Compliance Test skill 1.12.7: `results.ran` is empty. Failures are `results.by_device` only. The trend compares those lists.

Compliance Test skill 1.12.6: a compliance run still writes `operational/testing/<stamp>.json` because `state/testing.json` points there, and `compliance/testing/<stamp>.json` for the history. The stored rows are failures, errors, skips, and static passes that just cleared. `results.by_device` lists the failing check ids per device. Passes stay on the counts. A run whose suites do not include `compliance` writes operational only.

Compliance 1.2.0 (skill 1.2.0): `scripts/assess_chart.py` writes `state/compliance.json` from the visits on disk. The agent sets the opinion, the narrative, and the plan with `annotate`. It does not fold the series or score the chart.

An earlier Pipeline Monitor 2.0.0 note said the script polls inside one command. That design was not what shipped. The watch checks once and returns.

Compliance Test skill 1.12.5: a static failure that is gone on the next run in the same lab is a PASS row and `newly_passing`. The job names static failures, so that absence is the pass.

Compliance Test skill 1.12.4: `github_get_action_run` takes an integer `run_id`. The list-runs payload has no jobs, and a failed get is no longer replaced with that list.

Compliance Test 1.8.1 (skill 1.12.3): a missing job id is a script miss. The agent reports Result, Reason, and Run and does not tell the operator to re-dispatch. The reason line names the payload keys.

Compliance Test skill 1.12.2: a jobs list inside the run payload is a job id. The script no longer requires the job URL string. Run 37652149873 job id is 112897953597.

Compliance Test skill 1.12.1: the visit is filled from `NETWORK_TEST_RESULT_JSON`, the emit-result line. The log tool's old 500-line cap is raised to 20000 in the GitHub MCP server; Studio keeps the old cap until that server is redeployed.

Compliance Test 1.8.0 (skill 1.12.0): a workflow run id is not a job id. The log call uses only the id in `/runs/<run>/job/<id>`.

Compliance Test 1.7.9 (skill 1.11.9): one `python3` command per execute, timeout 60. A `running` result is not a shell loop and not a 400-second timeout.

Compliance Test 1.7.8 (skill 1.11.8): `github_get_action_run` returns `run.jobs[].id` (name, status, conclusion, html_url; no steps). The log tool requires that id and returns at most the last 500 lines.

Compliance Test 1.7.7 (skill 1.11.7): the log tool requires `job_id`. The script takes that id from a job object on the run (name + status, not only a `jobs` list) and does not call the log tool without it.

Compliance Test 1.7.6 (skill 1.11.6): the get-run result is a list, and the report is not always in the first item. The script keeps every item. It does not write an empty visit when the report text was never read.

Compliance Test 1.7.5 (skill 1.11.5): a short job-log tail has no `# Network test report`. The script reads `NETWORK_TEST_RESULT_JSON` from the end of the log, and it strips GitHub timestamps before parsing the report blocks. A finished result does not include a phase.

Compliance Test 1.7.4 (skill 1.11.4): `timeout` is 60. The script checks the run once and returns. The skill no longer says 300. A finished run writes the visit on that check.

Compliance Test 1.7.3 (skill 1.11.3): the command timeout is 120 seconds, not 300. A resume checks the run and returns within 20 seconds unless it is writing the visit. `running` carries `github_status`. The agent does not invent a phase or pass "still in progress".

Compliance Test 1.7.2 (skill 1.11.2): the poll checks the run before it sleeps. A finished job writes the visit in that call. The script returns `running` only when static or live tests start, or the four-minute budget runs out, not when a step ends.

Compliance Test 1.7.1 (skill 1.11.1): a running summary includes `phase` from the job steps `Static pytest` and `Live pyATS`. The agent says that phase and resumes with `--run-id` and `--phase`. The finished visit is unchanged.

Compliance Test 1.7.0 (skill 1.11.0): `scripts/run_suite.py` dispatches `test.yml`, polls, and writes the visit. A compliance job's static block and live block both land in `compliance-test-visit/v3`. The agent reads the script's last line. Static failures are rows; static passes stay on the count line.

Network Map skill 1.2.4: trend points keep the formula and counts. Hover shows the visit; click opens the drawer.

Network Map skill 1.2.3: Application Health, Health, and Compliance cards show a white title and a percent when closed. Open compliance lists the ten worst devices then critical findings; it does not paint the trend narrative.

Network Map 1.0.2 (skill 1.2.2): the compile command copies the Studio path of `build_map.py` and passes the `file_explorer` directory beside `skills` as `--workspace`. The words `Internal directory` are not a path. Do not `cd file_explorer`.

Network Map skill 1.2.1: a container joins a CMDB tier when its name is the tier or a hyphen prefix plus the tier (`dc-api`, `prod-api` → `api`). The label is not renamed. Unmatched containers stay on their own row.

Network Map skill 1.2.0 (agent prompt stays 1.0.1, workspace-handoff 1.70.5): the page keeps a tested-posture percent and a voting-plane health percent in the header, side cards start closed, and a Trend toggle draws the compliance series plus application, NetFlow, and IOS-XE percents. Tiers with no service inherit it along `depends_on`. Check counts and failing-device badges fall back to the compliance series and finding keys when `state/testing.json` does not carry them.

Health Device 1.13.0 (skill 1.13.0): MiniMax. Distinguishes reload, BGP session reset, interface transition, and boot-time skew. A shorter BGP `up_time` is re-establishment, not a reboot. Reboot only with boot-time beyond 5 seconds plus corroboration. Error/flap deltas over the visit interval; a drop is a counter reset. Admin-down vs `links[]` intended vs prior-board BGP expected. Keyed BGP reset-reason GET when a session is down. Unsaved config is a flag unless the boolean flips; no running/startup text (no verified GET). GET only.

Health Device 1.12.3 (skill 1.12.6, workspace-handoff 1.70.4): a `call_mcp` raise is a failed GET, not a dead visit. Tool-not-found is not retried. Topology map is unchanged.

Health Logging 1.1.0 (skill 1.1.0): S1 counts use a bounded window. S2 still collects from the watermark and is not treated as a rate. Deny rows keep source, destination, ports, protocol, ACL, and interface when the message has them. Config rows keep the actor and access method. A change reference stays empty when the syslog has none. Each reading keeps one trimmed evidence line, the event time, and the ingestion delay. The reply splits search, reporting coverage, and findings. A silent device is a pipeline question only when the operator set `source_registry` reporting to expected.

Health Logging 1.0.1 (skill 1.0.1): annotate accepts the summary `stamp` path. A bare watch id, or a trailing quote, still resolves to `health/splunk/<id>.json`.

workspace-handoff 1.70.10: the IOS-XE board catalog row names admin_status, intent, session up_time, prefixes_received, and reset_reason.

workspace-handoff 1.70.9: the Splunk catalog row names the bounded window, the watermark, deny and config fields, and the evidence line.

workspace-handoff 1.70.8: the NetFlow catalog row names identity, the top-N carry, the observed rate, and one observation point for estate totals.

workspace-handoff 1.70.7: the application catalog row names probe environment, content check, window latency, and container limit, throttle, and OOM columns.

workspace-handoff 1.70.3: `unwrap_grafana` pivots Grafana 13 columnar frames. Live NetFlow for the last hour is bucket `network-v2`, measurement `netflow`, five exporters.

Health Application 1.3.0 (skill 1.3.0): a probe row is application, destination environment, target, and vantage. The visit reports window failure and latency, a body-check result when `probe_failed_due_to_regex` exists, and container limit, throttle, and OOM when those series exist. Missing series and missing vantage points (cloud, hq, branch unless the board sets `expected_vantages`) stay missing. `last_collected_at` and `last_visit_id` both appear in the reply.

Health Application 1.2.0 (skill 1.2.0): probe `duration_ms` is material when it crosses `latency_threshold_ms` (default 500) or moves 3× against the board row. A probe still over that line degrades the plane. The value stays on the board when the move is smaller.

Health Application 1.1.1 (skill 1.1.1): prior visit rows carried a `scope` the board schema does not allow. The script keeps the visit fields and drops the rest, so an older board still saves.

Health Application 1.1.0 (skill 1.1.0): the visit runs `visit_application.py`. The script calls Prometheus targets, the twelve expressions in `references/prometheus.md`, and the annotation list, then diffs the board. Stamp only when a row moved, on the first visit, or when coverage is not complete. Annotate only when `needs_note` is not empty. Health Monitor is unchanged.

Health Telemetry 1.1.0 (skill 1.1.0): device identity requires fresh exact-interface, access-host, or exporter-name evidence. A stored owner that disagrees is conflicted, and `10.30.30.2` is written to `identity_review` when that list is empty so a containing subnet cannot assign it. A conversation missing from the top-N query is `not_in_top_n` with last bytes kept, not absent. `bytes_per_s` is the observed rate at that exporter and window. Estate totals use one observation point. Registry policy slots stay null unless the operator set them. The first visit under these rules is a baseline migration and is not `worse` only because identifiers changed. Silence is not a forwarding failure.

Health Telemetry 1.0.7 (skill 1.0.7): the visit also reads the bucket measurement whose fields include `fw_event` and records deny rows. A new, changed, or cleared deny is material and a deny still in the window degrades the plane. Health Telemetry 1.0.6 (skill 1.0.6): same visit as the other nurses. Rewrite the nested board every visit. Stamp only on the first visit, a material row, or coverage that is not complete. Annotate only when `needs_note` is not empty. A flat board already on disk is read, then written in the schema shape. Health Telemetry 1.0.5 (skill 1.0.5): every completed visit updates `health/metadata-netflow.json` in the flat shape already on disk and writes `health/netflow/<stamp>.json` with `vs_prior`. The headline is the opinion, set by annotate. Health Telemetry 1.0.4 (skill 1.0.4): a board whose provenance is `bucket` / `measurement` / `window` is saved as `provenance.netflow`. Health Telemetry 1.0.3 (skill 1.0.3): collect reads a flat `health/metadata-netflow.json` (bucket and measurement at the top level, as in the workspace capture) as well as a nested `netflow` object. Health Telemetry 1.0.2 (skill 1.0.2): a missing `netflow.bucket` is empty, not an error, so collect continues into Grafana discovery. Health Telemetry 1.0.1 (skill 1.0.1): `visit_netflow.py` takes bucket, measurement, and datasource from the board or from optional collect flags. When the board lookup is missing or F1 is empty, and `provenance.netflow` is not `user`, the script lists Influx datasources, lists buckets with `buckets()`, and keeps the measurement whose tags match the flow queries. Health Monitor 2.2.0 is unchanged.
