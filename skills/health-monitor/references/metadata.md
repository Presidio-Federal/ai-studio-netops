# Health metadata — ids and Splunk window

Splunk lookup is `health/metadata-splunk.json`. ThousandEyes lookup
is `health/metadata-thousandeyes.json`. **Not** the five-field
envelope. Workspace first. Do not put live index names or test ids
in the prompt or this skill. Do not read or write the other source’s
metadata on this visit.

## Read before telemetry MCP

1. `read_file` this visit’s metadata file if it exists.
2. If `last_visit_id` is set, that stamp is the prior observation.
3. Only if ids are still incomplete: resolve (below). Do not list
   when metadata already has the facts for this visit.

**Splunk visit** needs `splunk.index` and `splunk.sourcetype`.
**ThousandEyes visit** needs `thousandeyes.account_id` and at least
one `tests[].test_id`.

Do not collect another health source. Do not copy PAT into metadata.

## Splunk window

- No `collected_through`: `earliest_time` = `bootstrap_earliest` if
  set, else `-24h`. `latest_time` = `now`.
- After a **successful** Splunk collection: set `collected_through`
  to `last_event_at` when events exist, else this visit’s
  `checked_at`. Set `last_visit_id` and `last_collected_at`. Never
  move `collected_through` backward. Re-read metadata before writing
  it.
- Later Splunk visits: `earliest_time` = `collected_through`. Collect
  newly arrived data — not another rolling 24h.
- Failed MCP: do **not** advance the watermark. Empty successful
  window: zeros allowed; **do** advance to `checked_at`.

Pass the window as MCP `earliest_time` / `latest_time`. Do not put
`earliest=` in SPL.

ThousandEyes window is `thousandeyes.window` or `1h`. Not a Splunk
watermark.

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

**ThousandEyes** missing `account_id` or tests:
`te_manage_account_groups(action="list")` then `te_tests_get_tests`
(or `te_tests_manage_agent_agent` list) once. One account and a
clear path-test set → write them (`provenance: discovered`) and
collect. Several accounts or no obvious tests → show options and
ask. No human: one account + tests you will watch, write and run;
ambiguous → stop. Do not list agents. Do not copy ids out of this
skill.

Human ask shape (after you have options):

```text
Need: <index | sourcetype | TE account | TE tests>
Options:
- <from the listing>
Which?
```

Do not create indexes, dashboards, or tests. Do not `index=*`.

## Write metadata

After resolve, after every successful Splunk watermark update, and
after every successful stamp write, `write_file` **this visit’s**
metadata file only (`last_visit_id`). Do not copy the other source
through.
