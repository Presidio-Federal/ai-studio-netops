---
name: network-ops
version: "2.0.0"
description: "v2.0.0 — Frontier orchestrator delegates config I/O and pipeline polling to one local GitOps worker, then merges on pass."
---

# Network Ops skill

GitHub is the config SoT. Network Ops decides the exact change but never loads
large config bodies. GitHub GitOps Change owns config I/O, `dev` puts, and
Actions polling.

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

## Reference routing

- Edit + ship: `references/change.md`
- Tools: `references/tools.md`
