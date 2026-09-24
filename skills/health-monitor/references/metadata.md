# Health metadata — ids, window, boards

Splunk board is `health/metadata-splunk.json`. ThousandEyes board is
`health/metadata-thousandeyes.json`. **Not** the five-field
envelope. Workspace first. Do not put live index names or test ids
in the prompt or this skill. Do not read or write the other source’s
metadata on this visit.

## Read before telemetry MCP

1. `read_file` this visit’s metadata file if it exists.
2. The metadata file **is** the board (`splunk.current[]` /
   `thousandeyes.current[]`); do not open the prior stamp.
3. Only if ids are still incomplete: resolve (below). Do not list
   when metadata already has the facts for this visit.

**Splunk visit** needs `splunk.index` and `splunk.sourcetype`.
**ThousandEyes visit** needs `thousandeyes.account_id`, `window`,
and at least one `tests[].test_id`. `agents[]` empty is fine — call
A in `references/thousandeyes.md` fills it.

Do not collect another health source. Do not copy PAT into metadata.

## Splunk window

- No `collected_through`: this is the baseline visit. Do not use
  `-24h` and do not use `bootstrap_earliest` when that value is
  `-24h`. S0 (`references/splunk.md`) finds the oldest event still
  stored; `earliest_time` is that time. `latest_time` is `now`. If
  S0 fails, stop. Do not substitute `-24h`. Do not advance the
  watermark.
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

## ThousandEyes window

Every ThousandEyes visit, first or later, passes
`thousandeyes.window` (default `1h`; write `1h` when the field is
missing). No `7d`, no `24h`, no watermark: the board holds the
state, the window is how many rounds the state is read from.

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
once. Keep enabled tests of type `agent-to-agent` and
`agent-to-server`; skip `api`, `bgp`, disabled tests. Write each as
`{test_id, test_name, type, service: null}` (`provenance:
discovered`) and collect. Several accounts → show options and ask.
No human: one account → write and run; several → stop. Do not copy
ids out of this skill. `service` is set by an operator, never by
you.

Human ask shape (after you have options):

```text
Need: <index | sourcetype | TE account | TE tests>
Options:
- <from the listing>
Which?
```

Do not create indexes, dashboards, or tests. Do not `index=*`.

## Write metadata

Splunk: `write_file` `health/metadata-splunk.json` **every visit**
(it is the board), after resolve and again at the end with the
watermark, `current[]`, `series[]`, `visits[]`. ThousandEyes: `write_file`
`health/metadata-thousandeyes.json` **every visit** (it is the
board), after resolve and again at the end with `current[]`,
`series[]`, `visits[]`, `agents[]`. Do not copy the other source
through.
