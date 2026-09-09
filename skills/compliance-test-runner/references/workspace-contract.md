# Produce — Compliance Test

Paths, envelope, catalog: **`workspace-handoff`**.
Write schemas live in this skill (`schemas/testing-run.schema.json`,
`schemas/testing-state.schema.json`). Shared run/state copies also live
under workspace-handoff for Design/Compliance readers of those two files.

## When to write

Every live or static run writes both:

- `testing/YYYY-MM-DDTHH-MM-SSZ.json` — this run; never overwrite
  (e.g. `testing/2026-08-21T19-56-18Z.json`)
- `state/testing.json` — replace; `latest` is that testing path

Also write **only when** `scope.suites` includes `compliance`:

- `compliance/YYYY-MM-DDTHH-MM-SSZ.json` — same extract; never overwrite
- `state/compliance.json` — replace; `latest` is that compliance path

Do not overwrite `state/compliance.json` from reachability, routing, or
path runs. Do not write `risk/` or a root `compliance.json`.

Read-only (handoff rely-on): `test-request.json`, inventory json,
`state/network-sync.json`, `state/health.json` if they asked to test what
health flagged, `compliance/intel.json`, `compliance/coverage.json`.

Scope: `references/scope.md`. Trigger/extract: `references/run.md`.

## After write

```text
python3 /skills/user/compliance-test-runner/scripts/validate_testing.py run /workspace/testing/2026-08-16T23-10-00Z.json
python3 /skills/user/compliance-test-runner/scripts/validate_testing.py state /workspace/state/testing.json
```

If this run included `compliance`, also validate:

```text
python3 /skills/user/compliance-test-runner/scripts/validate_testing.py run /workspace/compliance/2026-08-16T23-10-00Z.json
python3 /skills/user/compliance-test-runner/scripts/validate_testing.py state /workspace/state/compliance.json
```

Skip if script missing. Never `find /`.
