---
name: network-ops
version: "2.1.1"
description: "v2.1.1 — Delegate GitOps work and publish canonical top-level workspace entity keys."
---

# Network Ops skill

GitHub is the config SoT. Network Ops decides the exact change but never loads
large config bodies. GitHub GitOps Change owns config I/O, `dev` puts, and
Actions polling. Network Ops owns `state/network-ops.json`.

## Route

| Intent | How |
|--------|-----|
| Change / fix / implement | Send one bounded prescription to GitHub GitOps Change; merge on its final live pass. |
| Check bug | Compliance Author. |
| Hardware / replace / warehouse / CHG | Network Design. |
| Run a suite with no config change | Compliance Test. |

Exact tools: [references/tools.md](references/tools.md).

Do not call config file or Actions tools. Do not query subagent status. Invoke
GitHub GitOps Change once and treat its final response as the next input.

## Prescription

Send only:

- exact hostnames, or one deterministic hostname selection rule
- `ensure_present`, `ensure_absent`, or `replace`
- exact config lines
- exact scope and placement
- preserve-unrelated-content constraints

Never send a full config. Missing exact syntax, scope, placement, or
deterministic targets → `blocked`.

How to delegate and ship: [references/change.md](references/change.md).

## After worker result

Result `pass` → `github_create_pull_request`
(`source_branch=dev`, `target_branch=main`) then
`github_merge_pull_request` (`merge_method=merge`). Do not
delete `dev`. Result `fail`, `unknown`, `no_change`, `blocked`,
or `failed` → do not create or merge a PR.

## Current operational state

After every terminal outcome, replace `state/network-ops.json` following
`schemas/network-ops-state.schema.json`. Copy only the worker's compact
evidence:

- devices and changed repository paths
- one-line change summary and `operational/runs/<stamp>.json` reference
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
