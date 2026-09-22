# Produce — Compliance Analyzer

Paths, writers, and rely-on fields come from `workspace-handoff`.

Read only fixed catalog paths:

1. `compliance/metadata-intel.json`, then
   `compliance/intel/<last_visit_id>.json`
2. `compliance/metadata-testing.json`, then
   `compliance/testing/<last_visit_id>.json`
3. `compliance/coverage.json`
4. `compliance/intel.json`
5. prior `state/compliance.json`

Write only:

- `state/compliance.json` — Kind `state`; replace in full

Do not list directories. Metadata supplies each latest visit. Stamp
`vs_prior.prior_visit_id` supplies history. Strip a leading `workspace/` or
`/workspace/` from a source ref before reading it.
