---
name: github-gitops-change
version: "1.3.0"
description: "v1.3.0 — Mechanically apply an exact Network Ops prescription without polling Actions."
---

# GitHub GitOps Change

Mechanical config work only. Network Ops owns config discovery, comparison,
the decision, and PR merge. Pipeline Monitor owns Actions. This skill performs
surgical `dev` puts from an exact prescription.

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
- Set top-level `keys` to the deduplicated union of exact structured entity
  keys, or `[]`; never infer from prose. Allowed prefixes are
  `device|interface|site|service|test|control|incident|change`. Use `site:`
  for location and `interface:<device>/<interface>` when the device is known.
  Keep nested `keys`.

Exact edit flow: [references/change.md](references/change.md).
Exact tools: [references/tools.md](references/tools.md).
