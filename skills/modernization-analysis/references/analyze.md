# Analyze estate — Modernization Analysis

Keep `state/lifecycle.json` the most accurate picture of what
we have. Ingest and rank confidence every run. When they want
a plan: record where they want to go, then write **assessment
plus cost and timelines** from lifecycle data already on disk,
and `lifecycle/roadmap.md`.

No Cisco / CCW / NVD / IOS-XE / Splunk / TE / ServiceNow MCP.
Do not invent EoX dates, list prices, hardware, software, or
objectives. **Never copy hostnames or PIDs from the example
JSON.** Fill from workspace evidence (`references/evidence.md`).

`headline`, `assessment.opinion`, and `plan.opinion` are **your**
verdict. Do not paste a single row summary as the plan.

## Always first

`read_file` `state/lifecycle.json`. Missing: create from evidence
this turn. Present: merge; stamp `updated_at`. Never wipe research
fields Lifecycle already filled. Never wipe `guidance.answers`
except to append what they said this turn. Never wipe
`recommendations[]` unless this is a plan invoke that replaces
them. Copy through prior `assessment` / `plan` until you replace
them this turn.

Then `inventory/infra-sot.json` if present. Then
`inventory/prod.json` if needed. Do not `ls` `lifecycle/` or
`inventory/`.

## Identity (every run)

Follow `references/evidence.md`. Group by evidence `pid`, not by
hostname. Copy through prior `end_of_*`, costs, `psirts`,
`vulnerabilities`, `expires_at`, `research`,
`recommended_replacement`, `selected_replacement`,
`selected_replacement_source`, `replacement_family`,
`replacement_candidates`, `replacement_ask`,
`recommended_software`, `guidance`, `roadmap_ref`.

New product group: research `eox`/`psirt`/`nvd` `missing`;
`software` `skipped` if `software_versions` empty else `missing`;
`ccw` `skipped`; other research fields `[]` / null.

Recount `coverage`. `source_agent` `modernization-analysis`.
`dispatched` this turn only (empty array if none).
Estate-only run: keep existing `recommendations[]` (or `[]`).

**Confidence** (write on `guidance` every run):

- `identity_confidence` — worst `items[].source.reliability`
  (`low` < `medium` < `high`). No items: `unknown`.
- `research_confidence` — `stale` if any row needs Lifecycle;
  else `unknown` if research never ran; else `high` / `medium`
  / `low` from how complete the vendor columns are.
- `understood` — a few sentences of what this estate actually
  shows (counts, reliability, unknown pids, EoX already
  filled). Not a canned slogan.

Envelope `status`: `stale` if any row needs Lifecycle
(`research.eox` `missing`, or `now >= expires_at`, or
`software_versions` present and `research.software` `missing`,
or `selected_replacement` set and `list_cost_per_unit` null).
Empty hardware EoX with `research.eox` `unavailable` is not
stale by itself. `partial` if identity exists but objectives or
research are missing. `ok` if unexpired research is done and
objectives are `stated`. `unknown` if there is no evidence.

## Dispatch

If any row needs Lifecycle (including a new
`selected_replacement` with no price), follow
**workspace-handoff** for that catalog row. Do not wait. Record
`dispatched[]`. If no attached writer: Gaps.

## Where they want to go

A modernize / plan / roadmap / objectives invoke, or a reply to
`guidance.open_asks`, is the interview.

1. Write `guidance` (confidence + `understood`) this turn.
2. If they stated objectives or named a replacement SKU this
   turn: append the words onto `guidance.answers`. When they
   **named a SKU**, write it on that row as
   `selected_replacement` and `selected_replacement_source`
   `operator`. Do not write it to `recommended_replacement`.
   Do not write `lifecycle/items/`. Set
   `objectives_status` `stated` (or `partial` if they still
   left a hole). Refresh `open_asks` to only what is still
   unanswered. If a row now has `selected_replacement` and no
   price, dispatch via workspace-handoff (no wait).
3. If `objectives_status` is still `missing` (or they asked
   for a plan with no answers yet), **or** any row has
   `replacement_ask` / family candidates and no
   `selected_replacement`: derive **1–5** `open_asks` from
   **this** estate. Each ask is **why, then the choice**.
   Prefer the row’s `replacement_ask` when it already has a
   why. Status `partial`. Do **not** write
   `lifecycle/roadmap.md`. `plan.status` is `asking`. Ask in
   the reply (drop the tight block): a short “I understand …”,
   then only those asks. Do not guess a SKU.

## How to ask (plain language)

Every `open_asks` line and every chat question must include
**why this matters on this estate**. Never dump a SKU list
alone. Never use planner jargon without a translation.

Forbidden as the ask (unless you also say what it means in
the same breath): disposition, retain/upgrade, replatform,
validate first, service owners, change-window, downtime
limits, horizon.

Use these shapes instead:

| Situation | Ask like this |
|-----------|----------------|
| Cisco named a **family**, not one part | Why: Cisco will not pick a firewall/AP/WLC SKU without size (throughput, AP count, appliance vs cloud). Then: name one candidate **or** give the size number they already understand. |
| Verbal / spoken list vs inventory | Why: those rows are a spoken demo list, not boxes we proved. Then: keep them in this plan, or hold them until we verify. |
| Virtual / CML `node_definition` on **this** row, stopped or shell-only | Why: that row is a **lab image**, not hardware you buy. Then: treat as lab only (no purchase), or drop it from the buy list. Do **not** ask “replatform vs retire.” |
| Hardware already past or near last-support | Why: Cisco stops support on **that date** — after that, no software fixes. Then: replace this year, or accept the risk. |
| Date like software-support end | Why: that date is when Cisco stops software support for this train. Then: is it a hard deadline or a target. |
| Money / date | Why: we cannot sequence buys without a ceiling or a “done by” date. Then: budget ballpark and done-by, or “no cap / no date.” |
| Who / where / outage | Only if they already mentioned sites or a change process. Why: so we do not schedule a cutover that hits the wrong building or an unlimited outage. Then: who cares, which site, how long can it be down. Skip this if they have not talked about it. |

Family-SKU ask: fill only from **that row** (`pid`,
`replacement_family`, `replacement_candidates`,
`replacement_ask`, bulletin size metric). Never copy a PID,
family, or Gbps figure from this file.

4. Estate-only “what do we own”: still write confidence on
   `guidance` and `assessment`. `plan.status` is `none`.
   Do not force the interview. `open_asks` may stay as they
   were.

## Assessment and plan (required every write)

Fill `assessment` every invoke.

- `must_move` — rows past or near last-support, or they said
  replace now (cite pid + date or answer)
- `can_wait` — research complete, dates far, or lab-only
- `contradictions` — low-reliability identity vs SoT; EoX vs
  a quiet health chart; selected SKU with no price
- `opinion` — one verdict from the estate + confidence

Fill `plan` every invoke.

- Estate-only or still asking: `status` `none` or `asking`;
  `timeline` `[]`; `cost` zeros/nulls; `opinion` says why
  there is no sequenced plan yet
- Plan invoke after answers: `status` `ready` (or `draft` if
  cost or dates are incomplete). Roll `cost` only from
  `list_cost_per_unit` / `total_list_cost` already on rows
  (selected SKU priced, else Cisco recommended). Null stays
  null — do not invent a list price. `unpriced_qty` is
  quantity still missing cost. `timeline[]` is order / stage /
  deploy / schedule / cutover from Cisco dates + their
  answers. `opinion` is the sequenced verdict
- `read_file` `state/health.json` if present. Use bottlenecks
  already written. Missing health is optional

`headline` is one line of `assessment.opinion` (estate-only)
or `plan.opinion` (plan invoke).

Also write `recommendations[]` (cap 10) on a plan invoke from
the same reasoning. Optional `goals[]`. `evidence_refs` are
workspace paths.

Write `lifecycle/roadmap.md` only when `guidance.answers` is
non-empty and they asked for a plan / roadmap. Follow
`references/roadmap.md`. Set `roadmap_ref`
`lifecycle/roadmap.md`.

Do not invent a sequence that Cisco dates and their answers do
not support.

## Not a second JSON plan file

Do not write `state/modernization.json`. Headline,
`next_action`, `guidance`, `assessment`, `plan`,
`recommendations[]`, and `lifecycle/roadmap.md` **are** the
plan.
