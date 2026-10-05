# Analyze compliance over time

Compliance Intelligence and Compliance Test are independent evidence
producers. Read their files; do not depend on their chat replies.

The chart's job is to say whether compliance is getting better. That is
decided from keyed evidence (which test on which device flipped, which
score moved), not from prose. Trend is a lab-to-same-lab comparison:
production against production, Dev against Dev.

## Fixed read order

1. `compliance/metadata-intel.json`, then its
   `compliance/intel/<last_visit_id>.json`
2. `compliance/metadata-testing.json`, then
   `compliance/testing/<last_visit_by_environment.prod>.json` and, when
   set and different, `compliance/testing/<last_visit_by_environment.dev>.json`.
   A v1 metadata file has only `last_visit_id`: open that one.
3. `compliance/coverage.json`
4. `compliance/intel.json`
5. prior `state/compliance.json`

Do not list directories. Record opened paths in `read[]`.

**Primary test visit** = the latest prod visit; when there is none, the
latest dev visit (proposal evidence, said so in the narrative). Scores,
trend, and test findings come from the primary visit.

## Freshness and modes

Each evidence plane is current for 24 hours from `checked_at` (testing:
the primary visit).

- `missing`: no metadata pointer or latest stamp
- `stale`: `now >= checked_at + 24h`
- `current`: inside the 24-hour window, including partial/unavailable visits

Default `assess-now`. Dispatch only stale or missing material planes.
Do not wait; assess existing files. `refresh-then-assess` waits for stale
material planes, rereads metadata and the new stamp, then assesses. Never
refresh current evidence.

Invoke lines come from `workspace-handoff`.

## Series fold

Separate Intel and Testing series, window 10. Fold first, then
synthesize. Do not alter prior points.

**Intel.** Start at metadata `last_visit_id`. Equal to the prior
chart's `series.intel.watermark` → unchanged. Otherwise follow
`vs_prior.prior_visit_id` newest to oldest until the watermark, null, a
missing file, or ten stamps; reverse; append each `metrics` verbatim;
keep ten; watermark = newest read.

**Testing, per lab** (`prod`, then `dev`). Start at
`last_visit_by_environment.<lab>`. Equal to
`series.testing.watermarks.<lab>` → nothing new. Otherwise follow
`vs_prior.prior_visit_id` (same lab by construction) until the
watermark, null, a missing file, a v1 stamp (no `metrics.environment`),
or ten stamps. Append each `metrics` verbatim. Then sort all points by
`at`, keep the newest ten, set `watermarks.<lab>` = newest read.

A v1 prior chart has `series.testing.watermark`: treat it as the
watermark of whichever lab that visit belongs to; the other is null.

## Scores

Never blend these scores. `scores.environment` = the primary visit's lab.

### Tested posture

From the primary visit, by canonical test id:

- verified test: all executed rows for that test PASS
- failing test: any row for that test is FAIL or ERROR
- skipped test: no FAIL/ERROR and at least one SKIP
- N/A-only test: all rows are not applicable

`denominator = verified_tests + failing_tests`;
`percent = 100 * verified_tests / denominator`, one decimal; null when 0.

### Device checks

From the primary visit's `results.counts_ran`:
`passed = pass`, `failing = fail + error`,
`denominator = passed + failing`, `percent = 100 * passed / denominator`,
one decimal; null when 0. This score moves when some devices of a
still-failing test are fixed; tested posture does not.

### Framework coverage

From `compliance/coverage.json` counts:
`denominator = covered + partial + gap + unwired`;
`percent = 100 * covered / denominator`, one decimal; null when 0.
`not_applicable` excluded. No partial credit; keep the partial count.

## Trend

Fill `trend_analysis` mechanically, then write the narrative.

**Nothing new.** Both the Intel watermark and the primary lab's testing
watermark equal the prior chart's → copy the prior chart's
`trend_analysis` unchanged except `narrative` (say no new evidence since
<watermark>). A re-run never turns an improvement into `unchanged`.

**Otherwise:**

- `environment` = `scores.environment`; `since_visit_id` = the primary
  visit's `vs_prior.prior_visit_id`.
- `newly_passing`, `newly_failing` = the lengths of those `vs_prior`
  lists; `still_failing` copied.
- `flips[]` = each `newly_failing` item (`direction` `worse`), then each
  `newly_passing` item (`direction` `better`), with `environment` and
  `at` = the primary visit's `checked_at`. Cap 20.
- `scores.tested_posture` / `scores.device_checks`: `current` = this
  chart's percent; `prior` = current minus `vs_prior.metrics_delta`
  (`tested_posture_pct` / `device_check_pass_pct`); null when
  `metrics_delta` is null.
- `scores.framework_coverage`: `current` = this chart's percent;
  `prior` = the prior chart's `scores.framework_coverage.percent` when
  the Intel watermark moved, else the prior chart's
  `trend_analysis.scores.framework_coverage.prior`; null with no prior
  chart.

**Direction.** Signals:

| Signal | + | − |
|--------|---|---|
| test visit `vs_prior.delta` | `better` | `worse` (`mixed` is both) |
| framework coverage | `current > prior` | `current < prior` |

`first` when the test delta is `first` and framework has no prior.
`improving` when there is at least one + and no −. `worsening` when at
least one − and no +. `mixed` when both. `unchanged` when neither.

A Dev primary visit trends Dev only; the narrative says so. Never
compare a Dev visit with a prod visit, and never call a Dev pass
production remediation.

## Findings and their lifecycle

Create findings from evidence, never assumptions:

- Intel candidate or coverage gap → `missing_control`
- Test FAIL/ERROR → `test_failure`
- Test SKIP, unavailable source, or no scoreable test → `evidence_gap`

Copy every source-supported key. Join rows that share exact `type:name`
keys. `source_refs` cite stamps, not raw payloads.

**Carry, do not recreate.** Match each prior chart finding to this
visit's evidence by `kind` + its `test:` key (`test_failure`) or
`control:` key (`missing_control`, `evidence_gap`):

| Prior finding | This evidence | Result |
|---------------|---------------|--------|
| `open` / `regressed` test_failure | the test still has FAIL/ERROR rows in the primary visit | `open` (stays `regressed` if it was); `keys` = test, controls, and the devices still failing |
| `open` / `regressed` test_failure | every row of that test now PASS | `remediated`, `resolved_at` = primary visit `checked_at`, `next_owner` `none` |
| `open` missing_control | `coverage.json` row now `covered` | `remediated`, `resolved_at` = Intel visit `checked_at`, `next_owner` `none` |
| `remediated` | fails or is missing again | `regressed`, `resolved_at` null, `next_owner` as for a new finding |
| `remediated` | still passing | unchanged; drop it once `resolved_at` is older than 7 days |
| none | new FAIL/ERROR or gap | new finding, `open`, `first_seen` = that visit's `checked_at` |

`first_seen` is always carried from the prior finding. A still-open
test_failure whose test has `newly_passing` items says so in the
summary: "fixed on <devices> since <since_visit_id>; still failing on
<devices>". A prior v1 finding with no `status` is `open` with
`first_seen` = the prior chart's `analyzed_at`.

Order: `regressed`, `open`, then `remediated`; keep 20.

Route:

- missing control → operator selects it, then Compliance Author
- test failure → Network Ops
- stale/missing test evidence → Compliance Test
- stale/missing framework evidence → Compliance Intelligence
- remediated → `none`

## Consults and assessment

Consult status:

- Intel: `unknown` unavailable; `partial` gaps/candidates remain; `ok` no
  relevant gaps
- Testing: `unknown` no scoreable evidence; `degraded` FAIL/ERROR; `partial`
  SKIP; `ok` otherwise

Consult `trend` for testing = the primary visit's `vs_prior.delta`.
Write each consult impression and trend note from the visit plus series.
Do not paste a headline.

Assessment separates:

- `noncompliant`: proven FAIL/ERROR
- `compliant`: what current execution actually verified, including what
  was remediated since the prior same-lab visit
- `gaps`: missing controls, partial coverage, skips, unavailable evidence
- `contradictions`: disagreement between framework and execution evidence
- `opinion`: one verdict naming both scores when known and the direction

## Status precedence

First match:

1. `unknown`: neither plane has usable evidence
2. `stale_chart`: either material plane is stale or was dispatched
3. `degraded`: current testing has FAIL/ERROR
4. `partial`: a plane is missing/unavailable, testing has SKIP, or framework
   coverage has partial/gap/unwired rows
5. `ok`: current evidence, no failures, skips, or framework gaps

Remediated findings do not affect status.

## Headline and SOAP

`headline` starts with the direction: `Improving:`, `Worsening:`,
`Mixed:`, `Unchanged:`, or `Baseline:`, then the scores and the biggest
flip or open failure.

- Subjective: why analysis ran
- Objective: latest evidence, freshness, all three scores with prior →
  current, and the flips
- Assessment: exactly `assessment.opinion`
- Plan: stale specialist visit, operator-selected Author work, Network Ops
  referral for proven failures, or `none`

`next_action` equals `soap.plan`. Do not write configuration commands,
invent root cause, or invoke Network Ops.
