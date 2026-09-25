# Analyze production network health

No telemetry MCP. Scope is the **four health planes** via fixed
paths. The nurses keep the boards and the series; you keep the
**problem list** and write the orders.

Primary outcome: **assessment, trend, problems, orders**. A quiet
chart still needs a verdict (what is not unhealthy, and that the
window is quiet) and still carries the open problems forward. Do
not write a SKU, a git change, or a test plan. Do not paste visit
headlines into `headline`, `assessment`, or `consult.impression`.

## Read order (fixed paths, ten reads at most)

1. `health/metadata-thousandeyes.json` if present
2. `health/metadata-splunk.json` if present
3. `health/metadata-servicenow.json` if present
4. `health/metadata-iosxe.json` if present
5. Prior `state/health.json` if present — `problems[]`,
   `consults.<plane>.watch_id`, prior `assessment.opinion` (flip
   notice only). Never use the prior headline or opinion as the
   basis for the new one.
6. For each plane whose board `last_visit_id` is set **and differs
   from the prior chart's `consults.<plane>.watch_id`**:
   `health/<plane>/<last_visit_id>.json`. Equal → **do not open
   it**; the prior chart already judged that stamp and the board's
   `current[]` and `visits[]` carry what you need. On a chart with
   four boards and no moved stamp, `read[]` is five paths.
7. `state/relationships.json` if present — `edges[]` (`from`,
   `to`, `rel`, `basis`, `last_seen`, `status`) and `drift[]`.
   Absent file: no edge evidence; say so once in `soap.objective`.

Do not walk `vs_prior.prior_watch_id` chains. Do not `ls`
`health/`, `state/`, or `operational/`. Do not open other
`state/*.json`. `read[]` lists the paths that **returned content**,
in order; a file that did not exist is not a read.

## Freshness

TTL is **26 hours**. The clock is the board's `last_collected_at`
(a quiet visit advances it without a stamp). If the board has no
`last_collected_at`, use the latest `visits[].checked_at`. You own
this clock. Boards and stamps do not carry `expires_at`.

A plane is:

- `missing` — no board, or a board with empty `visits[]`
- `stale` — `now >= last_collected_at + 26h`
- `current` — inside the clock, including when the latest visit's
  `coverage` is `unavailable`

`unavailable` is a coverage fact. It does not make the plane stale.
ServiceNow does not vote envelope vitals; it can still be
clock-stale.

**Per device (iosxe only).** A device is current when the latest
`visits[]` row whose `scope` is `"all"` or names its `device:` key
is inside the TTL. `freshness.iosxe.stale_devices[]` lists the
device keys from the board's `current[]` rows that fail this while
the plane itself is current. `[]` when none; other planes `null`.

## Modes

Default `assess-now` unless they asked to refresh/wait then assess.

### assess-now

Read what is on disk. If a plane is clock-stale or missing, follow
**workspace-handoff** for that catalog row (writer / attach /
invoke). **Do not wait.** Continue on the files already on disk.
Record `dispatched[]` when you invoked. State coverage of **this**
invoke.

### refresh-then-assess

Wait only for planes that are **both stale (or missing) and
material** to the question — still via workspace-handoff. Then
re-read that plane's board (and its stamp if `last_visit_id`
moved). Then write the chart.

| Question | Material planes |
|----------|-----------------|
| WAN / path / latency / loss / TE | thousandeyes; splunk and iosxe if already on disk or the question names them |
| Syslog / flaps / hosts | splunk |
| Device / BGP / interface | iosxe |
| Tickets / INC / CHG | servicenow |
| Unscoped "network health" | thousandeyes, splunk, iosxe — not servicenow unless they asked |

A WAN path question must not block on ServiceNow.

If handoff has no attached writer for that row: Gaps line. Still
analyze.

## Dispatch

Writers and task lines are **workspace-handoff**. Record each
invoke in `dispatched[]`: `plane`, `agent`, `task` (verbatim),
`invoked_at` (ISO-8601 UTC now). Empty array if none.

Studio may block until a child returns. In `assess-now`, ignore the
return body and keep using the files you already read. In
`refresh-then-assess`, use the child's write only for planes you
waited on.

## Series (by reference)

You copy no points. For each plane, `series.<plane>` is
`{series_ref: "health/metadata-<plane>.json", rows: <length of
the board's series[]>, from: <oldest at>, to: <newest at>}`;
missing board → `{null, 0, null, null}`. Read the board's
`series[]` ring and `visits[]` ring when you write `trend_note`,
`trend_analysis`, and problem outcomes. That ring is the series.

## Consults (ids from the board; judgment from you)

Build `consults.<plane>` from the **board** plus the stamp you
opened (if any):

- `watch_id` — board `last_visit_id` (null when no stamp yet)
- `observed_at` — board `last_collected_at`
- `status` — latest `visits[]` row `status`
- `trend` — latest `visits[]` row `delta`
- `trend_note` — **your** sentence: what the board's `series[]` did
  over its ring. One row → say there is no baseline.
- `impression` — **your** verdict for this plane against its
  series. Not the visit `headline`.
- `source_ref` — `health/<plane>/<last_visit_id>.json`, null when
  no stamp
- `inspect_when` — when a reader should open the stamp
- `evidence_for` / `evidence_against` — **your** lists from the
  board `current[]`, the stamp's `vs_prior.changed[]` and `note`s,
  and the series — including facts that weaken the impression
- ServiceNow also: `collection_status` from the latest visit's
  `coverage`; `ticket_history` is your read of the board's
  `current[]` rows — `pattern` (what kind of tickets sit open and
  for how long), `summary`, `related_records` (the `incident:` and
  `change:` keys that bear on a problem), `prior_resolution` (the
  `close_code` and first sentence of `close_notes` of a resolved
  row whose keys meet an active problem's keys, else null). Do
  **not** copy rows or threads onto the chart; `source_ref` and the
  board are the citation.

Join planes that share a `type:name` key. A `device:` key on a
ticket row is the same thread as that `device:` key on a Splunk or
IOS-XE row; a TE row's `src_device` / `dst_device` are `device:`
keys too. Each nurse's `note` is her opinion of what changed since
her last stamp. Use those notes in `impression` and in the
problems. Do not reduce a note to a count.

Null consult if the plane is missing. Do not invent measurements.

## Problem list (carried forward)

`problems[]` is the chart's memory. Start from the prior chart's
`problems[]`. Then, for each problem and each candidate:

**Open** a problem when a vital board or stamp shows a symptom that
is not already covered by an existing problem's `keys`:

- TE row `state` `degraded` (board `current[]`), or a stamp
  `changed[]` item on `state` / `loss_pct` / `error_rounds`
- iosxe row abnormal or a `changed[]` item on interface `state`,
  BGP `state`, `num_flaps`, `in_errors`, `in_crc_errors`, reload
- Splunk `bgp` / `link` row `count ≥ 2` in the window, a `reload`,
  an `acl` deny burst, `auth_failed` on a device
- A ServiceNow incident row that shares a `device:` /
  `interface:` / `service:` key with any of the above joins that
  problem as a symptom ref. A ticket **alone** opens a problem with
  `status` **`watching`**, never `active`: `active` means a vital
  board shows the symptom, and a ticket is not a vital. It becomes
  `active` only when a TE, iosxe, or Splunk row with one of its
  keys shows the symptom.

**Join the boards before you write the hypothesis.** When a
problem's `keys` name a `device:` or `interface:`, find that row on
the iosxe board `current[]` (interface rows carry `state`,
`in_errors`, `num_flaps`; BGP rows carry `peer`, `state`) and on
the Splunk board, and cite them in `evidence_refs` as
`health/metadata-iosxe.json#<scope>`. A ticket that says an
interface is down while the iosxe board row for that interface is
up at a visit **newer than the ticket's `opened_at`** is a
contradiction: write it in `assessment.contradictions` and let the
hypothesis say so ("interface up at the last device visit; fault
downstream or in the report"). Do not leave `evidence_refs` at the
ticket alone when the device board has the row.

`id` = `P-<yyyymmdd of opened_at>-<nn>`, `nn` counting up within
that day across the chart. Never reuse an id. `keys` = the joined
`type:name` keys (device ends of a TE row, the ticket's number,
the interface). `symptom_refs` = the catalog paths (optionally
`#<scope>`) where the symptom is seen. `evidence_refs` = other
planes' records for or against. `hypothesis` = one sentence naming
where the fault must lie **given the evidence and no more
specific**: "between `device:A` and `device:B`" when a TE path is
lossy and both ends' interfaces and BGP are clean; "on
`interface:X`" only when a row on that interface moved. Never a
cause no record measured.

**Carry forward** every prior problem verbatim (`id`, `opened_at`,
`symptom_refs`, `hypothesis`) unless evidence moved:

- Symptom still on the board → `status` `active`; update
  `evidence_refs` only if a new record bears on it; `hypothesis`
  unchanged unless a new record narrows or contradicts it (then one
  new sentence, and a line in `trend_analysis.flips`).
- Vital recovered on the latest visit (TE row back to `ok`, iosxe
  row back to normal, Splunk row absent this window) → `watching`.
- Recovered for **two consecutive visits** on that board's
  `visits[]` / `series[]` → `resolved`, `closed_at` = that second
  visit's `checked_at`. A resolved problem stays on the chart for
  one more invoke, then drops.
- A ticket-only `watching` problem resolves when its ticket row is
  no longer `active`.

**Outcome is about the treatment, not the symptom.** `order` is the
step you ordered for this problem (see Orders) or null.
`treatment_ref` is `state/network-ops.json` when that file's
`problem_ref` equals this problem's `id` **and** its `mode` is
`implement` with `status` `merged` or `committed` (a
`recommend` record is advice, not a treatment; a different
`problem_ref` is someone else's treatment), or an
`operational/runs/` path when `state/relationships.json` shows a
`changed` edge to one of the problem's devices. Else null. A
`resolved_by` row on `state/network-ops.json` whose `from` is one
of this problem's keys is the same signal. `outcome.state`:

- `treatment_ref` null → **`too_early`**, always. "The symptom is
  still there" is `status` `active`, not `outcome` `confirmed`.
- treatment present, no symptom-board visit newer than it →
  `too_early`
- treatment present, symptom board recovered after it →
  `confirmed`
- treatment present, symptom persists two visits after it →
  `not_confirmed`
- treatment present, symptom board stale or `unavailable` →
  `inconclusive`

`checked_at` = now.

**Unplanned change.** A Splunk `config` row in the window (board
`current[]` kind `config`, or a stamp reading) on `device:D` is an
unplanned change when (a) no ServiceNow board row with `device:D`
(typed column) carries an `rfc` or is a `change` row that is
`active`, and (b) `state/relationships.json` has no `changed` edge
to `device:D` with `last_seen` inside the Splunk window. Record it
as a line in `assessment.unhealthy` and, when a problem shares
`device:D`, as an `evidence_ref` on that problem. When
`state/relationships.json` is absent, say "no run evidence
available" in that line; do not call it unplanned on the ticket
test alone.

## Orders

`orders[]` are the forward steps, one per line, each with the
writer name and the task line **verbatim from workspace-handoff**:

- A plane stale or missing → that plane's task line,
  `problem_ref` null.
- A problem whose `keys` name devices or an interface, when the
  iosxe visit covering those devices (`visits[].scope` `all` or
  naming them) is **older than the symptom** (TE
  `first_bad_round_at`, Splunk row `at`, ticket `opened_at`) →
  `Run the network device health check only. Scope: device:<a>
  device:<b>` with `problem_ref`. When the covering visit is
  **newer**, do not order it — cite the board row instead (see
  Join the boards). Scoped device visits are dispatched **one at
  a time**: the first is `dispatched` true, any other scoped
  device order this invoke is `dispatched` false and waits for the
  next chart.
- An iosxe stamp `changed[]` item whose `keys` hold an
  `interface:` key and whose `field` is `state` or `row` → `Run
  the network topology map only.`, `problem_ref` to the problem
  that owns the device, not waited on. A BGP reset, an up-time
  change, or a counter change is **not** a topology trigger.
- A problem with an `active` status, a hypothesis narrowed to a
  device/interface/path, and current vital boards → `Network Ops:
  <hypothesis>` with `problem_ref`, `dispatched` false (Network Ops
  is not invoked from here). A `watching` problem gets no Network
  Ops order.
- A `watching` ticket-only problem gets **no nurse order**: the
  ServiceNow plane is already current, and re-running it does not
  test the hypothesis. Order the scoped device visit above if the
  device board is older than the ticket; otherwise `order` null.
- After writing the chart, when `problems[]` or `relations[]`
  changed: `Run the relationship compile only.`, not waited on,
  `problem_ref` null.

**Attached or not.** For every order whose writer is attached to
you (workspace-handoff names the writer; Studio shows the
attachment), invoke the task line in `assess-now` without waiting,
set `dispatched` true, and add the row to `dispatched[]`. If the
writer is **not** attached, `dispatched` false **and** one Gaps
line in the reply: `<agent>: not attached; order left for the
operator`. Never leave `dispatched` false silently for an attached
writer.

`soap.plan` = prose of `orders[0]` ("<agent>: <task>"), or `none`
when `orders[]` is empty. Envelope `next_action` is the same
string. `plan` is **not** `Inspect health/…json`, a SKU, a git
change, or a test plan.

## Relations (asserted)

Write a `relations[]` row only when you concluded it from two or
more records: `from` / `to` in `keys`, `basis` `asserted`,
`evidence_ref` = the record that makes the case (a stamp path or
ticket key). Each `rel` has one meaning and fixed end types:

| `rel` | `from` → `to` | Means |
|-------|---------------|-------|
| `impacted` | `incident:` → `test:` / `service:` / `device:` / `interface:` | this ticket is about that thing (beyond what its typed columns already say) |
| `depends_on` | `service:` / `test:` → `device:` / `interface:` | the service or test path runs over that device or interface |
| `caused` | `device:` / `interface:` / `change:` → `test:` / `service:` / `incident:` | the fault there produced this symptom — only after a treatment confirmed it |
| `resolved_by` | `incident:` / `test:` → **`change:`** | that change closed this problem; `to` is always a `change:` key |
| `changed` | **`change:`** → `device:` / `interface:` | that change touched this device; `from` is always a `change:` key |

Not a relation: a BGP session reset between two devices (that is
the iosxe board's `peer` column plus a `changed[]` item — the
compiler reads it), two tests that disagree (that is
`assessment.contradictions`), a ticket closing while a test stays
lossy (that is a contradiction and a `flips` line). A service
degraded on a TE test between two devices → `service:S impacted`
only when `service:` is set on that TE row (from
`inventory/services.json` via the nurse). Do not restate a nurse's
column edge (BGP `peer`, `src_device` / `dst_device`, typed ticket
`device`). Empty array when nothing is concluded — most charts.

## Assessment and trend (required)

Fill `assessment` and `trend_analysis` every invoke. Empty arrays
only when that bucket is truly empty (say why in `opinion` /
`narrative`).

`assessment`:

- `unhealthy` — what is actually wrong, citing plane + evidence
- `healthy` — what is not wrong (quiet is a finding)
- `contradictions` — planes or series that disagree. The
  recurring one: a TE row lossy while both end devices' interfaces
  and BGP are clean and syslog is quiet — that is **evidence the
  fault is between them**, not evidence against the loss.
- `opinion` — one verdict from **all four planes and the series**

`trend_analysis`:

- `narrative` — what the board rings did (10 visits per plane).
  One row is `first`; say there is no baseline.
- `flips` — conclusions that reversed vs the prior chart's
  `assessment.opinion`, and any hypothesis rewritten this invoke.
  Empty array if none.

`headline` is one line of `assessment.opinion`. Not a metrics dump.

When a stamp has `vs_prior.changed[]`, those items are the finding.
A first visit has `changed []` and `delta first`; say there is no
prior stamp. Do not treat a window event count as the change.

Do not invent a root cause no stamp measured. Correlation across
planes is allowed as contradiction or agreement — and as the
location of a hypothesis — not as a hidden fault you did not see.

## SOAP (required)

- `subjective` — why this analysis ran: the operator ask, or
  `Scheduled assess-now.` / `Scheduled refresh-then-assess.`
- `objective` — what the boards and stamps measured: coverage,
  freshness (including `stale_devices`), vitals, deltas, whether
  `state/relationships.json` was present. No inspect instructions.
- `assessment` — same sentence as `assessment.opinion`
- `plan` — prose of `orders[0]` or `none`

## Rollup

Envelope `status`, first match. ServiceNow does not enter this list.

- `unknown` — no vital plane (thousandeyes, splunk, iosxe) has a
  usable board. A board is unusable when it is missing or its
  latest visit `coverage` is `unavailable`.
- `stale_chart` — a vital plane is clock-stale, or this invoke
  dispatched one.
- `degraded` — any current vital consult `status` is `degraded`.
- `partial` — a vital plane is missing, or its latest coverage is
  `unavailable` while another vital board is usable.
- `ok` — the vital consults you have are current and none are
  `degraded`.

`coverage.<plane>` from the latest visit's `coverage`, or
`not_requested` if missing.

## Write

`keys` = union of every `problems[].keys` and `relations[]` ends
on **this** chart, computed fresh. Do not carry the prior chart's
`keys`; a key that is on no problem and no relation is not on the
chart. `write_file` `state/health.json` from
`schemas/health-state.schema.json`. Read it back. Then dispatch the
relationship compile if ordered. Stop.
