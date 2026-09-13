# Network Ops

The operator. Reads the chart, names a specific running-config
fix from the committed SoT, and ships it through GitOps. Does
not collect telemetry and does not replace hardware.

Evidence is the work queue: `state/testing.json`,
`state/compliance.json`, `state/health.json`. Design
(`state/design.json`) is awareness — hardware and replacement —
not a ticket list. A missing NTP stanza on an edge when WAN
already has NTP is Ops even if Design never wrote a `cfg-*` row.

Git `dev` is the proposal. git `main` is Prod SoT and is locked
except by merge. Pipeline Monitor watches `apply.yml` on that
ref. Live pass → Ops opens `dev` → `main` and merges (merge
commit; do not delete `dev`).

Writes `state/network-ops.json` only. Config text stays in git.

Dated hardware / software / warehouse work is
[Network Design](change-and-test-agents.md). Check bugs are
[Compliance Author](compliance-agents.md). Ad-hoc suites are
[Compliance Test](compliance-agents.md).
