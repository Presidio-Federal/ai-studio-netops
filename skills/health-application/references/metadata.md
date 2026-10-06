# Application metadata — ids, window, board

The file is `health/metadata-application.json`. **Not** the
five-field envelope. It is the board (`application.current[]`),
the annotation ring, and the lookup. Workspace first. Do not put a
datasource uid, job name, host name, or service name in the prompt
or this skill.

## Read before Grafana

1. `read_file` `health/metadata-application.json` if it exists.
2. The board is the prior; do not open the prior stamp.
3. Only if `probe_job` is missing: resolve (below). Do not discover
   when metadata already has it.

Fields the visit needs: `application.probe_job`,
`application.window` (write `1h` when missing),
`application.latency_threshold_ms` (write `500` when missing; do not
overwrite a value already there), `application.expected_vantages`
(write `cloud`, `hq`, `branch` when missing). `datasource_uid`
may stay null; the tool then uses the default Prometheus
datasource. An operator may pin it.

## Window

Every visit passes `application.window` (default `1h`) as
`timerange` on every query, as the `[<window>]` range in P4, and
as `timerange` on the annotations list. No `7d`, no `24h`, no
watermark: the board holds the state; the window is how far back
the success percentage and the change annotations reach.

## Resolve — `probe_job` only

Run call T (`grafana_prometheus_targets()`) — you need it anyway.
The probe job is the `labels.job` of the targets whose `scrapeUrl`
contains `/probe?`. Exactly one such job → write it
(`provenance: discovered`) and continue. Several → show them and
ask which; no human on a schedule → stop and write on the visit
row that `probe_job` is missing. None → write `probe_job` null,
skip P1–P4, coverage `partial`, and say so in the coverage detail.

Ask shape:

```text
Need: probe_job
Options:
- <job from the target list>
Which?
```

Do not create scrape jobs, dashboards, or datasources. Do not
guess a job name.

## Lookup

`lookup` = `{services[], sites[], vantage_points[], hosts[]}`,
written from call L on the baseline or when the object is empty.
It records the label spellings the datasource used so a reader
(Analyzer, compiler, registry keeper) can match them; it is not a
filter and it is not truth about which application exists. Copy
label values as-is.

## Write metadata

`write_file` `health/metadata-application.json` **every visit**:
after resolve (if anything was resolved), again when the rows
exist, and again at the end with `last_visit_id` when a stamp was
written. Never copy another source's board through this file.
