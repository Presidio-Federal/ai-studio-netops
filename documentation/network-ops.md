# Network Ops

The frontier-model operator. Reads the chart and names a bounded,
exact running-config change. When exact syntax is missing, it asks the local
GitHub GitOps Change worker for bounded target/peer evidence. That worker also
owns full-file GitHub writes. Pipeline Monitor owns pipeline polling.

Evidence is the work queue: `state/testing.json`,
`state/compliance.json`, `state/health.json`. Design
(`state/design.json`) is awareness — hardware and replacement —
not a ticket list. A missing NTP stanza on an edge when WAN
already has NTP is Ops even if Design never wrote a `cfg-*` row.

Git `dev` is the proposal. git `main` is Prod SoT and is locked
except by merge. GitHub GitOps Change commits the prescription to `dev` and
returns the exact SHA. Network Ops invokes Pipeline Monitor once for that SHA;
it never polls subagent status. Live pass → Ops opens `dev` → `main` and
merges (merge commit; do not delete `dev`).

Config bodies remain in the local worker context and git. Only bounded,
feature-specific evidence enters the frontier model's context. GitOps Change
and Pipeline Monitor each write one concise relationship-ready
`operational/runs/<stamp>.json`; Network Ops then replaces
`state/network-ops.json` with the current change, commit, CI, PR, and
entity-key summary.

Dated hardware / software / warehouse work is
[Network Design](change-and-test-agents.md). Check bugs are
[Compliance Author](compliance-agents.md). Ad-hoc suites are
[Compliance Test](compliance-agents.md).
