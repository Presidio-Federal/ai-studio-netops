---
name: network-ops
version: "1.0.2"
description: "v1.0.2 — Operate the network: read failures, copy working SoT config onto peers that lack it, commit git dev, wait for GitOps, merge to main."
---

# Network Ops skill

You operate the running network. Evidence is the work queue
(testing, compliance, health). Git holds running-configs. You
write a specific config fix onto git `dev` and ship it through
GitOps. Design is awareness (hardware, replacement), not a ticket
list.

An operate / fix / remediate / implement invoke is authorization
to commit `dev`. A “what’s wrong / recommend” ask: write the
recommendation and stop.

## Route

| Intent | How |
|--------|-----|
| What’s wrong / recommend | Read chart + git SoT. Write `state/network-ops.json`. |
| Fix / remediate / implement | Recommend, then commit `dev`, invoke Pipeline Monitor, merge if live pass. |
| Check bug (`dict` has no `.lower`, checker error) | Compliance Author. |
| Hardware / replace / warehouse / CHG | Network Design. Name them and stop. |
| Run a suite with no config change | Compliance Test. |

Exact tools: [references/tools.md](references/tools.md).

`github_put_file` **must** use `ref=dev` (the tool defaults to
`main`). Merge with `merge_method=merge`. Do not delete `dev`.
Do not `github_create_branch`. After the commit, invoke Pipeline
Monitor once and wait — do not poll Actions yourself.

## First action

**Read workspace, then git.** Do not confirm.

1. `state/testing.json` if present, then `state/compliance.json` if
   present, then `state/health.json`, `inventory/prod.json`,
   `inventory/dev.json`. `state/design.json` is awareness only —
   hardware/software dates; not the work queue.
2. Pick devices from evidence (gaps, failed checks). Copy hostnames
   from inventory character for character. Never invent or prefix
   `AI-`.
3. Git SoT: `github_get_file` on `inventory/configs/<hostname>`
   `ref=dev`. 404 → same path `ref=main`. Still 404 → try
   `<hostname>.cfg`. Stop after those. A failed get is not “no NTP.”
4. Compare a failing device to a peer that passed (or a same-role
   neighbor that has the feature). How: [references/change.md](references/change.md).

## Implement

How to edit and ship: [references/change.md](references/change.md).

After the last `github_put_file` on `dev`, take `commit_sha` from
that tool result. Invoke Pipeline Monitor with those three fields
filled — never omit the sha:

```text
Watch apply.yml on ref=dev for commit <commit_sha>. Return the run URL and the marker result. Do not merge.
```

Wait. Judge **live** from the monitor Result. Static fail is not
a merge block. Missing marker is `unknown` — do not merge.

Live pass → `github_create_pull_request` (`source_branch=dev`,
`target_branch=main`) then `github_merge_pull_request`
(`merge_method=merge`). If those tools error, stop with the PR
URL or “ready to merge.”

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
[references/workspace-contract.md](references/workspace-contract.md).

Write ONLY `state/network-ops.json`. Replace in full.

Use exactly:

- `references/workspace-contract.md`
- `references/change.md`
- `references/tools.md`
- `schemas/network-ops-state.schema.json`
- `examples/network-ops-state.example.json`

`execute_command` only after `write_file`:

```text
python3 /skills/user/network-ops/scripts/validate_network_ops.py /workspace/state/network-ops.json
```

If `/skills` is empty, skip validate. Never `find /`.

## State machine

READ_CHART → READ_SOT → JUDGE (config gap vs test bug) → WRITE_STATE
→ (recommend: STOP) → PUT_DEV → INVOKE_MONITOR → MERGE_OR_STOP →
WRITE_STATE → VALIDATE → STOP

## Reference routing

- Peer template + NTP example: `references/change.md`
- Tools: `references/tools.md`
- Produce: `references/workspace-contract.md`
- Watch/poll: Pipeline Monitor / `github-actions-mcp`
