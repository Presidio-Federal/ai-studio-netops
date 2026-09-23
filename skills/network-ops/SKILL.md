---
name: network-ops
version: "2.3.0"
description: "v2.3.0 — Read workspace and GitHub configs, decide exact changes, and delegate mechanical commits."
---

# Network Ops skill

GitHub is the config SoT. Network Ops reads relevant workspace evidence and
target/peer configs directly, then decides the exact change. GitHub GitOps
Change performs only exact full-file edits and `dev` puts. Pipeline Monitor
owns Actions polling. Network Ops owns `state/network-ops.json`.

## Route

| Intent | How |
|--------|-----|
| Change / fix / implement | Read workspace evidence + target/peer Git configs → decide → GitOps Change commit. |
| Check bug | Compliance Author. |
| Hardware / replace / warehouse / CHG | Network Design. |
| Run a suite with no config change | Compliance Test. |

Exact tools: [references/tools.md](references/tools.md).

Network Ops may call `github_list_files` and `github_get_file` for config
discovery. It never calls `github_put_file` or Actions tools. Do not query
subagent status. Treat each attached agent's final response as the next input.
Invoke attached agents synchronously and wait in the same run; never launch
background/autonomous work. Waiting on one invocation is not polling. Use the
exact registered identifier exposed for the attached agent.

## Prescription

Send only:

- exact hostnames, or one deterministic hostname selection rule
- `ensure_present`, `ensure_absent`, or `replace`
- exact config lines
- exact scope and placement
- preserve-unrelated-content constraints

Never send a full config to the worker. Read the relevant workspace state and
detailed visit, list `inventory/configs` on `dev`, then get only the target and
relevant passing/canonical peer paths returned by that listing. Verify the
finding and derive exact lines, scope, and placement. Ambiguous evidence →
`blocked`; do not ask the operator for lines already available in Git.

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
