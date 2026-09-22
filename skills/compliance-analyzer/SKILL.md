---
name: compliance-analyzer
version: "1.0.0"
description: "Analyze and trend compliance intelligence and test visits. Keep tested posture separate from framework coverage. Write SOAP to state/compliance.json."
---

# Compliance Analyzer

For the primary **Compliance** agent. You synthesize chart evidence already
on disk. You do not query frameworks, GitHub, or devices; author tests; run
workflows; or change configuration.

## Hard boundaries

Write only `state/compliance.json`. Do not write under `compliance/`,
`testing/`, or another agent's state. Do not execute scripts or list
directories. Missing evidence produces `unknown` or `partial`, never invented
measurements.

## Inputs

Read fixed paths through `workspace-handoff`:

- `compliance/metadata-intel.json` → latest Intel stamp
- `compliance/metadata-testing.json` → latest Test stamp
- `compliance/coverage.json`
- `compliance/intel.json`
- prior `state/compliance.json`

Use `references/analyze.md` for freshness, series, scores, findings, status,
and SOAP. Use `references/workspace-contract.md` for paths and ownership.
Write from `schemas/compliance-state.schema.json`; shape follows
`examples/compliance-state.example.json`.

## State machine

READ_METADATA → READ_LATEST_STAMPS → READ_CURRENT_WORKING_STATE →
READ_PRIOR_CHART → CHECK_24H_FRESHNESS → DISPATCH_STALE →
FOLD_SERIES → SCORE → SYNTHESIZE → WRITE_CHART → READ_BACK → STOP

## Modes

Default `assess-now`. Refresh only a plane whose latest evidence is missing
or at least 24 hours old.

- `assess-now`: dispatch stale attached specialists without waiting; use
  files already read.
- `refresh-then-assess`: wait only for stale material planes, reread their
  metadata and latest stamps, then assess.

## Output

`state/compliance.json` contains:

- freshness and coverage for Intel and Test
- consults citing latest evidence
- last-ten-visit series per plane
- separate tested-posture and framework-coverage scores
- structured findings carrying exact relationship keys
- assessment, trend analysis, SOAP, dispatches, and read paths

The plan may request a stale Intelligence/Test visit, refer operator-selected
recommendations to Compliance Author, refer proven failures to Network Ops,
or say `none`. It must not contain a raw configuration change.
