# Health Agents — the patient chart

The shared workspace is the chart. Nurses collect **one** telemetry
source per conversation and write a **lab slip** (what they measured,
vs the last visit of that source). Health Analyzer is the attending:
it reads those slips and writes **SOAP** on `state/health.json`.
Network Ops and Network Design start from that chart — not from four
chat recaps.

![Building the Patient Chart](health-patient-chart.svg)

## Background

The model comes from **continuity of patient care**. A hospital does
not ask every clinician to re-interview the patient and re-run every
lab. Each encounter is a specialty visit. The specialist opens the
chart, does their work, writes a note, and hands off. The next
person — night shift, attending, or another service — reads the
record. They do not reconstruct the stay from memory or from four
separate recaps.

Treat the production network the same way.

| Hospital | This fleet |
|----------|------------|
| Medical record | Studio workspace |
| Specialty visit (one chat) | One telemetry source |
| Lab slip (Objective) | Visit stamp under `health/<source>/` |
| Wristband / known ids | Plane metadata (`health/metadata-*.json`) |
| Attending SOAP | `state/health.json` |
| Vitals expire | Freshness window (26 hours from `checked_at`) |
| Envelope | `status`, `headline`, `next_action` (`soap.plan`) |
| Next service on the floor | Network Ops / Network Design |

**SOAP** (Subjective / Objective / Assessment / Plan) is the
attending note on `state/health.json`. Nurses do not write SOAP.
They write Objective only: vitals (`metrics`), coverage, and
`vs_prior`. **Plan** is a forward clinical step: another named
nurse visit, refer Network Ops or Network Design, or `none`. It is
not “inspect the stamp the Analyzer already read.” Treatment and
test live on Ops / Design / Compliance Test.

A Splunk visit is labs. A ThousandEyes visit is imaging. An IOS-XE
visit is examining the patient. ServiceNow is the prior-admission
history. Mixing those in one conversation is one clinician doing
everyone else’s job — and it destroys the record for the next reader.

## What this solves

**Standardized prompts and skills.** Every health agent is the same
loop: check chart, get data, update chart, summarize. Domain detail
(SPL, test ids, YANG, ticket marker) stays in the skill. The prompt
stays identity plus that loop. Each agent owns one specialty and can
run unattended.

**Small chats, better accuracy.** Studio starts a **new conversation**
on every invoke. That is a feature: the nurse does not drag four other
planes, last week’s recap, or another agent’s prompt into context.
Initial tokens stay small. The chart on disk is the memory. Accuracy
goes up because the model is judging one source it actually queried,
not a blended story it was told.

**No telephone recap.** The next agent reads files, not the previous
chat. Four recaps of the same incident drift; one chart does not.

**One writer per note.** Nurses never write `state/`. Analyzer never
collects and never overwrites a visit stamp. Stamps are append-only
(keep ten). Concurrent visits cannot clobber each other.

**Vitals expire; silence is not health.** A missing log is not a down
device. Correlation across planes is not root cause. ServiceNow does
not vote on envelope status. “No critical errors” is one fact — the
visit still records volume, hosts, and coverage for **that** source.

**Executors vs attending.** Nurses are MiniMax-shaped: named tools,
named paths, get the data, write a lab slip. Analyzer spends tokens on
synthesis (`soap`, `assessment`, `trend_analysis`, each
`consult.impression`). Downstream agents implement; they do not
re-pull Splunk because the chart already said what syslog showed.

## The visit loop

```text
1. Check chart   → metadata + last stamp for this plane (Analyzer: all four + prior state/health.json)
2. Get data      → one source (Analyzer: none — collectors already measured)
3. Update chart  → append lab slip; metadata if ids/watermark/last_visit_id changed
                   Analyzer replaces state/health.json (SOAP)
4. Summarize     → tight reply with the path; do not paste the note
```

Live lookup ids and the Splunk watermark live in metadata, not in the
prompt. IOS-XE PAT lives on `inventory/prod.json` — there is no
`health/metadata-iosxe.json`. Empty, 0 rows, or a tool error is a
failed query, not a healthy network.

## Who writes what

| Role | Hospital | Agent | Writes |
|------|----------|-------|--------|
| Path / syslog nurse | Imaging / labs | Health Monitor | Named Splunk **or** ThousandEyes lab slip + that plane’s metadata |
| Bedside nurse | Exam | Health Device | `health/iosxe/<stamp>.json` |
| Records nurse | Prior admissions | Health ServiceNow | ServiceNow lab slip + metadata |
| Attending | SOAP | Health Analyzer | `state/health.json` only |

Nurses do not write `state/`. Analyzer does not write visit files.
[Network Ops](network-ops.md) and [Network Design](change-and-test-agents.md)
read the chart. They do not collect these planes.

## Health Monitor

One named check. Unnamed invoke asks which and stops. A Splunk finding
does not authorize a ThousandEyes query or an IOS-XE GET.

**Splunk** — syslog for the lab index and sourcetype. Window is the
watermark (`collected_through`), not another rolling 24 hours.

**ThousandEyes** — path tests: loss, latency, jitter, errors, alerts.
Account and test ids come from metadata. Standing order on loss /
error rounds: one path-vis on the worst direction — still this visit.

The stamp is vitals + `vs_prior`, not a copy of the MCP JSON.

## Health Device

Device plane only. GET interfaces, BGP, and counters. ACL GET only
when a ranked up port is dropping. Rank from `inventory/prod.json`.
Prior stamp comes from `state/health.json` `consults.iosxe.source_ref`
(no directory list). Does not change config.

## Health ServiceNow

Tickets for **this lab**, scoped by a workspace marker and inventory
labels. Shared-instance rows are out of scope. Open in-scope tickets
do not degrade vital status. Filing cases is
[Ops ServiceNow Operator](servicenow-agents.md).

## Health Analyzer

Reasoner. Reads the four latest stamps (and prior `state/health.json`),
**folds** new visit `metrics` into `series` (last 10 per plane), then
writes SOAP. Envelope status is worst of ThousandEyes, Splunk, and
IOS-XE. ServiceNow does not vote. Silent plane is not health.

- **assess-now** — dispatch stale planes if attached; do not wait;
  analyze what is on disk.
- **refresh-then-assess** — wait only for planes that are both stale
  and material (a WAN question does not block on ticket history).

`soap.plan` / envelope `next_action` is a named nurse visit, a
referral, or `none`. No inspect-stamp. No SKUs. No git change.

## Example notes

Trimmed from the skill examples. Full schemas live next to each skill.

### Wristband — Splunk metadata

`health/metadata-splunk.json`

```json
{
  "schema": "health-metadata-splunk/v1",
  "source_agent": "health-monitor",
  "splunk": {
    "index": "example",
    "sourcetype": "syslog",
    "collected_through": "2026-08-30T18:43:58Z",
    "last_visit_id": "2026-08-30T18-45-00Z"
  }
}
```

ThousandEyes metadata holds `account_id` and `tests[]`. ServiceNow
metadata holds `marker` and `last_visit_id`.

### O — Splunk lab slip

`health/splunk/<stamp>.json`

```json
{
  "schema": "health-splunk-check/v2",
  "source": "splunk",
  "watch_id": "2026-08-30T18-45-00Z",
  "status": "ok",
  "headline": "37 new syslog events, 7 hosts; CONFIG_I + DMI sync; 0 flaps",
  "coverage": { "state": "complete" },
  "vs_prior": {
    "prior_watch_id": "2026-08-30T04-03-20Z",
    "delta": "unchanged",
    "changed": []
  },
  "metrics": [
    {
      "at": "2026-08-30T18:45:00Z",
      "scope": "window",
      "event_count": 37,
      "critical_error_count": 0,
      "flap_count": 0,
      "unique_hosts": 7
    }
  ]
}
```

### O — ThousandEyes lab slip

`health/thousandeyes/<stamp>.json`

```json
{
  "schema": "health-thousandeyes-check/v2",
  "source": "thousandeyes",
  "watch_id": "2026-08-14T16-05-00Z",
  "status": "degraded",
  "headline": "path-b 30/30 errored; path-a 0% loss",
  "coverage": { "state": "complete" },
  "vs_prior": {
    "prior_watch_id": "2026-08-14T15-00-00Z",
    "delta": "worse",
    "changed": ["test:t2 ok_rounds 12 → 0", "test:t2 error_rounds 0 → 30"]
  },
  "metrics": [
    { "scope": "test:t1", "loss_pct": 0.0, "ok_rounds": 1, "error_rounds": 0 },
    { "scope": "test:t2", "loss_pct": null, "ok_rounds": 0, "error_rounds": 30 }
  ]
}
```

### O — IOS-XE lab slip

`health/iosxe/<stamp>.json`

```json
{
  "schema": "health-iosxe-check/v2",
  "source": "iosxe",
  "watch_id": "2026-08-31T16-00-00Z",
  "status": "ok",
  "headline": "edge-1 + wan-1: 0 oper-not-ready, BGP established, 0 errors/flaps",
  "coverage": { "state": "complete" },
  "vs_prior": {
    "prior_watch_id": "2026-08-31T10-00-00Z",
    "delta": "unchanged",
    "changed": []
  },
  "metrics": [
    { "scope": "device:wan-1", "oper_not_ready": 0, "bgp_not_established": 0, "in_errors": 0, "num_flaps": 0 }
  ]
}
```

### O — ServiceNow lab slip

`health/servicenow/<stamp>.json`

```json
{
  "schema": "health-servicenow-check/v2",
  "source": "servicenow",
  "watch_id": "2026-09-01T15-00-00Z",
  "status": "ok",
  "headline": "0 open lab INC / 0 open lab CHG; 14 shared-instance open ignored",
  "coverage": { "state": "complete" },
  "vs_prior": {
    "prior_watch_id": "2026-09-01T09-00-00Z",
    "delta": "unchanged",
    "changed": []
  },
  "metrics": [
    { "scope": "lab", "open_incidents": 0, "open_changes": 0, "open_p1p2": 0, "out_of_scope_open": 14 }
  ]
}
```

An in-scope open ticket does not set `status` to `degraded`. Tickets
are history, not vitals.

### SOAP — attending chart

`state/health.json`

```json
{
  "schema": "health-state/v5",
  "source_agent": "health-analyzer",
  "status": "degraded",
  "headline": "Unhealthy is the WAN path, not the lab syslog or the boxes.",
  "next_action": "Network Ops: path or config, not a down box.",
  "soap": {
    "subjective": "Scheduled assess-now.",
    "objective": "TE path-b 30/30 error rounds (worse vs prior); path-a 0% loss. Splunk 0 flaps. IOS-XE ranked wan/edge oper-ready. ServiceNow not requested.",
    "assessment": "Unhealthy is the WAN path, not the lab syslog or the boxes.",
    "plan": "Network Ops: path or config, not a down box."
  },
  "assessment": {
    "unhealthy": ["thousandeyes path-b (test t2): 30/30 error rounds this visit"],
    "healthy": ["splunk: 0 flaps, 0 critical across 7 hosts", "iosxe: ranked wan/edge oper-ready"],
    "contradictions": ["WAN path-b failed; device plane and syslog are quiet"],
    "opinion": "Unhealthy is the WAN path, not the lab syslog or the boxes."
  },
  "trend_analysis": {
    "narrative": "TE path-b flipped from ok rounds to all errors vs prior stamp; Splunk and IOS-XE stayed quiet."
  }
}
```

`consults.<plane>` is the attending’s impression of that lab slip, not
a paste of the nurse headline. `series` is the last ten `metrics`
points per plane. Stamp path stays on `consults.*.source_ref`.

## Invoke lines

- `Run the Splunk health check only.`
- `Run the ThousandEyes health check only.`
- `Run the network device health check only.`
- `Run the ServiceNow health check only.`

Analyzer: an ask to analyze, assess, chart, or trend is `assess-now`.
Refresh first is `refresh-then-assess`.
