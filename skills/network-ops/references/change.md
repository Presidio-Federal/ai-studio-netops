# Delegate and ship

Network Ops decides the change without loading config bodies. GitHub GitOps
Change performs all config discovery, full-file edits, `dev` puts, and
`apply.yml` polling.

## Handoff

Invoke the worker once with exact targets or one deterministic hostname rule,
operation, exact lines, scope, placement, and preservation constraints. Do
not include a config body.

The invocation's final response is the next input. Do not query task/subagent
status, poll GitHub, or re-invoke the worker.

## Ship

Worker Result `pass` → create `dev` → `main` PR and merge with
`merge_method=merge`. Do not delete `dev`. Any other result → no PR and no
merge.
