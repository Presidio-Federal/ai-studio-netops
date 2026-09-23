---
name: compliance-test-authoring
version: "1.7.0"
description: "v1.7.0 — Publish complete check-to-bridge-to-NET-COMP chains on git compliance."
---

# Compliance test authoring

For **Compliance Author**. Workspace is input. Candidate checks live on git
`compliance`; automation validates and publishes them. After you push, stop.
Do not call `github_run_action` or poll runs.

## Write

1. Read the ask, or `compliance/intel.json` if they pointed at it.
   Implement that INTEL id / suggested_assert. Do not invent extra
   checks the row did not need.
2. Read `inventory/prod.json` if present. List git `inventory/configs`
   on `main`, then read a listed committed running-config for an edge/wan
   (more if the first is not typical). Never guess a filename or suffix.
   Live GET only if git config is missing.
3. **Applicable** is a judgment from those files. A protocol or
   feature that does not appear in config is not a check — including
   when intel said “applicable IGP.” Do not write `output_matches`
   / empty-section patterns that pass when the protocol is absent.
4. On `ref=compliance`, read `tests/CAPABILITIES.yml`,
   `catalog/job-catalog.json`, and
   `tests/compliance/matrix/test-bridge.yml`. List
   `tests/compliance/matrix` and read the returned matrix path; never guess
   its filename. Read one neighbouring check/rule and one neighbouring bridge
   mapping. Match those shapes.
   Formats: [`references/live-checks.md`](references/live-checks.md),
   [`references/static-rules.md`](references/static-rules.md).
5. **Static** if committed config can answer. **Live** if you need
   device state (BGP up, ping, NTP sync). Both if they asked configured *and* working.
6. Build one complete compliance implementation chain on existing git
   **`compliance`** (GitHub contents — not a new branch, not `dev`, not
   `main`):
   - live: `tests/live/checks/<suite>/<id>.yml` (stem = `id`)
   - static: append `tests/static/schemas/<group>/rules.yml`
   - select an existing `NET-COMP-*` rule that expresses the same requirement,
     or add the smallest new rule using the existing matrix shape
   - map every new live/static implementation id to that rule in
     `tests/compliance/matrix/test-bridge.yml`
   - add the implementation id to `catalog/job-catalog.json`; include `nist:`
     only when the bridge chain supports that coverage claim
   `github_get_file` those paths `ref=compliance`, then `github_put_file`
   `ref=compliance` with that `sha`. Never `github_create_branch`.
7. Verify before the final put:
   - every new live/static id exists exactly once
   - every id that contributes to compliance has exactly one intended bridge
     mapping and its `NET-COMP-*` target exists
   - bridge ids, catalog ids, filenames, and rule ids match exactly
   - NIST relationships are intentional; live and static lists need not be
     identical when they prove different things
   Missing or ambiguous linkage → `blocked`; never publish a catalog-only
   coverage claim. Put matrix/check assets first, bridge next, and the catalog
   last.
8. Stop. Branch automation validates the candidate and auto-merges successful
   tests to `main`. Do not claim publication before the test appears there.
   Compliance Test later records evidence from a pipeline or authorized
   ad-hoc run; it is not the candidate-branch validator.

Do not write YAML to the workspace. Do not invent an `assert` / `type` outside
`CAPABILITIES.yml`. Do not open a PR. Do not run `author-check.yml`. Do not
change the check because a device failed — that is a finding. An unused
protocol is not a finding and not a check.

Copy applicable intel `nist_sp_800_53` onto the implementation and catalog
`nist:` fields only when the completed matrix/bridge chain represents those
controls. Titles only.
