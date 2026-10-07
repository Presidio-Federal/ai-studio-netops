---
name: compliance-analyzer
version: "1.2.1"
description: "v1.2.1 — Score the chart from the visit metrics; findings come from the failing rows."
---

# Compliance Analyzer

For the primary **Compliance** agent. `scripts/assess_chart.py` builds
`state/compliance.json` from the visits already on disk. The agent sets
the opinion. You do not query frameworks, GitHub, or devices; author
tests; run workflows; or change configuration.

## Hard boundaries

The script writes only `state/compliance.json`. Do not write under
`compliance/`, `testing/`, or another agent's state. Do not list
directories. Missing evidence produces `unknown` or `partial`, never
invented measurements.

Run it with `execution_type: standard`. It does not call MCP.

```text
python3 <skill>/scripts/assess_chart.py assess --workspace <file_explorer> --mode assess-now
python3 <skill>/scripts/assess_chart.py annotate --workspace <file_explorer> --opinion "..." --why "..." --plan "..."
```

`assess` fills scores, series, flips, findings, status, and a factual
plan. `needs_opinion` on its last line means the opinion is still a
placeholder. `annotate` replaces the opinion, the trend narrative, and
the plan, and leaves the scores alone.

## Inputs

The script reads fixed paths. Do not open them to fill the chart:

- `compliance/metadata-intel.json` → latest Intel stamp
- `compliance/metadata-testing.json` → latest prod and latest dev Test
  stamps (`last_visit_by_environment`)
- `compliance/coverage.json`
- `compliance/intel.json`
- prior `state/compliance.json`

`references/analyze.md` is the rule the script follows for freshness,
series, scores, trend, findings lifecycle, status, and SOAP.
`references/workspace-contract.md` is ownership. The schema is
`schemas/compliance-state.schema.json`.

## Trend is the point

Every chart answers "is compliance getting better?" from keyed evidence.
The script copies it. Do not recompute it in the reply.

- The latest prod test visit's `vs_prior` already lists which test +
  device pairs went FAIL/ERROR → PASS and PASS → FAIL/ERROR against the
  previous **prod** visit. Those become `trend_analysis.flips`. Never
  compare Dev with prod.
- Three scores, each with prior → current: tested posture (per test),
  device checks (per device row — moves on partial fixes), framework
  coverage.
- `trend_analysis.direction` is mechanical: `improving`, `worsening`,
  `mixed`, `unchanged`, or `first`.
- Findings carry `status`. A failure that now passes becomes
  `remediated` with `resolved_at` and stays on the chart for 7 days; it
  does not silently disappear. One that fails again is `regressed`.

## State machine

ASSESS_SCRIPT → DISPATCH_STALE → ASSESS_SCRIPT_AGAIN → ANNOTATE_OPINION → STOP

## Modes

Default `assess-now`. Refresh only a plane whose latest evidence is missing
or at least 24 hours old.

- `assess-now`: dispatch stale attached specialists without waiting, then
  run `assess` again with `--dispatched`.
- `refresh-then-assess`: wait only for stale material planes, then run
  `assess` again.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## Output

The agent does not write this file. `assess` writes it and `annotate`
fills the opinion. `state/compliance.json` (`compliance-state/v2`) contains:

- freshness and coverage for Intel and Test
- consults citing latest evidence
- last-ten-visit series per plane (testing: both labs, one watermark each)
- three separate scores and the lab they come from
- findings with `status`, `first_seen`, `resolved_at`, exact keys
- `trend_analysis`: direction, prior → current scores, flips, narrative
- assessment, SOAP, dispatches, and read paths

The plan may request a stale Intelligence/Test visit, refer operator-selected
recommendations to Compliance Author, refer proven failures to Network Ops,
or say `none`. It must not contain a raw configuration change.
