---
name: network-ops
version: "3.1.0"
description: "v3.1.0 — network-ops-state/v3: recommend one charted problem, review every board and config-class symptom into a ranked review[] with exact git-verified lines, or implement with explicit authorization; problem_ref, verified_in_git, asserted relations[]."
---

# Network Ops skill

GitHub is the config SoT. Network Ops reads relevant workspace evidence and
target/peer configs directly, then decides the exact change. GitHub GitOps
Change performs only exact full-file edits and `dev` puts. Pipeline Monitor
owns Actions polling. Network Ops owns `state/network-ops.json`.

## Evidence sources

Three sources name a target and a feature. **Any one is enough** to
open git; none of them is a precondition for the others.

| Source | Where | `finding.source` | `problem_ref` |
|--------|-------|------------------|---------------|
| Charted problem | `state/health.json` `problems[]` — the Analyzer's order reads `Network Ops: <hypothesis>`; or the operator named a key or symptom exactly one `active` / `watching` problem carries | `health:<P-id>` | its `id` |
| Compliance result | `state/testing.json` `latest` → `operational/testing/<stamp>.json` result rows: failing targets, passing peers, the control | `state/testing.json` | null, unless a problem also carries the device |
| Operator | the ask names devices (or a role) and a feature | `operator` | null |

Read `symptom_refs` / `evidence_refs` (chart) or the result rows
(testing) before listing configs — they say which device, interface,
or path to open. Then **always** list `inventory/configs` on `dev` and
read the target and a passing or canonical peer. The config on `dev`
is the current intent by definition; the age of the evidence that
pointed you at it is a note in `Gaps:`, never a reason to skip git or
to return `blocked`.

`blocked` means one thing: the two bodies you read cannot yield exact
lines, scope, and placement (no peer carries the feature and the
operator gave no values). "No charted problem", "compliance run is
old", and "several things are wrong" are not `blocked`.

What you conclude from config plus evidence is recorded as asserted
`relations[]` with the git path as evidence
([references/relations.md](references/relations.md)); the Analyzer's
`outcome` says whether a charted treatment worked.

## Route

| Intent | How |
|--------|-----|
| “How would”, “what should”, recommend, explain — **one** problem, device, or feature named | `recommend`: read evidence and the two configs; return an exact recommendation; no delegation or Git mutation. |
| Open-ended — “look at everything”, “what should I improve”, “review”, no problem named | `review`: read the chart, the four boards, testing, topology, prod; list configs once, read up to six; return a ranked `review[]` of exact git-verified proposals ([references/review.md](references/review.md)). Read-only. |
| Change / fix / implement / apply — explicit imperative | `implement`: same reads as `recommend` → decide → GitOps Change commit → Pipeline Monitor → PR. |
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

Never send a full config to the worker. Read the evidence source (chart
problem refs, at most four files; or `state/testing.json` and its latest
run; or the operator's words), list `inventory/configs` on `dev`, then get
only the target and relevant passing/canonical peer paths returned by that
listing. Verify the finding and derive exact lines, scope, and placement.
The peer is the source of canonical values (NTP servers, AAA groups,
source interfaces): copy them from the peer body, never from memory.
Only when no peer carries the feature and the operator gave no values →
`blocked`, naming the one value you need. Do not ask the operator for
lines already available in Git.

A multi-feature imperative (“implement the NTP configs”, “fix AAA and
NTP”) is one prescription per feature, targets grouped, sent to GitOps
Change one at a time in the same run; it is not `blocked` for being
several changes.

In recommendation mode, write `state/network-ops.json` with
`mode=recommend`, `status=recommended`, the exact proposed change, evidence
summary, `problem_ref`, `finding.verified_in_git`, the `depends_on` /
`caused` rows the evidence supports, and canonical keys. Do not invoke
either subagent or mutate Git. Review mode writes the same record with
`review[]` added; row 1 is the record ([references/review.md](references/review.md)).

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
- Review mode (open-ended ask): `references/review.md`
- Edit + ship: `references/change.md`
- Tools: `references/tools.md`
