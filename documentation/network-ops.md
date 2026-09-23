# Network Ops

The frontier-model operator. Reads the chart and names a bounded,
exact running-config change. It delegates large config reads,
full-file GitHub writes, and pipeline polling to the local
GitHub GitOps Change worker.

Evidence is the work queue: `state/testing.json`,
`state/compliance.json`, `state/health.json`. Design
(`state/design.json`) is awareness — hardware and replacement —
not a ticket list. A missing NTP stanza on an edge when WAN
already has NTP is Ops even if Design never wrote a `cfg-*` row.

Git `dev` is the proposal. git `main` is Prod SoT and is locked
except by merge. GitHub GitOps Change commits the prescription
to `dev` and watches the exact `apply.yml` run. Its final compact
response returns to Network Ops without parent polling. Live pass
→ Ops opens `dev` → `main` and merges (merge commit; do not
delete `dev`).

Config bodies remain in the local worker context and git; they do
not enter the frontier model's context. The worker writes one
concise relationship-ready `operational/runs/<stamp>.json`; Network
Ops then replaces `state/network-ops.json` with the current change,
commit, CI, PR, and entity-key summary.

Dated hardware / software / warehouse work is
[Network Design](change-and-test-agents.md). Check bugs are
[Compliance Author](compliance-agents.md). Ad-hoc suites are
[Compliance Test](compliance-agents.md).
