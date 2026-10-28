---
name: secops-event-response
version: "1.0.5"
description: "v1.0.5 — SecOps event response: the scan task permits TCP 80, 443, 8080, and 8443, then denies ip."
---

# SecOps event response

One visit. Run `scripts/respond.py collect`, then `annotate` with
the kind and the blocks. The script reads every health board, then
calls `elasticsearch_query` with F1–F4 from `health-elastic` and
`splunk_search` with S1–S3 from `health-logging`. It writes
`state/secops-event.json`. You decide whether the traffic is a
port scan. F4 and S3 are that signal.

A port scan is one source and many service ports, or one source and
many destinations. One scan source is one IOS-XE edge and the closest
firewall on that path. Destination is `any`. Invoke Ops Firewall once
per device in `tasks` and wait. Do not add the word deploy.

Do not call Grafana. Do not write `state/health.json`, `state/firewall.json`,
or a health board.
