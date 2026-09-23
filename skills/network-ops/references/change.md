# Delegate and ship

Network Ops decides the change without loading config bodies. GitHub GitOps
Change performs bounded config inspection, full-file edits, and `dev` puts.
Pipeline Monitor owns `apply.yml` polling.

## Handoff

When exact syntax is missing, invoke GitOps Change in `inspect` mode with
exact targets/question and an exact or deterministic peer rule. Decide from
its bounded evidence. Then invoke it in `apply` mode with exact targets,
operation, lines, scope, placement, and preservation constraints. Do not
include a config body.

Each invocation's final response is the next input. Do not query
task/subagent status.

## Ship

Apply Result `submitted` → invoke Pipeline Monitor once with `workflow=apply.yml`,
`ref=dev`, and the exact commit SHA. Monitor Result `pass` → create `dev` →
`main` PR and merge with `merge_method=merge`. Do not delete `dev`. Any other
terminal result → no PR and no merge.

After the terminal result, replace `state/network-ops.json` with only the
compact worker, CI, and PR evidence. Set top-level `keys` to the deduplicated
union derived only from structured entities, or `[]`; never infer from prose.
Allowed prefixes are `device|interface|site|service|test|control|incident|change`.
Use `site:` for location and `interface:<device>/<interface>` when the device
is known; preserve nested keys. Preserve the
GitOps record in `change.operational_ref` and the Pipeline Monitor record in
`change.monitoring_ref`.
