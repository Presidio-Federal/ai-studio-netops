# Health metadata — ServiceNow lookup and board

`health/metadata-servicenow.json` is this plane's lookup **and
board** (**metadata** Kind, schema
`schemas/health-metadata-servicenow.schema.json`). Not the five-field
envelope. Workspace first. Do not put live marker text, column names,
or ticket numbers in the prompt or this skill. Do not read Splunk,
ThousandEyes, or IOS-XE metadata.

## Read before ServiceNow MCP

1. `read_file` `health/metadata-servicenow.json` if it exists. The
   file **is** the board (`servicenow.current[]`); do not open the
   prior stamp.
2. `read_file` `inventory/prod.json` — device names and lab title.
3. `read_file` `inventory/services.json` if it exists.

This visit needs `servicenow.marker` and `servicenow.entity_fields`.

## Resolve — marker (missing only)

Do not ask. A schedule has no one to answer. Do not list options.

If `servicenow.marker` is already set, keep it. If it is missing,
set it from `inventory/prod.json`:

1. `lab_title` when that string is non-empty.
2. Else `source.name`.

`provenance.servicenow` is `discovered`. A device `name` is not the
marker. Zero hits on the marker is a collect result, not a reason to
stop. `prod.json` missing both strings: do not invent a marker; write
the observation `unavailable` and stop.

`match_terms` is operator-set (a correlation tag, a project code).
Leave it `[]` when absent. Never put device names in it.
`lookback_days` default `30`; keep an operator's value.

## Resolve — entity fields (missing only)

Typed ticket columns are a **capability probe**: some instances have a
device column, some have none. Discover once, write the answer, never
retry, never ask.

**Call D:**

```
snow_query_table(
  table="sys_dictionary",
  query="name=incident^elementSTARTSWITHu_",
  fields="element,column_label,internal_type",
  limit=50)
```

Map each returned `element` by its `element` name and
`column_label`, case-insensitive, first match per slot:

| Slot | Match when name or label contains |
|------|-----------------------------------|
| `device` | `device` |
| `interface` | `interface` |
| `ip` | `ip` (and not `description`) |
| `service` | `service` |

A slot with no match is `null`. Zero rows, `ok: false`, or a 404 →
every slot `null`. Write `entity_fields` to metadata with
`provenance.entity_fields` `discovered`, then continue the visit.
Null slots are not degraded coverage: the rows simply carry `null`
in those columns and no key comes from them.

An operator may overwrite `entity_fields` (`provenance.entity_fields`
`user`); keep their values.

## Write metadata

`write_file` `health/metadata-servicenow.json` **every visit** (it is
the board): after resolve, and again at the end with `current[]`,
`series[]`, `visits[]`, `last_collected_at`, `last_visit_id` (only
when a stamp was written), `baseline_visit_id` (first visit). Do not
advance `last_collected_at` on `unavailable`. Field rules:
`references/query.md` "Board".
