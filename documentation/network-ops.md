# Network Ops

The frontier-model operator. Reads the chart and names a bounded,
exact running-config change. It reads relevant target and passing-peer configs
from GitHub directly to verify the finding and derive exact syntax. The local
GitHub GitOps Change worker owns full-file GitHub writes. Pipeline Monitor owns
pipeline polling.

Questions such as “how would you configure” are read-only recommendations.
Only an explicit implementation command authorizes the GitOps worker,
pipeline watch, PR, and merge.

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

Network Ops may load the few relevant config bodies into its reasoning context
but never copies them into workspace state or its reply. GitOps Change and
Pipeline Monitor each write one concise relationship-ready
`operational/runs/<stamp>.json`; Network Ops then replaces
`state/network-ops.json` with the current change, commit, CI, PR, and
entity-key summary.

Dated hardware / software / warehouse work is
[Network Design](change-and-test-agents.md). Check bugs are
[Compliance Author](compliance-agents.md). Ad-hoc suites are
[Compliance Test](compliance-agents.md).
