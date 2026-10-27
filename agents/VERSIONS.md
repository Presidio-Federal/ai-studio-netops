# Prompt versions

Deployed model is **MiniMax** unless noted.

| Agent | Version | Model |
|-------|---------|-------|
| Network Ops | 3.2.5 | Frontier (operator-selected; GitOps orchestration risk) |
| GitHub GitOps Change | 1.4.3 | MiniMax |
| Pipeline Monitor | 2.0.1 | MiniMax |
| Network Design | 3.2.2 | MiniMax |
| Ops Network Sync | 2.6.0 | MiniMax |
| Ops Firewall | 1.1.3 | MiniMax |
| SecOps Event Response | 1.0.4 | MiniMax |
| Ops NetBox SoT | 1.5.2 | MiniMax |
| Ops ServiceNow | 1.5.1 | MiniMax |
| Ops ServiceNow Trends | 1.3.0 | MiniMax |
| Modernization Analysis | 2.5.2 | MiniMax |
| Modernization Lifecycle | 1.7.0 | MiniMax |
| Compliance | 1.3.0 | MiniMax |
| Compliance Intelligence | 2.2.1 | Frontier (operator-selected; catalog and NIST interpretation) |
| Compliance Author | 1.4.0 | MiniMax |
| Compliance Test | 1.9.0 | MiniMax |
| Health Monitor | 2.2.0 | MiniMax |
| Health Logging | 1.2.0 | MiniMax |
| Health Telemetry | 1.3.4 | MiniMax |
| Health Application | 1.4.0 | MiniMax |
| Health Device | 1.13.0 | MiniMax |
| Health ServiceNow | 1.9.0 | MiniMax |
| Health Analyzer | 5.3.2 | Frontier (operator-selected; SOAP synthesis) |
| Relationship agent | 1.5.1 | MiniMax |
| Network Map | 1.2.0 | MiniMax |
| Application Map | 1.0.0 | MiniMax |
| Presentation | 1.2.6 | MiniMax |
| Presentation Builder | 1.2.1 | MiniMax |
| Ops CMDB Sync | 1.2.0 | MiniMax |

Relationship agent 1.5.1 (skill 1.5.1): a no-op prints the on-disk edge, drift, read, and lifecycle counts. The reply copies that JSON. It does not report 0 current because nothing was rewritten. MiniMax.

Network Map 1.2.0 (skill 1.4.0) and Relationship agent 1.5.0 (skill 1.5.0, workspace-handoff 1.70.34): the telemetry board names a path by `src` and `dst`, not `src_device`. A device arc or `flows_to` edge is copied only when both names are in `inventory/prod.json`. Exporter state comes from the exporter row. Firewall denies stay on the map and off the graph. Syslog attaches to a device only when `name` resolved; an address stays unresolved. Health Analyzer skill 5.3.3 reads those columns the same way. MiniMax.

SecOps Event Response 1.0.4: the only subagent is the attached Ops Firewall. A generic subagent is not used. The task is the web allow-list line, not a source deny. MiniMax.

SecOps Event Response 1.0.3: an API call's `sessions/<id>/file_explorer` is empty. The boards are read from the shared workspace beside `skills`. A miss in the session folder is not a missing board. MiniMax.

SecOps Event Response 1.0.2 (skill 1.0.2, workspace-handoff 1.70.37): one scan source is one IOS-XE edge. The task is `On <device>, permit tcp to any ports 80, 443, 8080, then deny ip to any.` Destination is `any`. No prefix, no firewall, no deploy. MiniMax.

Ops Firewall 1.1.1 (skill 1.1.1): a destination other than `any` must be one host address. A prefix is rejected. MiniMax.

SecOps Event Response 1.0.1 (skill 1.0.1): the visit reads every health board, then runs NetFlow F1–F4 and Splunk S1–S3 through `elasticsearch_query` and `splunk_search`. F4 and S3 are the scan signal. The block list keeps the client address F4 replaces with a name. MiniMax.

SecOps Event Response 1.0.0 (skill 1.0.0, workspace-handoff 1.70.35): an API call reads the health chart and the NetFlow and Splunk boards, then queries Elasticsearch and Splunk. The agent names a port scan from the spread. Each block is one Ops Firewall task, `Deny <source> to <destination> on <device>.` That task does not deploy an FTD. MiniMax.

Ops Firewall 1.1.3 (skill 1.1.3): the agent only adds the allow-list. A delete or reset is not this job. MiniMax.

Ops Firewall 1.1.2 (skill 1.1.2): the IOS allow-list is applied inbound on the LAN interface. The WAN is a /30 or 100.64.0.0/10 and is left alone. An interface that already has a different inbound ACL is left alone. Remove takes the access-group off before deleting the list. MiniMax.

 `apply_rule.py` writes `SCAN-ALLOW-WEB` under `mcp_orchestration`. IOS-XE permits TCP 80, 443, and 8080, then denies ip. FTD posts one permit for those port objects. The script writes `state/firewall.json`. A task is `On <device>, permit tcp to <destination> ports 80, 443, 8080, then deny ip to <destination>.` MiniMax.

Ops Firewall 1.0.1 (skill 1.0.1): `Deny <source> to <destination> on <device>.` is a write. One device. Deploy still requires the word deploy. MiniMax.

Ops Firewall 1.0.0 (skill 1.0.0, workspace-handoff 1.70.32): one live IOS-XE ACL or FTD access rule. Host and port come from `inventory/prod.json`. No credentials in the call. A write does not deploy. `ftd_deploy` runs only when the operator says deploy, and it deploys every pending change on that firewall. `state/firewall.json` is this invoke. MiniMax.

Ops Network Sync 2.6.0 (skill 1.10.0): `collect_inventory.py` reads the CML lab under `mcp_orchestration` and writes `inventory/prod.json` or `dev.json`, then `state/network-sync.json`. The agent does not parse the lab. `ftdv` is platform `ftd`. A device that left the lab stays. MiniMax.

Health Logging 1.2.1 (skill 1.2.1): an FTD hostname in the syslog text is used before the management IP. MiniMax.

Health Logging 1.2.0 (skill 1.2.0): FTD syslog is included with ASA. A source denied or allowed across 20 destinations or ports, or denied 100 times, is a stamp reading. The board keeps this window only. MiniMax.

Health Telemetry 1.3.4 (skill health-elastic 1.1.5): a port spread ignores destination ports at or above 32768. Those are the return path of a normal session, not a scan. MiniMax.

Health Telemetry 1.3.3 (skill health-elastic 1.1.4): the port-spread query sorts before it drops the port count, so a scan is a stamp reading. The board drops empty columns and paths that left the window. The stamp is the detail. MiniMax.

Health Telemetry 1.3.2 (skill health-elastic 1.1.3): a pair that uses 20 or more destination ports is a port spread. It is a finding and it degrades the plane. Byte rank no longer hides it. MiniMax.

Health Telemetry 1.3.1 (skill health-elastic 1.1.2): `visit_netflow.py` calls Elasticsearch through `visit_common.mcp_call`, the same wrapper the other nurses use. MiniMax.

Health Telemetry 1.3.1 (skill health-elastic 1.1.1): the collect call has no `timeout`. `window_delta` is defined again, so the visit can stamp a window. MiniMax.

Health Telemetry 1.3.0 (skill health-elastic 1.1.0, workspace-handoff 1.70.31): the first NetFlow stamp is a baseline of named paths, not every flow. A later stamp is a 4× surge, a loud new path, a deny surge, or an exporter change. Names come from `observer.name` and `lab.*.device` when the stream has them. A steady path or a steady deny is not a finding. MiniMax.

Health Telemetry 1.2.0 (skill health-elastic 1.0.0, workspace-handoff 1.70.30): the NetFlow plane reads Elasticsearch `logs-netflow.log-default` with ES|QL. Grafana Influx is not this visit. `observer.ip` is the exporter. A deny is `netflow.firewall_event` 3. MiniMax.

Caldera skill 2.1.0: collect writes `campaigns/` from Caldera only. Network, CML, and IOS-XE stay on their own agents. A run starts one operation from the kept ability ids. Ability commands stay on the server. `next_test` is the following campaign. No agent prompt yet. MiniMax.

Ops CMDB Sync skill 1.2.2: an address that already exists in NetBox is reused. The device primary is pointed at that object. A duplicate create is not a gap for the operator. MiniMax. Agent prompt stays 1.2.0.

Ops CMDB Sync skill 1.2.1: an address change looks up the interface by name before creating one. An existing `GigabitEthernet1` is reused. The IP on it is updated. MiniMax. Agent prompt stays 1.2.0.

Ops CMDB Sync 1.2.0 (skill 1.2.0): the ServiceNow record is an `alm_hardware` asset. Serial and asset tag are the device name. `snow_get_asset` / `snow_upsert_asset`. The address is written in `comments` with the lab tenant, because the asset tools have no IP field. A missing NetBox device is created. MiniMax.

Ops CMDB Sync skill 1.1.1: the ServiceNow query also requires `comments` equal to the lab tenant and includes `cmdb_ci_ip_firewall`. Application CIs share that comment. The network set is company Cisco AI Lab. MiniMax. Agent prompt stays 1.1.0.

Ops CMDB Sync 1.1.0 (skill 1.1.0, workspace-handoff 1.70.28): `scripts/sync_cmdb.py sync` runs under `mcp_orchestration`. Scope is `inventory/prod.json` `netbox.tenant` (else `source.name`) and one `devices[]` name. NetBox find sends that tenant and requires the `{tenant}-simulate` tag. ServiceNow is one exact-name query, limit 5, network CI classes only. `origin` `prod-twin` is not a separator. MiniMax.

Ops CMDB Sync 1.0.0 (skill 1.0.0, workspace-handoff 1.70.27): a NetBox or ServiceNow webhook is the same job. `Sync <device>.` The signal is a label. IOS-XE hostname must match that name. Primary IPv4 is copied onto the existing NetBox address only. ServiceNow is read with `snow_query_table`; a mismatch is a gap because there is no network-CI write tool. Serial, asset tag, status, model, and site are reported and not copied. `state/cmdb-sync.json` is this invoke only. A second webhook that already matches writes nothing. MiniMax.

Compliance Intelligence 2.2.1 (skill 1.22.0): `scan` writes the covered rows in `compliance/coverage.json`. `finalize` recounts `counts` from those rows, drops a key that has no row, and fills candidate `frameworks` from the banking crosswalk. `AC-17(2)` uses the `AC-17` row when the enhancement has none. The model does not write coverage.

Compliance Test skill 1.13.1: the federal brief writes failing control rows. The id is in backticks in the log (`AC-11`, `8.2.8`). Skill 1.13.0 stored the counts and dropped those rows.

Compliance 1.3.0 (skill 1.3.0), Intelligence 2.2.0 (skill 1.21.0), Author 1.4.0 (skill 1.8.0), Test 1.9.0 (skill 1.13.0), workspace-handoff 1.70.29: `banking-framework-crosswalk.v1.json` joins NIST SP 800-53 to PCI DSS v4.0 and FFIEC. The scan returns that map. A compliance visit stores the federal brief counts. PCI and FFIEC inherit NIST status and are not a second test. Explain asks read the workspace files. MiniMax, except Intelligence stays Frontier.

Compliance Intelligence 2.1.1 (skill 1.20.1): coverage.json is one row per NIST id, replaced in full. A partial proof is `partial` on that row. An empty search-replace is not a delete; write the file once and stop retrying. Frontier.

Compliance Intelligence 2.1.0 (skill 1.20.0, workspace-handoff 1.70.26, Compliance Author 1.3.2, authoring skill 1.7.3): `scripts/scan_catalog.py scan` runs under `mcp_orchestration`. It lists `catalog` and `tests/compliance` on `main`, reads the job catalog and the bridge, and returns unresolved NIST titles plus the estate. A NIST id is covered only when its check is on the bridge. The model ranks at most ten and sets `evidence` `static` (pytest on committed config) or `live` (ask the device). Frontier, because the operator selected it for this interpretation.

Presentation 1.2.6 (skill 1.2.6): file tools use `<customer>/deck.json`. `file_explorer/acme/deck.json` is `/app/file_explorer/acme/deck.json` and Access denied. "Acme Corp" is `acme-corp`. File not found on the customer path means there is no deck yet. MiniMax.

Presentation 1.2.5 (skill 1.2.5, presentation-build 1.2.1): every write of `deck.json` invokes Presentation Builder. The Disney template's Title Slide 2 Blue is slide 1 only. Neighboring slides may not share a layout. MiniMax.

Presentation 1.2.3 (skill 1.2.3): invoke Presentation Builder and end the turn. Do not poll. Its result is delivered when the parent is idle. MiniMax.

Presentation 1.2.2 (skill 1.2.2, presentation-build 1.2.0): the pptx is `<customer>/<customer>.pptx`. Body slides use the Presidio master layouts (Title Slide 2 Blue, Title and Content, 1_Two Content, Section, Chapter, Large Quote), not the generic second-master Title, Content layouts. MiniMax.

Presentation 1.2.1 (skill 1.2.1): Acme is `file_explorer/acme/deck.json`. The folder is the name they said. `acme/deck.json` and `acme-corp/deck.json` are the wrong path, and file-not-found on those is not "no deck". MiniMax.

Presentation 1.2.0 (skill 1.2.0, presentation-build 1.1.0): a customer is a folder at the workspace root. Amtrak is `file_explorer/amtrak/deck.json`. Acme is `file_explorer/acme/deck.json`. The builder writes `<customer>/deck.pptx` beside it. These agents do not use the network-ops catalog. MiniMax.

Presentation 1.1.0 (skill 1.1.0, presentation-build 1.0.0, workspace-handoff 1.70.24): the parent writes `reports/presentations/<slug>/deck.json` with the file tools and does not compile. Presentation Builder runs `deck.py compile` only when the parent sends `Compile the deck only.` `python-pptx` is already in the sandbox. MiniMax.

Network Map skill 1.3.3 (agent prompt stays 1.1.0): the Lifecycle card is a scorecard — overdue, approaching (inside 90 days), and the list-price total for approaching products. Advisories are a separate card, counted and colored Critical, High, and Medium.

Network Map skill 1.3.2 (agent prompt stays 1.1.0): the trend is the compliance state and the health problem state. Probe, exporter, and IOS-XE series are not lines. Clicking a point or a problem opens the interpretation and the evidence.

Network Map skill 1.3.1 (agent prompt stays 1.1.0): the gold line and the compliant header are checks passed / (passed + failed + errored). Canonical tests that are fully green stay on the point detail and are not the percent.

Network Map 1.1.0 (skill 1.3.0, workspace-handoff 1.70.21): the map reads `state/lifecycle.json`. A device drawer and the Lifecycle card show support date, replacement offers with list price and lead time, and the top PSIRT advisories. Overdue products get an L badge. The list range is min and max offer × quantity.

Relationship agent 1.4.0 (skill 1.4.0, workspace-handoff 1.70.20): `compile_graph.py` copies `state/lifecycle.json` into `lifecycle` (cost, timeline, per-device replacement, list price, CCW lead time, and the order window already on `plan.timeline`). It does not recompute order-by. Compliance failures come from `results.by_device`; older `results.ran[]` rows still copy. Health `relations[]` is unchanged.

Modernization Analysis skill 2.5.1 (agent prompt stays 2.5.0): an order stage lists every pid in that window. The previous 12-pid cap dropped priced rows such as C8500L-8S4X off `plan.timeline`.

workspace-handoff 1.70.20: `state/relationships.json` readers may rely on `lifecycle`.

GitOps Change 1.4.3 (skill 1.4.3) and Network Ops 3.2.5: `interface 1` is not a nickname table. The script returns the interface headers from that device file. The change agent picks the one numbered 1 and submits again. A blocked reply does not send Network Ops into the chart or the relationship map.

Network Ops 3.2.2 (skill 3.3.2, workspace-handoff 1.70.22): `scripts/recommend.py assess` writes `state/recommendations.json` under `execution_type: standard`. It reads the testing visit, active chart problems, and the sync watermark. The same fingerprint writes nothing. An exact operator edit still skips the board and goes to GitOps Change.

Network Ops 3.2.1 (skill 3.3.1): an operator who names the hostname and the exact text is implemented at once. GitOps Change gets that prescription. The chart, the peer, and the blast-radius walk are for asks that do not already contain the lines.

GitHub GitOps Change 1.4.1 (skill 1.4.1): a direct request is committed with `scripts/submit_change.py` on `ref=dev`. The agent does not read a peer or call the GitHub file tools itself.

Pipeline Monitor skill 4.5.3 (agent prompt stays 2.0.1): `apply.yml` prints the live report in the Live tests job as `# Network test report — FAILED` and `counts_ran:`. The watch reads the Static and Live jobs, not the first three. Run 38474971784 live is pass=65 fail=2.

Pipeline Monitor skill 4.5.2 (agent prompt stays 2.0.1): a finished `apply.yml` whose report is only static failures is `fail`, and the marker line does not invent a live score of zero. `unknown` is a missing report. A live pass with static failures is still `pass`.

Pipeline Monitor 2.0.1 (github-actions skill 4.5.1): `watch_run.py` and `github_common.py` both live in that skill. `workspace-handoff` is attached only for `visit_common`. The script checks the run once. `running` is the same command plus `--run-id`. Compliance Test skill stays 1.12.7.

Modernization Analysis 2.5.2 (skill 2.5.2): the reply must quote `cost_low`, `cost_high`, and `windows`. A missing product_id is a gap. It does not blank the budget. Operator `software_version` on `devices.json` is kept.

Modernization Analysis 2.5.1 (skill 2.5.1): the reply must quote `cost_low`, `cost_high`, and `windows`. A missing product_id is a gap. It does not blank the budget. Operator `software_version` on `devices.json` is kept.

Modernization Analysis 2.5.0 (skill 2.5.0): assess writes the budget and the order windows from support dates, lead times, and every CCW offer. The opinion cites those figures.

Modernization Analysis 2.4.0 (skill 2.4.0): `state/lifecycle.json` items may carry `lead_time` and `offers` from Lifecycle. The analysis schema accepts them and `assess_estate.py` copies them through.

Modernization Lifecycle 1.7.0 (skill 1.7.0): `cisco_psirt_software` is called with `mode` `OSType`, `osType` (`iosxe` or `asa`), and the stored software version. Every EoX replacement candidate is priced, with lead time, in `offers`.

Modernization Lifecycle skill 1.6.2: one hardware EoX call and one software release per PID, then PSIRT and NVD. Cisco calls wait 0.6s. CCW lead time is stored on the estate row. A missing PSIRT list is not treated as finished.

Modernization Lifecycle skill 1.6.1: `collect` takes `product_id` from `inventory/assets/devices.json` and researches those PIDs. An estate that still lists only CML node types is not treated as current.

workspace-handoff 1.70.19: Cisco research and the roadmap moved from `lifecycle/` to `inventory/assets/`. The operator product list is `inventory/assets/devices.json`. `state/lifecycle.json` stays the rollup.

workspace-handoff 1.70.18: `inventory/assets.json` is the operator product-id overlay. Analysis seeds it from `inventory/prod.json` and copies `product_id` through. Lifecycle calls MCP only for those product ids.

workspace-handoff 1.70.17: Modernization Lifecycle `scripts/visit_lifecycle.py collect` runs under `mcp_orchestration` (Cisco EoX, PSIRT, NVD, CCW). `annotate` sets only the family ask. Modernization Analysis `scripts/assess_estate.py` runs under `standard` and does not call MCP.

workspace-handoff 1.70.15: `unwrap_github` reads `github_list_files`, `github_get_file`, and `github_put_file`. The tool dict is `{ok, entries}` or `{ok, content, sha}` or `{ok, sha, commit_sha}`. `result` on `call_mcp` is a list; `result[0]` is that dict.

Relationship agent 1.3.0 (skill 1.3.0): `scripts/compile_graph.py compile` copies nurse columns, CMDB declarations, and asserted relations into `state/relationships.json`. No MCP. Unchanged watermarks write nothing. Superseded by 1.4.0.

Health Analyzer 5.3.2 (skill 5.3.2): Frontier. A named problem is checked against that plane's board `current[]`, `visits[]`, and `series[]`, and the stamps those ids already name. If the latest collect no longer shows the fault, say the SOAP row is behind the nurse, do not ls `health/`.

Health Analyzer 5.3.1 (skill 5.3.1): Frontier. A "where did this fault come from" answer names the telemetry plane from `problems[].symptom_refs` (IOS-XE, Splunk, Grafana NetFlow, Grafana application, ServiceNow), not only the device. Model is Frontier per the operator (SOAP synthesis).

Health Analyzer 5.3.0 (skill 5.3.0): MiniMax. Every turn reads the chart and five boards first. Current boards → answer, no script. Stale board → invoke the nurse, not `assess_health.py`. The assess script runs only on rewrite the health chart / fold SOAP / run assess_health. Analyze and scheduled analyze are not a rewrite when the boards are current.

Health Analyzer 5.2.0 (skill 5.2.0): MiniMax. A question is chat: `read_file` catalog rows, no `execute_command`, no write. Analyze / chart / trend / refresh still runs `assess_health.py` then `annotate`. Built-in paths stay workspace-relative.

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

Health Application 1.4.0 (skill 1.4.0, workspace-handoff 1.70.33): the visit reads Elasticsearch Docker container status, CPU, and memory, plus host uptime, memory, and root disk. Probe and scrape-target rows are not refreshed; those series are not in Elasticsearch. MiniMax.

Health Application 1.3.0 (skill 1.3.0): a probe row is application, destination environment, target, and vantage. The visit reports window failure and latency, a body-check result when `probe_failed_due_to_regex` exists, and container limit, throttle, and OOM when those series exist. Missing series and missing vantage points (cloud, hq, branch unless the board sets `expected_vantages`) stay missing. `last_collected_at` and `last_visit_id` both appear in the reply.

Health Application 1.2.0 (skill 1.2.0): probe `duration_ms` is material when it crosses `latency_threshold_ms` (default 500) or moves 3× against the board row. A probe still over that line degrades the plane. The value stays on the board when the move is smaller.

Health Application 1.1.1 (skill 1.1.1): prior visit rows carried a `scope` the board schema does not allow. The script keeps the visit fields and drops the rest, so an older board still saves.

Health Application 1.1.0 (skill 1.1.0): the visit runs `visit_application.py`. The script calls Prometheus targets, the twelve expressions in `references/prometheus.md`, and the annotation list, then diffs the board. Stamp only when a row moved, on the first visit, or when coverage is not complete. Annotate only when `needs_note` is not empty. Health Monitor is unchanged.

Health Telemetry 1.1.0 (skill 1.1.0): device identity requires fresh exact-interface, access-host, or exporter-name evidence. A stored owner that disagrees is conflicted, and `10.30.30.2` is written to `identity_review` when that list is empty so a containing subnet cannot assign it. A conversation missing from the top-N query is `not_in_top_n` with last bytes kept, not absent. `bytes_per_s` is the observed rate at that exporter and window. Estate totals use one observation point. Registry policy slots stay null unless the operator set them. The first visit under these rules is a baseline migration and is not `worse` only because identifiers changed. Silence is not a forwarding failure.

Health Telemetry 1.0.7 (skill 1.0.7): the visit also reads the bucket measurement whose fields include `fw_event` and records deny rows. A new, changed, or cleared deny is material and a deny still in the window degrades the plane. Health Telemetry 1.0.6 (skill 1.0.6): same visit as the other nurses. Rewrite the nested board every visit. Stamp only on the first visit, a material row, or coverage that is not complete. Annotate only when `needs_note` is not empty. A flat board already on disk is read, then written in the schema shape. Health Telemetry 1.0.5 (skill 1.0.5): every completed visit updates `health/metadata-netflow.json` in the flat shape already on disk and writes `health/netflow/<stamp>.json` with `vs_prior`. The headline is the opinion, set by annotate. Health Telemetry 1.0.4 (skill 1.0.4): a board whose provenance is `bucket` / `measurement` / `window` is saved as `provenance.netflow`. Health Telemetry 1.0.3 (skill 1.0.3): collect reads a flat `health/metadata-netflow.json` (bucket and measurement at the top level, as in the workspace capture) as well as a nested `netflow` object. Health Telemetry 1.0.2 (skill 1.0.2): a missing `netflow.bucket` is empty, not an error, so collect continues into Grafana discovery. Health Telemetry 1.0.1 (skill 1.0.1): `visit_netflow.py` takes bucket, measurement, and datasource from the board or from optional collect flags. When the board lookup is missing or F1 is empty, and `provenance.netflow` is not `user`, the script lists Influx datasources, lists buckets with `buckets()`, and keeps the measurement whose tags match the flow queries. Health Monitor 2.2.0 is unchanged.
