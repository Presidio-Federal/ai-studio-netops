---
name: compliance-test-authoring
version: "1.5.0"
description: "v1.5.0 — Judge applicable from git configs. Named INTEL row only. Put on existing git dev. Do not run test.yml."
---

# Compliance test authoring

For **Compliance Author**. Workspace is input. Checks live in **git**. After you
push, stop or hand off to **Compliance Test**. Do not call `github_run_action`.
Do not poll runs.

## Write

1. Read the ask, or `compliance/intel.json` if they pointed at it.
   Implement that INTEL id / suggested_assert. Do not invent extra
   checks the row did not need.
2. Read `inventory/prod.json` if present. Read committed
   running-configs from git (`github_get_file` on
   `inventory/configs/` for an edge/wan, more if the first is not
   typical). Live GET only if git config is missing.
3. **Applicable** is a judgment from those files. A protocol or
   feature that does not appear in config is not a check — including
   when intel said “applicable IGP.” Do not write `output_matches`
   / empty-section patterns that pass when the protocol is absent.
4. Read git `tests/CAPABILITIES.yml` and one neighbour check. Match that shape.
   Formats: [`references/live-checks.md`](references/live-checks.md),
   [`references/static-rules.md`](references/static-rules.md).
5. **Static** if committed config can answer. **Live** if you need
   device state (BGP up, ping, NTP sync). Both if they asked configured *and* working.
6. Commit on existing git **`dev`** (GitHub contents — not a
   new branch, not a config PR, not `main`):
   - live: `tests/live/checks/<suite>/<id>.yml` (stem = `id`)
   - static: append `tests/static/schemas/<group>/rules.yml`
   - add the id to `catalog/job-catalog.json` (include `nist:` when the check has NIST ids)
   - wire `tests/compliance/matrix/test-bridge.yml` if it is a `NET-COMP` rule
   `github_get_file` those paths `ref=dev`, then `github_put_file`
   `ref=dev` with that `sha`. Never `github_create_branch`. `main`
   is blocked.
7. Stop. Invoke Compliance Test to run the new check, or tell the operator to.

Do not write YAML to the workspace. Do not invent an `assert` / `type` outside
`CAPABILITIES.yml`. Do not open a PR. Do not run `author-check.yml`. Do not
change the check because a device failed — that is a finding. An unused
protocol is not a finding and not a check.

Copy intel `nist_sp_800_53` onto `nist:`. Titles only.
