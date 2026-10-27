---
name: secops-event-response
version: "1.0.1"
description: "v1.0.1 — SecOps event response: read the health boards, run the NetFlow and Splunk nurse queries, and order a block when the traffic is an attack."
---

# SecOps event response

One visit. Run `scripts/respond.py collect`, then `annotate` with
the kind and the blocks. The script reads every health board, then
calls `elasticsearch_query` with F1–F4 from `health-elastic` and
`splunk_search` with S1–S3 from `health-logging`. It writes
`state/secops-event.json`. You decide whether the traffic is a
port scan. F4 and S3 are that signal.

A port scan is one source and many service ports, or one source and
many destinations. Order a block only for a placement the script
listed. Then invoke Ops Firewall once per block and wait.

Do not call Grafana. Do not write `state/health.json`, `state/firewall.json`,
or a health board. Do not deploy an FTD.
