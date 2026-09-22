---
name: github-gitops-change
version: "1.0.0"
description: "Apply a bounded config prescription to git dev, then poll the exact apply.yml run. Large configs stay in the local worker."
---

# GitHub GitOps Change

Mechanical execution only. Network Ops owns the decision and PR merge. This
skill owns config file reads, surgical edits, `dev` puts, and the resulting
pipeline watch.

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

`VALIDATE → LIST → PREFLIGHT_ALL → GET_ALL → EDIT → PUT_CHANGED → WATCH_FINAL → REPORT`

- List `inventory/configs` on `dev`; use only returned paths.
- Preflight all targets before the first put.
- Preserve unrelated bytes and structure. Never regenerate a config.
- Treat an already-satisfied prescription as idempotent, not a write.
- Put each changed file with its current SHA and `ref=dev`.
- Watch only the final put's SHA; it contains all prior puts on `dev`.
- Never trigger `apply.yml`, create a PR, or merge.
- Never return config bodies or full diffs.

Exact edit flow: [references/change.md](references/change.md).
Exact tools: [references/tools.md](references/tools.md).
