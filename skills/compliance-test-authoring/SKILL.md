---
name: compliance-test-authoring
version: "1.4.3"
description: "v1.4.3 — Write a check to git. Copy nist onto the catalog check. Do not run test.yml."
---

# Compliance test authoring

For **Compliance Author**. Workspace is input. Checks live in **git**. After you
push, stop or hand off to **Compliance Test**. Do not call `github_run_action`.
Do not poll runs.

## Write

1. Read the ask, or `compliance/intel.json` if they pointed at it.
2. Read git `tests/CAPABILITIES.yml` and one neighbour check. Match that shape.
   Formats: [`references/live-checks.md`](references/live-checks.md),
   [`references/static-rules.md`](references/static-rules.md).
3. **Static** if committed config can answer. **Live** if you need device
   state (BGP up, ping, NTP sync). Both if they asked configured *and* working.
4. Push to `main` (GitHub contents — not a config PR):
   - live: `tests/live/checks/<suite>/<id>.yml` (stem = `id`)
   - static: append `tests/static/schemas/<group>/rules.yml`
   - add the id to `catalog/job-catalog.json` (include `nist:` when the check has NIST ids)
   - wire `tests/compliance/matrix/test-bridge.yml` if it is a `NET-COMP` rule
5. Stop. Invoke Compliance Test to run the new check, or tell the operator to.

Do not write YAML to the workspace. Do not invent an `assert` / `type` outside
`CAPABILITIES.yml`. Do not open a PR. Do not run `author-check.yml`. Do not
change the check because a device failed — that is a finding.

Copy intel `nist_sp_800_53` onto `nist:`. Titles only.
