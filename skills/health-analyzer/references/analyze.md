# Analyze production network health

No telemetry MCP. Scope is the **four health planes** via fixed
paths.

Primary outcome: **assessment plus trend**. A current, quiet chart
still needs a verdict (what is not unhealthy, and that the window
is quiet). Do not write recommendations. Do not paste visit
headlines into `headline`, `assessment`, or `consult.impression`.

## Read order (fixed paths)

1. `health/metadata-thousandeyes.json` if present — if
   `thousandeyes.last_visit_id` is set, `health/thousandeyes/<id>.json`
2. `health/metadata-splunk.json` if present — if
   `splunk.last_visit_id` is set, `health/splunk/<id>.json`
3. `health/metadata-servicenow.json` if present — if
   `servicenow.last_visit_id` is set, `health/servicenow/<id>.json`
4. Prior `state/health.json` if present — `series` watermarks, prior
   `assessment.opinion` (flip notice only), and
   `consults.iosxe.source_ref` for the iosxe stamp. Never use the
   prior headline or opinion as the basis for the new one. Do not
   list `health/iosxe/`.
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

Keep numbers as memory. Do not edit prior `points`.

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

Fold first. Then synthesize from the folded `points` plus the
latest stamps. Do not skip synthesis because the fold was a no-op.

## Consults (ids from the visit; judgment from you)

Visit files do not include `consult` objects. Build
`consults.<plane>` from the **latest observation** of that plane
plus **your** read of that plane’s series:

- `watch_id` — observation `watch_id`
- `observed_at` — `checked_at`
- `status` — observation `status` (the collector’s plane status)
- `impression` — **your** verdict for this plane against its
  series. Not the visit `headline`.
- `trend` — `first` if no prior `consults.<plane>` on the chart;
  else `worse` / `better` / `unchanged` from prior consult `status`
  (`degraded` > `unknown` > `ok`)
- `trend_note` — **your** sentence: what this plane’s series did
  over the window. `first` window → say so.
- `source_ref` — `health/<source>/<watch_id>.json`
- `inspect_when` — when a reader should open the stamp
- `evidence_for` / `evidence_against` — **your** lists from this
  visit and series, including facts that weaken the impression
- ServiceNow also: `collection_status` from `coverage.state`
  (`complete` / `partial` / `unavailable`); `ticket_history` is
  **your** read of in-scope tickets (pattern / summary), not a
  paste of the visit headline; `related_records` from
  `incidents[]` / `changes[]` / `recent[]` `number` (cap 10);
  `prior_resolution` if the stamps say so, else null

Null if there is no latest stamp. Do not invent measurements.

## Assessment and trend (required)

Fill `assessment` and `trend_analysis` every invoke. Empty arrays
only when that bucket is truly empty (say why in `opinion` /
`narrative`).

`assessment`:

- `unhealthy` — what is actually wrong, citing plane + evidence
- `healthy` — what is not wrong (quiet is a finding)
- `contradictions` — planes or series that disagree (path down,
  boxes quiet; tickets open, vitals ok)
- `opinion` — one verdict from **all four planes and the series**

`trend_analysis`:

- `narrative` — what changed over the window (10 visits per plane).
  One point is `first`; say there is no baseline.
- `flips` — conclusions that reversed vs the prior chart’s
  `assessment.opinion` (e.g. `was path-degraded, now stable`).
  Empty array if none. Do not reuse the old sentence as input.

`headline` is one line of `assessment.opinion`. Not a metrics dump.

Do not invent a root cause no stamp measured. Correlation across
planes is allowed as contradiction or agreement — not as a hidden
fault you did not see.

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

`next_action` is an inspect pointer to a stamp or `none`. Not a
SKU. Not a ticket. Not a work queue.

## Write

`write_file` `state/health.json` from
`schemas/health-state.schema.json`. Read it back. Stop.
