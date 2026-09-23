# Produce — Compliance Test

Paths, envelope, catalog: **`workspace-handoff`**.
Write schemas live in this skill (`schemas/testing-run.schema.json`,
`schemas/testing-state.schema.json`,
`schemas/compliance-test-visit.schema.json`, and
`schemas/compliance-test-metadata.schema.json`). Readers use catalog rely-on;
they do not load a second copy from workspace-handoff.

## When to write

Every live or static run writes both:

- `operational/testing/YYYY-MM-DDTHH-MM-SSZ.json` — this run; never overwrite
  (e.g. `operational/testing/2026-08-21T19-56-18Z.json`)
- `state/testing.json` — replace; `latest` is that testing path

Also write **only when** `scope.suites` includes `compliance`:

- `compliance/testing/YYYY-MM-DDTHH-MM-SSZ.json` — append-only
  compliance visit with stable metrics and `vs_prior`
- `compliance/metadata-testing.json` — replace after the visit; points to it

Each detailed `ran` and `not_applicable` row includes canonical
`test:<check-id>` and exact `device:<inventory-name>` keys. A report
`suite/check-id` maps to the catalog's `check-id`. Include `control:<id>` only
when source evidence provides the mapping. Metadata points to the detailed
compliance visit.

Read prior metadata and its latest stamp before a compliance run. Write the
new visit before advancing metadata. Keep ten stamps without listing the
directory. Do not write `state/compliance.json`; Compliance Analyzer owns
that chart. Do not write `risk/` or a root `compliance.json`.

Read-only (handoff rely-on): `test-request.json`, inventory json,
`state/network-sync.json`, `state/health.json` if they asked to test what
health flagged, `compliance/intel.json`, `compliance/coverage.json`.

Scope: `references/scope.md`. Trigger/extract: `references/run.md`.

Write each record directly with the built-in workspace file tool. Never create
or run a helper script, use Code Execution or `execute_command`, invoke a
shell, or write through `Internal directory`.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
