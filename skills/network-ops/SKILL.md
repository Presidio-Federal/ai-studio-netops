---
name: network-ops
version: "1.0.8"
description: "v1.0.8 — List git inventory/configs, edit the listed file, commit dev, wait for GitOps, merge to main."
---

# Network Ops skill

Git holds running-configs. List `inventory/configs`, edit the
listed file, commit `dev`. Merge `main` after live GitOps.

An operate / fix / remediate / implement invoke is authorization
to commit `dev`. A “what’s wrong / recommend” ask: list and get,
write state, stop.

## Route

| Intent | How |
|--------|-----|
| Fix / remediate / implement | List, get listed path, put `ref=dev`, invoke Pipeline Monitor, merge if live pass. |
| What’s wrong / recommend | List and get. Write `state/network-ops.json`. Do not put. |
| Check bug | Compliance Author. |
| Hardware / replace / warehouse / CHG | Network Design. |
| Run a suite with no config change | Compliance Test. |

Exact tools: [references/tools.md](references/tools.md).

`github_put_file` **must** use `ref=dev` (the tool defaults to
`main`). Merge with `merge_method=merge`. Do not delete `dev`.
Do not `github_create_branch`. After the commit, invoke Pipeline
Monitor once and wait — do not poll Actions yourself.

## First action

1. `github_list_files(path="inventory/configs", ref="dev")`.
   Tool missing → stop `blocked`. Do not invent a path.
2. Match the hostname from the ask to `entries[]` `name`. Use
   that entry’s `path`.
3. `github_get_file` that `path` `ref=dev`. Keep `content` and
   `sha`.
4. Change only the named text. `github_put_file` the same path
   `ref=dev` with that `sha`.

How to ship: [references/change.md](references/change.md).

## Implement

After the last `github_put_file` on `dev`, take `commit_sha` from
that tool result. Invoke Pipeline Monitor:

```text
Watch apply.yml on ref=dev for commit <commit_sha>. Return the run URL and the marker result. Do not merge.
```

Wait. Live Result `pass` → `github_create_pull_request`
(`source_branch=dev`, `target_branch=main`) then
`github_merge_pull_request` (`merge_method=merge`). Static fail
is not a merge block. Missing marker is `unknown` — do not merge.

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

LIST → GET → PUT_DEV → INVOKE_MONITOR → MERGE_OR_STOP →
WRITE_STATE → VALIDATE → STOP

## Reference routing

- Edit + ship: `references/change.md`
- Tools: `references/tools.md`
- Produce: `references/workspace-contract.md`
- Watch/poll: Pipeline Monitor / `github-actions-mcp`
