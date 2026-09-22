---
name: compliance-test-authoring
version: "1.6.0"
description: "v1.6.0 — Judge applicability from published configs. Put named INTEL tests on git compliance for automatic validation."
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
4. Read git `tests/CAPABILITIES.yml` and one neighbour check from
   `ref=compliance`. Match that shape.
   Formats: [`references/live-checks.md`](references/live-checks.md),
   [`references/static-rules.md`](references/static-rules.md).
5. **Static** if committed config can answer. **Live** if you need
   device state (BGP up, ping, NTP sync). Both if they asked configured *and* working.
6. Commit on existing git **`compliance`** (GitHub contents — not a
   new branch, not `dev`, not `main`):
   - live: `tests/live/checks/<suite>/<id>.yml` (stem = `id`)
   - static: append `tests/static/schemas/<group>/rules.yml`
   - add the id to `catalog/job-catalog.json` (include `nist:` when the check has NIST ids)
   - wire `tests/compliance/matrix/test-bridge.yml` if it is a `NET-COMP` rule
   `github_get_file` those paths `ref=compliance`, then `github_put_file`
   `ref=compliance` with that `sha`. Never `github_create_branch`.
7. Stop. Branch automation validates the candidate and auto-merges successful
   tests to `main`. Do not claim publication before the test appears there.
   Compliance Test later records evidence from a pipeline or authorized
   ad-hoc run; it is not the candidate-branch validator.

Do not write YAML to the workspace. Do not invent an `assert` / `type` outside
`CAPABILITIES.yml`. Do not open a PR. Do not run `author-check.yml`. Do not
change the check because a device failed — that is a finding. An unused
protocol is not a finding and not a check.

Copy intel `nist_sp_800_53` onto `nist:`. Titles only.
