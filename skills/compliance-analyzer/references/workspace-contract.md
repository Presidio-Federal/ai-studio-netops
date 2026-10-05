# Produce — Compliance Analyzer

Paths, writers, and rely-on fields come from `workspace-handoff`.

Read only fixed catalog paths:

1. `compliance/metadata-intel.json`, then
   `compliance/intel/<last_visit_id>.json`
2. `compliance/metadata-testing.json`, then
   `compliance/testing/<last_visit_by_environment.prod>.json` and
   `compliance/testing/<last_visit_by_environment.dev>.json` when set
   (v1 metadata: `<last_visit_id>` only)
3. `compliance/coverage.json`
4. `compliance/intel.json`
5. prior `state/compliance.json`

Write only:

- `state/compliance.json` — Kind `state`; replace in full

Do not list directories. Metadata supplies each latest visit (testing:
per lab). Stamp `vs_prior.prior_visit_id` supplies history; for testing
it always points at the same lab. Strip a leading `workspace/` or
`/workspace/` from a source ref before reading it.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
