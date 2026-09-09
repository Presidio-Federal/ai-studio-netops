# Analyze production network health

No telemetry MCP. Scope is the **four health planes** via fixed
paths.

Primary outcome: **observation rollup**. A current, quiet chart is
still a chart with numbers. Do not write recommendations.

## Read order (fixed paths)

1. `health/metadata-thousandeyes.json` if present — if
   `thousandeyes.last_visit_id` is set, `health/thousandeyes/<id>.json`
2. `health/metadata-splunk.json` if present — if
   `splunk.last_visit_id` is set, `health/splunk/<id>.json`
3. `health/metadata-servicenow.json` if present — if
   `servicenow.last_visit_id` is set, `health/servicenow/<id>.json`
4. Prior `state/health.json` if present — `series` watermarks, prior
   `headline` (flip notice only), and `consults.iosxe.source_ref`
   for the iosxe stamp. Never use the prior headline as the basis
   for the new one. Do not list `health/iosxe/`.
5. If `consults.iosxe.source_ref` names a stamp, `read_file` that
   path (strip a leading `workspace/` or `/workspace/`).

Do not `ls` `health/` or `state/`. Record paths opened in `read[]`.

Do not read other `state/*.json`.

## Freshness

TTL is **26 hours** from `checked_at` on that latest observation.
You own this clock. Visit files do not stamp `expires_at`.

A plane is:

- `missing` — no latest stamp (no `last_visit_id` / no iosxe
  `source_ref`)
- `stale` — stamp present and `now >= checked_at + 26h`, or
  `coverage.state` is `unavailable`
- `current` — otherwise

ServiceNow does not vote envelope vitals. It can still be stale.

## Modes

Default `assess-now` unless they asked to refresh/wait then assess.

### assess-now

Read what is on disk. If a plane is stale or missing, follow
**workspace-handoff** for that catalog row (writer / attach /
invoke). **Do not wait.** Continue on the files already on disk.
Record `dispatched[]` when you invoked. State coverage of **this**
invoke (which planes you actually had).

### refresh-then-assess

Wait only for planes that are **both stale (or missing) and
material** to the question — still via workspace-handoff. Then
re-read that plane’s metadata `last_visit_id` (iosxe: the
returned `Wrote:` stamp path only — do not list). Then write the
chart.

| Question | Material planes |
|----------|-----------------|
| WAN / path / latency / loss / TE | thousandeyes; splunk and iosxe if already on disk or the question names them |
| Syslog / flaps / hosts | splunk |
| Device / BGP / interface | iosxe |
| Tickets / INC / CHG | servicenow |
| Unscoped “network health” | thousandeyes, splunk, iosxe — not servicenow unless they asked |

A WAN path question must not block on ServiceNow.

If handoff has no attached writer for that row: Gaps line. Still
analyze.

## Dispatch

Do not name writers here. Writers and invoke lines for this
workspace are **workspace-handoff**.

Record each invoke in `dispatched[]`: `plane`, `agent` (from
handoff), `invoked_at` (ISO-8601 UTC now). Empty array if none.

Studio may block until a child returns. If it does in `assess-now`,
ignore the return body and keep using the files you already read.
In `refresh-then-assess`, use the child’s write only for planes you
waited on.

## Series fold (mechanical)

Keep numbers as memory. Do not edit the prior narrative.

For each plane (`thousandeyes`, `splunk`, `iosxe`, `servicenow`):

- `window` is 10.
- Latest stamp id: metadata `last_visit_id`, or iosxe `source_ref`
  filename / `watch_id`.
- If that id is newer than `series.<plane>.watermark`, `read_file`
  the stamp (if not already open). Copy each `metrics[]` row
  **verbatim** into `points` (include `at` and `scope`). Append.
  Drop oldest when over 10. Set `watermark` to that id.
- Else: leave `points` unchanged (no-op).
- Missing latest stamp: keep prior series for that plane, or empty
  `points` and `watermark` null.

## Consults (derived)

Visit files do not include `consult` objects. Build
`consults.<plane>` from the **latest observation** of that plane:

- `watch_id` — observation `watch_id`
- `observed_at` — `checked_at`
- `status` — observation `status`
- `impression` — `headline`
- `source_ref` — `health/<source>/<watch_id>.json`
- `inspect_when` — `coverage.detail` if present, else `Open the observation for samples.`
- `evidence_for` — `summary` as one item if present, else `headline`
- `evidence_against` — empty array
- `trend` — `first` if no prior `consults.<plane>` on the chart;
  else `worse` / `better` / `unchanged` from prior consult `status`
  (`degraded` > `unknown` > `ok`)
- ServiceNow also: `collection_status` from `coverage.state`
  (`complete` / `partial` / `unavailable`); `ticket_history.summary`
  from `headline`; `pattern` from `summary` or `headline`;
  `related_records` from `incidents[]` / `changes[]` / `recent[]`
  `number` (cap 10); `prior_resolution` null

Null if there is no latest stamp. Do not invent measurements.

## Rollup

Envelope `status`:

- Worst of thousandeyes, splunk, iosxe when that consult exists and
  coverage is `complete` or `partial` (`degraded` > `unknown` >
  `ok`).
- ServiceNow does not vote.
- `stale_chart` if you dispatched or a **vital** plane you needed
  was stale.
- `partial` if the chart is readable but a vital plane is missing
  or `not_requested`.
- `unknown` if no vital observation is usable.
- `ok` only if vital consults you have are current and none are
  degraded.

`coverage.<plane>` from that observation’s `coverage.state`, or
`not_requested` if missing.

`headline`: regenerate from `series` every invoke. Observation
only. Example: `p95 latency path-a down 40% over 14 days.`
No causality, no attribution, no recommendations. If the prior
headline’s conclusion flipped, you may note that in one clause
(“was degrading, now stable”) — still from the numbers, not from
the old sentence as input.

`next_action` is usually `none`.

## Write

`write_file` `state/health.json` from
`schemas/health-state.schema.json`. Read it back. Stop.
