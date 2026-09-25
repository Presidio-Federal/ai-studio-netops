---
name: network-ops
version: "3.0.0"
description: "v3.0.0 — network-ops-state/v3: start from state/health.json problems[] (problem_ref), finding.verified_in_git, change.interfaces, asserted relations[] (depends_on / caused / resolved_by with the git path as evidence). Read-only recommendations stay separate from explicitly authorized implementation."
---

# Network Ops skill

GitHub is the config SoT. Network Ops reads relevant workspace evidence and
target/peer configs directly, then decides the exact change. GitHub GitOps
Change performs only exact full-file edits and `dev` puts. Pipeline Monitor
owns Actions polling. Network Ops owns `state/network-ops.json`.

The chart comes first. `state/health.json` `problems[]` is the Analyzer's
problem list; a Network Ops order reads `Network Ops: <hypothesis>` and
carries a `problem_ref`. Match the ask to one problem, take its `id` as
`problem_ref`, and read its `symptom_refs` / `evidence_refs` before you list
configs — they name the device, interface, or path to open in git
([references/relations.md](references/relations.md)). What you conclude
from config plus chart is recorded as asserted `relations[]` with the git
path as evidence; the Analyzer's `outcome` on that problem says whether
the treatment worked.

## Route

| Intent | How |
|--------|-----|
| “How would”, “what should”, recommend, explain | Read evidence and return an exact recommendation; no delegation or Git mutation. |
| Change / fix / implement | Read workspace evidence + target/peer Git configs → decide → GitOps Change commit. |
| Check bug | Compliance Author. |
| Hardware / replace / warehouse / CHG | Network Design. |
| Run a suite with no config change | Compliance Test. |

Exact tools: [references/tools.md](references/tools.md).

Questions and hypotheticals are `recommend`, never implementation
authorization. Ambiguous intent is also `recommend`. Only an explicit
imperative such as `apply`, `implement`, `make this change`, `push`, `commit`,
`fix it`, or `proceed with that recommendation` authorizes delegation, Git
mutation, pipeline monitoring, and PR merge.

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

Never send a full config to the worker. Read `state/health.json` (the
problem), then the problem's `symptom_refs` / `evidence_refs` (at most four
files), list `inventory/configs` on `dev`, then get only the target and
relevant passing/canonical peer paths returned by that listing. Verify the
finding and derive exact lines, scope, and placement. Ambiguous evidence →
`blocked`; do not ask the operator for lines already available in Git.

In recommendation mode, write `state/network-ops.json` with
`mode=recommend`, `status=recommended`, the exact proposed change, evidence
summary, `problem_ref`, `finding.verified_in_git`, the `depends_on` /
`caused` rows the evidence supports, and canonical keys. Do not invoke
either subagent or mutate Git.

How to delegate and ship: [references/change.md](references/change.md).

## After worker result

Apply Result `submitted` → invoke Pipeline Monitor once with `apply.yml`,
`dev`, and the exact returned commit SHA. Monitor Result `pass` →
`github_create_pull_request`
(`source_branch=dev`, `target_branch=main`) then
`github_merge_pull_request` (`merge_method=merge`). Do not
delete `dev`. Monitor `fail|unknown`, or apply `no_change|blocked|failed` →
do not create or merge a PR.

Merged → add the `resolved_by` row (`references/relations.md`).

## Current operational state

After every terminal outcome, replace `state/network-ops.json` following
`schemas/network-ops-state.schema.json` (`network-ops-state/v3`). In
recommendation mode record the bounded proposal/evidence; in implementation
mode copy only compact worker evidence:

- `problem_ref` and `finding` (`source`, `headline`, `kind`,
  `verified_in_git`)
- devices, `interfaces` (`<device>/<interface>` for every interface stanza
  the prescription scoped), and changed repository paths
- one-line change summary plus GitOps and Pipeline Monitor
  `operational/runs/<stamp>.json` references
- final `dev` commit, CI run/result, and one marker line
- PR number/URL/merged result
- `relations[]` — the rows `references/relations.md` allows, nothing else
- top-level `keys` equal to the union of `change.devices` (`device:`),
  `change.interfaces` (`interface:`), and every relation end; never infer
  from prose

Allowed prefixes are `device|interface|site|service|test|control|incident|change`.
Location is `site:`. When a device is known, use
`interface:<device>/<interface>`. Keep any nested `keys`.

Never copy config bodies, patches, or full pipeline logs. Use
`examples/network-ops-state.example.json` for shape and `workspace-handoff`
for ownership. Validate with `scripts/validate_network_ops.py` when script
execution is available.

## Reference routing

- Problem list, relations, keys: `references/relations.md`
- Edit + ship: `references/change.md`
- Tools: `references/tools.md`
