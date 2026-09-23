# Bounded config change

## Preflight

List `inventory/configs` on `dev`. Resolve every requested hostname or
deterministic hostname rule against that response. Do not guess a path,
extension, platform, target, command, scope, or placement.

Get all resolved files before writing any. If any target is missing,
ambiguous, or incompatible with the prescription, return `blocked` with no
writes.

## Edit

Apply only the named operation:

- `ensure_present`: add the exact line only when absent from the named scope
- `ensure_absent`: remove only the exact matching line from the named scope
- `replace`: replace only the exact old lines in the named scope

Preserve unrelated content, order, indentation, comments, and line endings.
Do not render a fresh configuration. If placement cannot be followed exactly,
return `blocked`.

## Commit

Put changed files to their original listed paths on `ref=dev`, using each
retrieved SHA. Record every commit SHA. The final put SHA represents the
cumulative proposal.

No changes → `no_change`. Otherwise return the final SHA as `submitted` to
Network Ops. Do not call Actions tools; Pipeline Monitor owns the exact-SHA
watch.

The operation record's top-level `keys` is the deduplicated union derived only
from structured entities, or `[]`; never infer from config text, marker text,
headlines, or summaries. Allowed prefixes are
`device|interface|site|service|test|control|incident|change`. Location is
`site:`; a known-device interface is `interface:<device>/<interface>`. Keep
nested keys.
