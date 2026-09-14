---
name: network-ops
version: "1.1.0"
description: "v1.1.0 — GitHub only: list configs, edit the listed file, commit dev, invoke Pipeline Monitor. Do not write the Studio workspace."
---

# Network Ops skill

GitHub is the config SoT. You do not `write_file`. You do not
`read_file`. You do not `execute_command`.

## Route

| Intent | How |
|--------|-----|
| Change / fix / implement | List, get, put `ref=dev`, invoke Pipeline Monitor, merge if live pass. |
| Check bug | Compliance Author. |
| Hardware / replace / warehouse / CHG | Network Design. |
| Run a suite with no config change | Compliance Test. |

Exact tools: [references/tools.md](references/tools.md).

`github_put_file` **must** use `ref=dev` (the tool defaults to
`main`). Do not `github_create_branch`. After put, invoke
Pipeline Monitor once and wait — do not poll Actions yourself.

## First action

1. `github_list_files(path="inventory/configs", ref="dev")`.
2. Match the hostname from the ask to `entries[]` `name`. Use
   that entry’s `path`.
3. `github_get_file` that `path` `ref=dev`. Keep `content` and
   `sha`.
4. Change only the named text. `github_put_file` the same path
   `ref=dev` with that `sha`.
5. Invoke Pipeline Monitor with `commit_sha` from put.

How to ship: [references/change.md](references/change.md).

## After put

```text
Watch apply.yml on ref=dev for commit <commit_sha>. Return the run URL and the marker result. Do not merge.
```

Live Result `pass` → `github_create_pull_request`
(`source_branch=dev`, `target_branch=main`) then
`github_merge_pull_request` (`merge_method=merge`). Do not
delete `dev`. Static fail is not a merge block. Missing marker
is `unknown` — do not merge.

## Reference routing

- Edit + ship: `references/change.md`
- Tools: `references/tools.md`
