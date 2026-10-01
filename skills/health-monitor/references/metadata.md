# Health metadata — ids, window, boards

Splunk board is `health/metadata-splunk.json`. NetFlow board is
`health/metadata-netflow.json`. **Not** the five-field envelope.
Workspace first. Do not put live index names, bucket names, or
exporter addresses in the prompt or this skill. Do not read or
write the other source’s metadata on this visit.

## Read before telemetry MCP

1. `read_file` this visit’s metadata file if it exists.
2. The metadata file **is** the board (`splunk.current[]` /
   `netflow.current[]`); do not open the prior stamp.
3. Only if ids are still incomplete: resolve (below). Do not list
   when metadata already has the facts for this visit.

**Splunk visit** needs `splunk.index` and `splunk.sourcetype`.
**NetFlow visit** needs `netflow.bucket`, `netflow.measurement`,
and `netflow.window`. `exporters[]` empty is fine — call S in
`references/netflow.md` fills it on the baseline.

Do not collect another health source. Do not copy PAT into metadata.

## Splunk window

- No `collected_through`: this is the baseline visit.
  `earliest_time` = `-7d`, `latest_time` = `now`. Ignore
  `bootstrap_earliest`. The board is state; a week seeds it.
- After S1 and S2 succeed and the board is built: set
  `collected_through` to the latest S1 `last_at` when events exist,
  else this visit’s `checked_at`. Set `last_collected_at` every
  visit; `last_visit_id` only when a stamp was written;
  `baseline_visit_id` on the first visit. Never move
  `collected_through` backward.
- Later Splunk visits: `earliest_time` = `collected_through`. Collect
  newly arrived data — not another rolling 24h.
- Failed S1: do **not** advance the watermark. Empty successful
  window (S1 zero rows): **do** advance to `checked_at`; quiet visit.

Pass the window as MCP `earliest_time` / `latest_time`. Do not put
`earliest=` in SPL.

## NetFlow window

Every NetFlow visit, first or later, passes `netflow.window`
(default `1h`; write `1h` when the field is missing) as the tool's
`timerange`. No `7d`, no `24h`, no watermark: the board holds the
state, the window is how much flow the state is read from. Every
Flux query keeps `range(start: v.timeRangeStart, stop:
v.timeRangeStop)`; the tool fills it.

## Resolve — incomplete for this visit only

Workspace first (this metadata). Then **discover**. Then, if more
than one value still fits, **ask** and show the options. Write the
choice into metadata. Do not invent ids. Do not seed from this
skill.

**Splunk** missing `index` / `sourcetype`: one `splunk_get_indexes`
(not `index=*`). One index → write it (`provenance: discovered`)
and continue. Several → list them as options and ask which index
and sourcetype. No human (schedule): if exactly one index, use it;
if several, stop and write what you listed is missing.

**NetFlow** missing `bucket` / `measurement`: one
`grafana_influx_schema()` with no measurement lists the
measurements in the default bucket. Keep the one whose tag keys
(a second call with `measurement=<name>`) include `src`, `dst`,
`dst_port`, `protocol`, and `source`; skip `internal_*` and
`*_options`. Exactly one fits → write `bucket`, `measurement`,
`window` `1h` (`provenance: discovered`) and continue. Several →
show options and ask. No human: one → write and run; several →
stop. `exporters[]` is filled by call S in `references/netflow.md`;
`device` on each exporter row is resolved there and never guessed.
An operator may pin `datasource_uid`; otherwise leave it null and
let the tool default.

Human ask shape (after you have options):

```text
Need: <index | sourcetype | bucket | measurement>
Options:
- <from the listing>
Which?
```

Do not create indexes, dashboards, buckets, or measurements. Do not
`index=*`.

## Write metadata

Splunk: `write_file` `health/metadata-splunk.json` **every visit**
(it is the board), after resolve and again at the end with the
watermark, `current[]`, `series[]`, `visits[]`. NetFlow: `write_file`
`health/metadata-netflow.json` **every visit** (it is the board),
after resolve and again at the end with `current[]`, `series[]`,
`visits[]`, `exporters[]`. Do not copy the other source through.
