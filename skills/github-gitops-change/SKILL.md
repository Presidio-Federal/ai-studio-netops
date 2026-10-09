---
name: github-gitops-change
version: "1.4.0"
description: "v1.4.0 — submit_change.py applies change.prescription to inventory/configs on dev and writes one operation-run. No Actions, no PR."
---

# GitHub GitOps Change

Mechanical config work only. Network Ops owns config discovery, comparison,
and the decision. Pipeline Monitor owns Actions. This skill performs
surgical `dev` puts from an exact prescription.

## Script

`scripts/submit_change.py` is the editor. It reads `change.prescription`
from `state/network-ops.json`. It does not take the lines on argv.

```text
python3 <skill>/scripts/submit_change.py submit --workspace <file_explorer> [--state state/network-ops.json]
```

`execution_type` is `mcp_orchestration`. `timeout` is 60. One `python3`.
The last stdout line is the result. `--dry-run --fixture <file>` edits
that file in memory and prints a diff. No MCP.

The bytes edited are the body `github_get_file` returned for `ref=dev`.
The script does not read `main` and does not fast-forward `dev`. A `dev`
branch that is behind `main` is edited as it stands.

An open `pr.number` with `release.status` `pending` still commits.
The line then has `batch` true.

## Contract

Require:

- `Targets`: exact hostnames, or one deterministic hostname rule
- `Operation`: `ensure_present`, `ensure_absent`, or `replace`
- `Lines`: exact old/new content required by the operation
- `Scope`: where the lines belong
- `Placement`: an exact anchor or deterministic placement rule
- `Constraints`: preservation requirements

Ambiguous or incomplete prescription → `blocked` before any write.

## State machine

`VALIDATE → LIST → PREFLIGHT_ALL → GET_ALL → EDIT → PUT_CHANGED → WRITE_OPERATION → REPORT`

- List `inventory/configs` on `dev`; use only returned paths.
- Preflight all targets before the first put.
- Preserve unrelated bytes and structure. Never regenerate a config.
- Treat an already-satisfied prescription as idempotent, not a write.
- Put each changed file with its current SHA and `ref=dev`.
- Return the final put SHA as `submitted`; it contains all prior puts on `dev`.
- Never call Actions tools, create a PR, or merge.
- Never return config bodies or full diffs.
- For every terminal result, write exactly one operation-run record
  under `operational/runs/`, including blocked and no-change outcomes.
- A successful put records `status=ok`, `result=submitted`, and null workflow
  fields; Pipeline Monitor writes the later watch result.
- When the prescription's `Scope` is an interface stanza (`interface <name>`),
  record `interfaces[]` as `<device>/<interface>` for every written target,
  spelled as in the config; a global or non-interface scope leaves it empty.
  Do not write `relations[]` on the run — `devices[]`, `interfaces[]`, and
  `git.commit_sha` are the edge.
- Set top-level `keys` to the deduplicated union of exact structured entity
  keys, or `[]`; never infer from prose. Allowed prefixes are
  `device|interface|site|service|test|control|incident|change`. Use `site:`
  for location and `interface:<device>/<interface>` for every `interfaces[]`
  item. Keep nested `keys`.

Exact edit flow: [references/change.md](references/change.md).
Exact tools: [references/tools.md](references/tools.md).
