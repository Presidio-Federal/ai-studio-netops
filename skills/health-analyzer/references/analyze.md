# Analyze production network health

No telemetry MCP. Scope is the **four health planes** via fixed
paths.

Primary outcome: **assessment plus trend**. A current, quiet chart
still needs a verdict (what is not unhealthy, and that the window
is quiet). Do not write a SKU, a git change, or a test plan. Do not paste visit
headlines into `headline`, `assessment`, or `consult.impression`.

## Read order (fixed paths)

1. `health/metadata-thousandeyes.json` if present — if
   `thousandeyes.last_visit_id` is set, `health/thousandeyes/<id>.json`
2. `health/metadata-splunk.json` if present — if
   `splunk.last_visit_id` is set, `health/splunk/<id>.json`
3. `health/metadata-servicenow.json` if present — if
   `servicenow.last_visit_id` is set, `health/servicenow/<id>.json`
4. `health/metadata-iosxe.json` if present — if
   `iosxe.last_visit_id` is set, `health/iosxe/<id>.json`
5. Prior `state/health.json` if present — `series` watermarks and
   prior `assessment.opinion` (flip notice only). Never use the
   prior headline or opinion as the basis for the new one. Do not
   list `health/iosxe/`. If iosxe metadata has no `last_visit_id`
   and `consults.iosxe.source_ref` names a stamp, `read_file` that
   path (strip a leading `workspace/` or `/workspace/`).

Do not `ls` `health/` or `state/`. Record paths opened in `read[]`.

Do not read other `state/*.json`.

## Freshness

TTL is **26 hours** from `checked_at` on that latest observation.
You own this clock. Visit files do not stamp `expires_at`.

A plane is:

- `missing` — no latest stamp (no metadata `last_visit_id`, and
  no iosxe `source_ref` when iosxe metadata is absent)
- `stale` — stamp present and `now >= checked_at + 26h`
- `current` — stamp present and inside the 26h clock, including
  when `coverage.state` is `unavailable`

`unavailable` stays on `coverage`. It does not make the plane
stale. Do not dispatch a plane whose latest stamp is inside the
TTL. ServiceNow does not vote envelope vitals. It can still be
clock-stale.

## Modes

Default `assess-now` unless they asked to refresh/wait then assess.

### assess-now

Read what is on disk. If a plane is clock-stale or missing, follow
**workspace-handoff** for that catalog row (writer / attach /
invoke). A stamp inside 26h is not dispatched, even when coverage
is `unavailable`. **Do not wait.** Continue on the files already
on disk.
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

Keep numbers as memory. Do not edit prior `points`. Do not list
`health/`.

For each plane (`thousandeyes`, `splunk`, `iosxe`, `servicenow`):

- `window` is 10.
- Latest stamp id: that plane’s metadata `last_visit_id`. IOS-XE
  with no `last_visit_id`: `consults.iosxe.source_ref` filename /
  `watch_id`.
- Missing latest stamp: keep prior series for that plane, or empty
  `points` and `watermark` null.
- If that id is not newer than `series.<plane>.watermark`: leave
  `points` unchanged (no-op).
- Otherwise walk the stamp chain, newest first. `read_file`
  `health/<plane>/<id>.json` (iosxe: the `source_ref` path). Then
  follow that file's `vs_prior.prior_watch_id` to the previous
  stamp. Stop when `prior_watch_id` is null, equals `watermark`,
  the file is missing, or you have 10 stamps. Do not list the
  directory to fill a hole.
- Reverse that list so the oldest unseen stamp is first. For each,
  copy `metrics[]` **verbatim** into `points` (include `at` and
  `scope`). Append. Drop oldest `points` when over 10. Set
  `watermark` to the newest id you actually read.

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
- `trend` — the latest stamp’s `vs_prior.delta` when that object
  is present (`first`, `unchanged`, `worse`, `better`). A plane
  can stay `ok` while a reading moves; `delta` `worse` still
  applies. If the stamp has no `vs_prior`: `first` when this chart
  has no prior consult for the plane, otherwise `worse` /
  `better` / `unchanged` from the prior consult `status`
  (`degraded` > `unknown` > `ok`)
- `trend_note` — **your** sentence: what this plane’s series did
  over the window. `first` window → say so.
- `source_ref` — `health/<source>/<watch_id>.json`
- `inspect_when` — when a reader should open the stamp
- `evidence_for` / `evidence_against` — **your** lists from this
  visit and series, including facts that weaken the impression
- ServiceNow also: `collection_status` from `coverage.state`
  (`complete` / `partial` / `unavailable`); copy the stamp's
  `threads` onto this consult. `ticket_history.summary` is your
  read of those notes. `related_records` are the `incident:` and
  `change:` keys from `threads`. `prior_resolution` if a thread
  says the ticket closed, else null
- Join planes that share a `type:name` key. A `device:` key on a
  ServiceNow thread is the same thread as that `device:` key on a
  Splunk or IOS-XE row.
- Each nurse's `note` is her opinion of what changed since her
  last stamp. Use those notes in `consult.impression` and in SOAP.
  Do not reduce a note to a count.

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

When a latest stamp has `vs_prior`, use `changed` as the finding.
IOS-XE `readings` and Splunk `readings` are the facts that produced
that diff. A first visit has `changed` [] and `delta` `first`; say
there is no prior stamp. Do not treat a window event count as the
change. An old stamp with no `vs_prior` uses the status fallback
in `trend` above.

Do not invent a root cause no stamp measured. Correlation across
planes is allowed as contradiction or agreement — not as a hidden
fault you did not see.

## SOAP (required)

Fill `soap` every invoke. Envelope `next_action` **is** `soap.plan`
(same string).

- `subjective` — why this analysis ran: the operator ask, or
  `Scheduled assess-now.` / `Scheduled refresh-then-assess.`
- `objective` — what the lab slips and series measured: coverage,
  freshness, vitals, `vs_prior` deltas. Stamp paths stay on
  `consults.*.source_ref`. Do not write inspect instructions here.
- `assessment` — same sentence as `assessment.opinion`
- `plan` — **one** of:
  - another named nurse visit (`Run the network device health
    check only.` / Splunk / ThousandEyes / ServiceNow) when that
    plane is stale, missing, or the finding needs that specialty
  - `Network Ops: …` or `Network Design: …` when the chart is
    enough for a referral (path/config, not a down box)
  - `none` when no further clinical step is warranted

`plan` is **not** `Inspect health/…json`. That stamp is already
the citation. `plan` is **not** a SKU, git change, or test plan.
Treatment and test live on Ops / Design / Compliance Test.

## Rollup

Envelope `status`, first match. ServiceNow does not enter this list.

- `unknown` — no vital plane (thousandeyes, splunk, iosxe) has a
  usable slip. A slip is unusable when it is absent or
  `coverage.state` is `unavailable`.
- `stale_chart` — a vital plane is clock-stale, or this invoke
  dispatched one.
- `degraded` — any current vital consult is `degraded`.
- `partial` — a vital plane is missing or `not_requested`, or its
  latest coverage is `unavailable` while another vital slip is
  usable.
- `ok` — the vital consults you have are current and none are
  `degraded`.

`coverage.<plane>` from that observation’s `coverage.state`, or
`not_requested` if missing.

`next_action` is `soap.plan`. Not an inspect path. Not a SKU. Not
a ticket. Not a work queue.

## Write

`write_file` `state/health.json` from
`schemas/health-state.schema.json`. Read it back. Stop.
