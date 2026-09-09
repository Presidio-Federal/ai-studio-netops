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

1. Always: `testing/YYYY-MM-DDTHH-MM-SSZ.json` then `state/testing.json`
   (`latest` = that testing path).
2. If `scope.suites` includes `compliance`: also
   `compliance/YYYY-MM-DDTHH-MM-SSZ.json` then `state/compliance.json`
   (`latest` = that compliance path).
   Same extract. Do not update compliance files otherwise.

## Catalog

`catalog/job-catalog.json` lives in **git**, not the workspace. Never
`read_file` it from the workspace.

```text
github_get_file(path="catalog/job-catalog.json", ref="main")
```

Answer from `suites` in that file. If the tool is not attached, list only
the suite names above and say check ids need `github_get_file`. Do not
invent check ids. Do not hunt the disk.
