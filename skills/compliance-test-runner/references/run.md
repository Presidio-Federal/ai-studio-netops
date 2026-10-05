# Test run

Invoke that names a run is authorization. Do not confirm.

## Request file

Read `test-request.json` first (workspace-relative). If it exists, `status`
is `PENDING`, and `updated_at` is recent: that is the scope. You do not
write this file.

## Suites

| Ask | `suites` |
|-----|----------|
| default / live | `reachability,routing,path` |
| routing / BGP | `reachability,routing` |
| path / ping | `path` |
| compliance | `compliance` (never in the default set) |
| static | `mode=static` |

`live_lab` defaults to `dev`. Use `prod` only when asked. Resolve names and
tag groups from `references/scope.md` **before** you trigger.

## Trigger

This repository contract dispatches the published workflow definition from
`main`. That ref does not choose the lab; the `environment` input does.

```text
github_run_action(workflow="test.yml", ref="main", inputs={...})
github_list_action_runs(workflow="test.yml", limit=5)
```

All input values are strings. Dispatch does not return a run id. Do not invent
a `request_id` — leave it empty. `reason` can be `adhoc`.

Poll: `github_get_action_run(run_id=...)` until `completed`. No sleep script.

Then: `github_get_action_job_logs(job_id=..., tail_lines=200)`.

Marker prefix: `# Network test report`. Read the suffix.

## Counts

| Report | Means |
|--------|-------|
| PASS / FAIL | ran — real evidence |
| not_applicable / N/A | tag miss — not a gap |
| skip | could not run — **coverage gap** |

All-skip is not a pass. Missing marker is `unknown`.

Prove `devices=` from the log. Empty after you asked for a host →
`scope_honoured: false`.

## Risk (Dev default)

| Evidence | level | push_to_prod |
|----------|-------|--------------|
| All in-scope passed, no skip gaps | LOW | `proceed_with_caution` |
| Passed with skip gaps | MEDIUM | `proceed_with_caution` |
| Fail on reachability, BGP, or path | HIGH | `do_not_push` |
| No report | UNKNOWN | `unknown` |

Never `proceed` for a Dev run.

## Write

UTC stamp from `updated_at` (same as Health): `2026-08-25T00:28:30Z` →
`2026-08-25T00-28-30Z`. Filename `YYYY-MM-DDTHH-MM-SSZ.json`. Do not use
`20260825T002830Z`. `local_path` on the run file must match the path
you wrote.

1. Always: `operational/testing/YYYY-MM-DDTHH-MM-SSZ.json` then `state/testing.json`
   (`latest` = that testing path).
2. If `scope.suites` includes `compliance`: read
   `compliance/metadata-testing.json`, then the prior visit **for this
   run's environment**:
   `compliance/testing/<last_visit_by_environment.<live_lab>>.json`. Write
   `compliance/testing/YYYY-MM-DDTHH-MM-SSZ.json` with metrics and
   `vs_prior`, then replace `compliance/metadata-testing.json`
   (`last_visit_id`, `last_collected_at`, and this environment's
   `last_visit_by_environment` entry; keep the other environment's entry).
   Do not write `state/compliance.json`; Compliance Analyzer owns it.

A v1 metadata file has no `last_visit_by_environment`: open its
`last_visit_id`; when that visit's `environment.live_lab` matches, it
is the prior, else there is no prior. Write the v2 metadata with both
entries (the other one from that visit, or null).

### Metrics

Group rows by canonical `test:<check-id>`:

- any FAIL/ERROR → failing test
- otherwise at least one PASS → verified test
- otherwise at least one SKIP → skipped test
- N/A-only tests are counted only in `not_applicable`

`tested_posture_pct` = 100 × verified ÷ (verified + failing).
`device_check_pass_pct` = 100 × pass ÷ (pass + fail + error). One
decimal; null when the denominator is 0. `visit_id` and `environment`
copy this visit.

### vs_prior — same environment only

Never compare a Dev visit with a prod visit. No prior for this
environment → `prior_visit_id` null, `delta` `first`, empty lists,
`still_failing` 0, `metrics_delta` null.

With a prior, match rows by `test:` + `device:` key. Two lookups, in
this order:

1. Each **prior** row with `status` FAIL or ERROR: find the same test
   + device in this run. PASS → `newly_passing` item. FAIL or ERROR →
   count in `still_failing`. Missing or SKIP → nothing.
2. Each **current** row with `status` FAIL or ERROR: find the same
   test + device in the prior. PASS → `newly_failing` item.

Item: `{test, device, from, to, keys}` — `keys` copied from this run's
row. SKIP, N/A, and pairs present on one side only are not flips.

`delta`: `better` when `newly_passing` is non-empty and
`newly_failing` empty; `worse` the reverse; `mixed` both non-empty;
`unchanged` both empty.

`metrics_delta`: this visit's `verified_tests`, `failing_tests`,
`tested_posture_pct`, `device_check_pass_pct` minus the prior's (null
for a percent that is null on either side).

Do not compare prose headlines. Do not write any other diff field.

For every `results.ran[]` and `results.not_applicable[]` row:

- `keys` includes `test:<check-id>` and exact `device:<device>`; when the
  report says `suite/check-id`, use the final `check-id` so it joins catalog
  and coverage rows
- add `control:<id>` only when the report or published catalog maps it
- never add a key for an entity absent from the evidence

## Catalog

`catalog/job-catalog.json` lives in **git**, not the workspace. Never
`read_file` it from the workspace.

```text
github_get_file(path="catalog/job-catalog.json", ref="main")
```

Answer from `suites` in that file. If the tool is not attached, list only
the suite names above and say check ids need `github_get_file`. Do not
invent check ids. Do not hunt the disk.
