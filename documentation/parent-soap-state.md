# Parent SOAP state

This is the contract for the attending parent of a domain. Read it
before changing a prompt, a skill, or a `state/` file. Paths and
writers also live in `skills/workspace-handoff/SKILL.md`. The
architecture is `documentation/patient-chart.md`.

The Studio workspace is the case. Agents do not pass the chart to
each other in chat. A parent writes one current chart. Later agents
read that file.

## Who writes SOAP

SOAP is the attending note. It is the parent's interpretation of
evidence that specialists already wrote. Two parents write it today.

| Parent | Prompt | Skill | File | Schema |
|--------|--------|-------|------|--------|
| Health Analyzer | `agents/health-analyzer-agent.md` | `skills/health-analyzer` | `state/health.json` | `schemas/health-state.schema.json` (`health-state/v7`) |
| Compliance | `agents/compliance-agent.md` | `skills/compliance-analyzer` | `state/compliance.json` | `schemas/compliance-state.schema.json` (`compliance-state/v2`) |

`source_agent` is `health-analyzer` on the health chart and
`compliance` on the compliance chart.

Every other agent leaves those two files alone. A specialist does
not write `state/`, does not add a `soap` object to its own visit,
and does not summarize the parent's chart back into a second file.

These specialists produce the evidence the parent reads. They stop
after their own catalog rows:

| Domain | Specialists | What they write |
|--------|-------------|-----------------|
| Health | Health Monitor (Splunk, NetFlow), Health Application, Health Device, Health ServiceNow | `health/metadata-<plane>.json` and, when the visit is material, `health/<plane>/<stamp>.json` |
| Compliance | Compliance Intelligence, Compliance Test | `compliance/coverage.json`, `compliance/intel.json`, `compliance/intel/<stamp>.json`, `compliance/metadata-intel.json`; and for a compliance suite `compliance/testing/<stamp>.json`, `compliance/metadata-testing.json`. Every test run also writes `operational/testing/<stamp>.json` and `state/testing.json` |

`state/testing.json` is the latest test run. It is not the compliance
SOAP chart. Compliance Test does not write `state/compliance.json`.

## Where the file goes

The central directory is the workspace `state/` folder. The path is
the catalog row, written with built-in file tools as
`state/health.json` or `state/compliance.json`.

- One writer per file. Replace the file in full. Do not append a
  second chart beside it.
- `write_file` creates the directory. Do not `mkdir`. Do not invent
  a prefix, a UUID path, or a second tree (`runs/`, `risk/`, a root
  `compliance.json`, `health-board.md`).
- Built-in file tools are workspace-relative. Do not put
  `/workspace/` on those calls.
- `execute_command` sees the same files on the `file_explorer`
  directory beside `skills`. Pass that directory as `--workspace`.
  Do not `cd`. Do not pass the relative name `file_explorer`.
- Do not copy git, MCP bodies, running-configs, or ticket lists into
  `state/`. The chart cites evidence by path and key.

## What the parent is responsible for

The chart is the current belief about that domain, not a dump of the
visits.

Health Analyzer owns whether the network is healthy: which planes
are fresh, which vitals moved, which problems are still open, what
each problem reaches, and the next clinical step. It does not query
Splunk, Grafana, IOS-XE, or ServiceNow.

Compliance owns whether the estate is in a better compliance
position than the last same-lab chart: tested posture, device
checks, and framework coverage, kept as three separate scores. It
does not query NIST, call GitHub, run `test.yml`, author checks, or
change a device. A Dev result is proposal evidence. Say so when
`environment` is `dev`. Do not compare a lab with production.

Both parents read the specialist files already on disk, fold them
with their skill script, and then set the opinion. They do not
recompute the series in the reply.

## Envelope

Both files are Kind `state`. The five envelope fields are required:

| Field | Meaning |
|-------|---------|
| `updated_at` | When this chart was written, ISO-8601 |
| `source_agent` | The parent named above |
| `status` | Rollup of the chart, from the precedence in that skill |
| `headline` | One line a person can read. Health uses `assessment.opinion`. Compliance starts with the direction (`Improving:`, `Worsening:`, `Mixed:`, `Unchanged:`, or `Baseline:`) |
| `next_action` | The same string as `soap.plan` |

A reader that needs this chart blocks only when the file is missing,
`updated_at` is stale for that domain, or `status` is a failure that
schema treats as blocking. Quote `headline`. Do not paste the file
into chat.

Health freshness is 26 hours from each board's `last_collected_at`
(or the latest stamp `checked_at` when that field is absent).
Compliance evidence is stale after 24 hours. ServiceNow does not
vote on the health envelope status. The health vital planes are
`application`, `netflow`, `splunk`, and `iosxe`.

Health status, first match: `unknown`, `stale_chart`, `degraded`,
`partial`, `ok`.

Compliance status, first match: `unknown` (neither plane usable),
`stale_chart` (a material plane is stale or was just dispatched),
`degraded` (current testing has FAIL or ERROR), `partial` (a plane
is missing or unavailable, testing has SKIP, or framework coverage
has partial, gap, or unwired rows), `ok`. Remediated findings do
not change status.

## SOAP object

`soap` is required. All four strings are required and non-empty.
`additionalProperties` is false. Do not add a fifth SOAP field.

| Field | Write this | Do not write this |
|-------|------------|-------------------|
| `subjective` | Why this chart was written: the operator ask, or `Scheduled assess-now.` / `Scheduled refresh-then-assess.` | A copy of a nurse headline, a ticket body, or a control statement |
| `objective` | What the specialists measured this visit: coverage, freshness, the numbers and the flips | An instruction to go inspect a box, a raw log, or a guess |
| `assessment` | The same sentence as `assessment.opinion` | A second, different verdict |
| `plan` | The next owner and the task, or `none` | A configuration command, a SKU, a git diff, or a test plan |

`plan` names work. It does not do the work.

Health: `soap.plan` is the prose of `orders[0]` (`agent` plus the
task line from `workspace-handoff`), or `none` when there is no
order. `orders[]` is the structured list. Each order has `agent`,
`task`, `problem_ref`, and `dispatched`.

Compliance: `soap.plan` is one route.

- stale framework evidence → Compliance Intelligence
- stale test evidence → Compliance Test
- a missing control the operator selected → Compliance Author
- a proven test failure on a device and control → Network Ops
- nothing material → `none`

## How the file is produced

A question to the parent is not a chart write. Health Analyzer
**chat** uses built-in `read_file` on catalog rows
(`state/health.json`, the five boards, and the other `state/`
rows the ask names) and does not call `execute_command`. Paths are
workspace-relative, with no `/workspace/` prefix.

The parent does not hand-build the JSON. On **assess**, the skill
script folds the visits. The parent sets the opinion through a
second command.

Health, `skills/health-analyzer/scripts/assess_health.py`:

1. `assess` under `execution_type: standard`. The script reads the
   boards, the newest stamps, the prior chart, and
   `state/relationships.json` when it is present. It writes
   `state/health.json` with scores, series references, problems, and
   a placeholder opinion.
2. When the last stdout line has `needs_note`, `annotate` under
   `standard` fills `assessment`, `trend_analysis`, `soap`,
   `consult.impression`, and `problems[].hypothesis`. It does not
   recollect telemetry.

Compliance, `skills/compliance-analyzer/scripts/assess_chart.py`:

1. `assess --mode assess-now` or `--mode refresh-then-assess`. The
   script reads `compliance/metadata-intel.json`,
   `compliance/metadata-testing.json`, `compliance/coverage.json`,
   `compliance/intel.json`, and the prior `state/compliance.json`.
   It writes scores, the last-ten-visit series, flips, findings, and
   a factual plan.
2. When the last line has `needs_opinion`, `annotate` replaces
   `soap.assessment`, the trend narrative, and `soap.plan`. It
   leaves the scores alone. Do not run `assess` again after
   `annotate`.

Copy the script path Studio shows for the attached skill. Do not
retype it. The last stdout line is the result. A line above it from
the runtime is not the result. On failure, one line from stderr,
then stop. Do not build the chart by hand and do not write a helper
script into the workspace.

`assess-now` dispatches a stale specialist and does not wait, then
runs `assess` again with `--dispatched`. `refresh-then-assess`
waits only for planes that are both stale and material, then runs
`assess` again with no `--dispatched`. Record those dispatches on
the chart. Never refresh a plane the script called current.

## What else the chart must carry

Both charts require `keys`, `mode`, `analyzed_at`, `coverage`,
`freshness`, `consults`, `series`, `assessment`, `trend_analysis`,
`dispatched`, and `read`, plus `soap`.

`keys` is the deduplicated union of source-supported identities on
this chart. Each value matches `type:name` with no space after the
colon. Types are `device`, `interface`, `site`, `service`, `test`,
`control`, `incident`, `change`, and `application`. Use `site:` for
a location. Copy the name from inventory or from the evidence row.
Do not invent a device, and do not turn a recommendation id into a
key. `keys: []` only when the chart names no entity. Nested rows
keep their own `keys`. Health computes `keys` from `problems[].keys`
and `relations[]` on this chart, not from the prior file.

`read` lists the catalog paths this run actually opened. `series`
points at specialist history. Health series are references
(`series_ref` to the board). Do not copy the nurse's points onto
the chart. Compliance series are the last ten visits per plane,
testing kept per lab.

`assessment` is the structured verdict beside the one-line opinion:

- Health: `unhealthy`, `healthy`, `contradictions`, `opinion`
- Compliance: `noncompliant`, `compliant`, `gaps`, `contradictions`,
  `opinion`

`trend_analysis` answers whether this domain is getting better.
Health uses `narrative` and `flips`. Compliance uses `direction`
(`improving`, `worsening`, `mixed`, `unchanged`, or `first`), the
prior and current scores, and the same-lab FAIL/ERROR ↔ PASS flips.
A failure that now passes becomes a finding with status `remediated`
and stays on the compliance chart for 7 days.

### Health problems

`problems[]` is the carried list. Identity is the problem `id`.
Close a problem only when the board series shows the vital recovered
for two visits. Each open problem has `keys`, `symptom_refs`,
`evidence_refs`, `hypothesis`, and `impact`.

`impact` is `applications`, `services`, `hosts`, and `basis`, walked
from `state/relationships.json` (`depends_on`, `flows_to`,
`traverses`). Those names are not extra keys. A hypothesis says
where the fault must lie given the records. It does not name a cause
no stamp measured.

`relations[]` are edges this parent asserts, each with `evidence_ref`.
`orders[]` may be empty. `consults.<plane>` is this parent's
impression of that board, not a paste of the nurse headline.

### Compliance findings and scores

Three scores, each with prior and current:

- tested posture: verified tests over verified plus failing. SKIP and
  N/A are excluded and reported separately.
- device checks: per device row, so a partial fix moves this score
  without moving the per-test score.
- framework coverage: covered over covered plus partial plus gap plus
  unwired. Not-applicable controls are excluded.

`findings[]` carry `status` (`open`, `remediated`, `regressed`),
`first_seen`, `resolved_at`, and exact keys. `consults` cite the
latest Intel visit and the latest test visit per lab.

## Reply after the write

A Health Analyzer **chat** turn answers the question from the files
already on disk. It does not use the assess reply block and does
not claim `Wrote: state/health.json`.

The **assess** chat reply is the chart's summary, not a second
chart. No preamble, no tool narration, no raw JSON.

Health assess ends with `Next:` equal to `soap.plan` (the agent
and the task line, or `none`).

Compliance uses the fixed block in `agents/compliance-agent.md`:
`Result`, `Mode`, `Wrote: state/compliance.json`, `Dispatched`,
`Scores`, `Trend`, `Assessment`, `Why`, `Findings`, `Next`. `Next`
is the plan passed to `annotate`.

## Parents that write state and do not write SOAP

These files are the current record of that agent's job. They use
the envelope where the catalog says Kind `state`. They do not
contain a `soap` object. Do not add one, and do not create a
parallel SOAP file for them.

| Agent | File | What that file is |
|-------|------|-------------------|
| Network Ops | `state/network-ops.json` | The change in progress: mode, the health `problem_ref` when one matched, finding, prescription, blast radius, git, CI, PR |
| Network Ops | `state/recommendations.json` | Open configuration recommendations. The skill script rewrites it |
| Network Design | `state/design.json` | The design: assessment, hardware, software, configuration, compliance notes, timeline, warehouse |
| Modernization Analysis and Modernization Lifecycle | `state/lifecycle.json` | The estate table. Both may write it. Analysis owns assessment and plan. Lifecycle owns Cisco research |
| Relationship agent | `state/relationships.json` | Compiled edges. Not an opinion |
| Ops Network Sync | `state/network-sync.json` | Inventory sync result |
| Ops NetBox SoT | `state/netbox.json` | Infra source-of-truth summary |
| Ops ServiceNow | `state/servicenow.json` | Operator ticket summary |
| Compliance Test | `state/testing.json` | Latest suite run, not the attending chart |

Network Map and Application Map write derived HTML under `reports/`.
They do not write SOAP. Presentation writes the customer deck. It
does not write `state/`.

## Rules for an agent editing this contract

- The writer skill owns the schema and the example. Change
  `state/health.json` only in `skills/health-analyzer`. Change
  `state/compliance.json` only in `skills/compliance-analyzer`.
- Bump the prompt `version` and the `Version x.y.z.` line together,
  and record the number in `agents/VERSIONS.md`. Bump the skill
  `description` as `vX.Y.Z — ` in one sentence under 250 characters.
- If a new attending parent needs a chart, add one catalog row to
  `workspace-handoff`, one schema, and one example. Do not overload
  `state/health.json` or `state/compliance.json` with another domain.
- A plan may name the next agent and the task line. It may not
  contain the change that agent would make.
