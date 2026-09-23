---
name: network-ops
version: "2.2.0"
description: "v2.2.0 — Decide from bounded config evidence, delegate commits, and gate merges on Pipeline Monitor."
---

# Network Ops skill

GitHub is the config SoT. Network Ops decides the exact change but never loads
large config bodies. GitHub GitOps Change returns bounded inspection evidence
or performs exact `dev` puts. Pipeline Monitor owns Actions polling. Network
Ops owns `state/network-ops.json`.

## Route

| Intent | How |
|--------|-----|
| Change with missing syntax/evidence | GitOps Change `inspect` → decide → GitOps Change `apply`. |
| Change with exact evidence | GitOps Change `apply` directly. |
| Check bug | Compliance Author. |
| Hardware / replace / warehouse / CHG | Network Design. |
| Run a suite with no config change | Compliance Test. |

Exact tools: [references/tools.md](references/tools.md).

Do not call config file or Actions tools. Do not query subagent status. Treat
each attached agent's final response as the next input.

## Prescription

Send only:

- exact hostnames, or one deterministic hostname selection rule
- `ensure_present`, `ensure_absent`, or `replace`
- exact config lines
- exact scope and placement
- preserve-unrelated-content constraints

Never send a full config. If those details are missing, first invoke GitOps
Change with `Mode: inspect`, exact targets/question, and an exact or
deterministic peer rule. It returns only relevant lines, scope, placement, and
consensus. Network Ops decides; the worker does not choose policy. Inspection
that remains ambiguous → `blocked`.

How to delegate and ship: [references/change.md](references/change.md).

## After worker result

Apply Result `submitted` → invoke Pipeline Monitor once with `apply.yml`,
`dev`, and the exact returned commit SHA. Monitor Result `pass` →
`github_create_pull_request`
(`source_branch=dev`, `target_branch=main`) then
`github_merge_pull_request` (`merge_method=merge`). Do not
delete `dev`. Monitor `fail|unknown`, or apply `no_change|blocked|failed` →
do not create or merge a PR.

## Current operational state

After every terminal outcome, replace `state/network-ops.json` following
`schemas/network-ops-state.schema.json`. Copy only the worker's compact
evidence:

- devices and changed repository paths
- one-line change summary plus GitOps and Pipeline Monitor
  `operational/runs/<stamp>.json` references
- final `dev` commit, CI run/result, and one marker line
- PR number/URL/merged result
- top-level `keys` equal to the deduplicated union of exact keys supported by
  structured fields, or `[]`; never infer from prose

Allowed prefixes are `device|interface|site|service|test|control|incident|change`.
Location is `site:`. When a device is known, use
`interface:<device>/<interface>`. Keep any nested `keys`.

Never copy config bodies, patches, or full pipeline logs. Use
`examples/network-ops-state.example.json` for shape and `workspace-handoff`
for ownership.

## Reference routing

- Edit + ship: `references/change.md`
- Tools: `references/tools.md`
