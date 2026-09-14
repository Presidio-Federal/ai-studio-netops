---
name: network-ops
version: "1.0.6"
description: "v1.0.6 — Operate the network: list inventory/configs, edit the listed file, commit git dev, wait for GitOps, merge to main."
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
| Fix / remediate / implement | List configs, get listed path, put `ref=dev`, invoke Pipeline Monitor, merge if live pass. |
| Check bug (`dict` has no `.lower`, checker error) | Compliance Author. |
| Hardware / replace / warehouse / CHG | Network Design. Name them and stop. |
| Run a suite with no config change | Compliance Test. |

Exact tools: [references/tools.md](references/tools.md).

`github_put_file` **must** use `ref=dev` (the tool defaults to
`main`). Merge with `merge_method=merge`. Do not delete `dev`.
Do not `github_create_branch`. After the commit, invoke Pipeline
Monitor once and wait — do not poll Actions yourself.

## First action

**List, then get the listed path.** Do not invent a filename or
suffix. Do not confirm.

1. `github_list_files(path="inventory/configs", ref="dev")`.
2. Pick the `entries[]` whose `name` is the hostname plus whatever
   suffix the listing shows. Use that entry’s `path`.
3. `github_get_file` that `path` `ref=dev`. Keep `content` and
   `sha`.

Named line change: do not open design. Do not open a peer.

No hostname yet: `read_file` `inventory/prod.json` (Access denied
and Allowed paths include `file_explorer` → retry once
`file_explorer/inventory/prod.json`). Then list. Never `/app/`,
never `/workspace/` on built-in tools, never `/file_explorer`.
Copy hostnames character for character. Never invent or prefix
`AI-`.

How to edit: [references/change.md](references/change.md).

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
