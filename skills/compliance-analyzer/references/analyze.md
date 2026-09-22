# Analyze compliance over time

Compliance Intelligence and Compliance Test are independent evidence
producers. Read their files; do not depend on their chat replies.

## Fixed read order

1. `compliance/metadata-intel.json`, then its
   `compliance/intel/<last_visit_id>.json`
2. `compliance/metadata-testing.json`, then its
   `compliance/testing/<last_visit_id>.json`
3. `compliance/coverage.json`
4. `compliance/intel.json`
5. prior `state/compliance.json`

Do not list directories. Record opened paths in `read[]`.

## Freshness and modes

Each evidence plane is current for 24 hours from `checked_at`.

- `missing`: no metadata pointer or latest stamp
- `stale`: `now >= checked_at + 24h`
- `current`: inside the 24-hour window, including partial/unavailable visits

Default `assess-now`. Dispatch only stale or missing material planes.
Do not wait; assess existing files. `refresh-then-assess` waits for stale
material planes, rereads metadata and the new stamp, then assesses. Never
refresh current evidence.

Invoke lines come from `workspace-handoff`.

## Series fold

Maintain separate Intel and Testing series, window 10.

For each plane:

1. Start at metadata `last_visit_id`.
2. If it equals the prior chart watermark, keep points unchanged.
3. Otherwise read that stamp and follow `vs_prior.prior_visit_id` newest to
   oldest until the watermark, null, missing file, or ten stamps.
4. Reverse unseen visits; append each visit's `metrics` object verbatim.
5. Keep the newest ten points and set watermark to the newest visit read.

Do not alter prior points. Fold first, then synthesize.

## Scores

Never blend these scores.

### Tested posture

Use canonical test ids, not device-result row count:

- verified test: all executed rows for that test PASS
- failing test: any row for that test is FAIL or ERROR
- skipped test: no FAIL/ERROR and at least one SKIP
- N/A-only test: all rows are not applicable

`denominator = verified_tests + failing_tests`

`percent = 100 * verified_tests / denominator`, rounded to one decimal.
When denominator is zero, percent is null. SKIP and N/A are reported but
excluded from the percentage.

### Framework coverage

Use `compliance/coverage.json` counts:

`denominator = covered + partial + gap + unwired`

`percent = 100 * covered / denominator`, rounded to one decimal.
When denominator is zero, percent is null. `not_applicable` is excluded.
Do not award partial credit; preserve the partial count.

## Findings and keys

Create findings from evidence, never assumptions:

- Intel candidate or coverage gap → `missing_control`
- Test FAIL/ERROR → `test_failure`
- Test SKIP, unavailable source, or no scoreable test → `evidence_gap`

Copy every source-supported key on the finding. Join rows that share exact
`type:name` keys. `source_refs` cite stamps, not raw payloads.

Route:

- missing control → operator selects it, then Compliance Author
- test failure → Network Ops
- stale/missing test evidence → Compliance Test
- stale/missing framework evidence → Compliance Intelligence

## Consults and assessment

Consult status:

- Intel: `unknown` unavailable; `partial` gaps/candidates remain; `ok` no
  relevant gaps
- Testing: `unknown` no scoreable evidence; `degraded` FAIL/ERROR; `partial`
  SKIP; `ok` otherwise

Write each consult impression and trend note from the visit plus series.
Do not paste a headline.

Assessment separates:

- `noncompliant`: proven FAIL/ERROR
- `compliant`: what current execution actually verified
- `gaps`: missing controls, partial coverage, skips, unavailable evidence
- `contradictions`: disagreement between framework and execution evidence
- `opinion`: one verdict naming both scores when known

## Status precedence

First match:

1. `unknown`: neither plane has usable evidence
2. `stale_chart`: either material plane is stale or was dispatched
3. `degraded`: current testing has FAIL/ERROR
4. `partial`: a plane is missing/unavailable, testing has SKIP, or framework
   coverage has partial/gap/unwired rows
5. `ok`: current evidence, no failures, skips, or framework gaps

## SOAP

- Subjective: why analysis ran
- Objective: latest evidence, freshness, both scores, and measured deltas
- Assessment: exactly `assessment.opinion`
- Plan: stale specialist visit, operator-selected Author work, Network Ops
  referral for proven failures, or `none`

`next_action` equals `soap.plan`. Do not write configuration commands,
invent root cause, or invoke Network Ops.
