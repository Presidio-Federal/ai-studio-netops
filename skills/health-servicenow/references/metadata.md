# Health metadata — ServiceNow lookup

`health/metadata-servicenow.json` is this plane’s lookup
(**metadata** Kind). Marker, match terms, last-visit stamps. **Not**
the five-field envelope. Workspace first. Do not put live marker
text in the prompt or this skill. Do not read Splunk or ThousandEyes
metadata.

## Read before ServiceNow MCP

1. `read_file` `health/metadata-servicenow.json` if it exists.
2. If `servicenow.last_visit_id` is set, that stamp is the prior
   observation.
3. `read_file` `inventory/prod.json` — labels and lab title.

This visit needs `servicenow.marker`.

Do not collect Splunk, ThousandEyes, or IOS-XE. Do not copy PAT into
metadata.

## Resolve — missing marker only

Do not ask. A schedule has no one to answer. Do not list options.
Do not treat a device name and the lab title as competing markers.

If `servicenow.marker` is already set, keep it.

If it is missing, set it from `inventory/prod.json` and write
metadata before any ServiceNow call:

1. `lab_title` when that string is non-empty.
2. Else `source.name`.

`provenance.servicenow` is `discovered`. Do not invent a third
string. A device `name` is not the marker. Zero hits on the lab
title is a collect result, not a reason to stop.

`prod.json` missing both `lab_title` and `source.name`: do not
invent a marker. Write the observation `unavailable` and stop.

Do not create tickets. Do not put device names into `match_terms`.

## Write metadata

After resolve, and after every successful collection, `write_file`
`health/metadata-servicenow.json`:

- `source_agent` — `health-servicenow`
- `servicenow.marker` / `match_terms` — from prior file or this resolve
- `servicenow.last_visit_id` / `last_collected_at` — this visit when
  collection succeeded; do not advance on MCP failure
- `provenance.servicenow` — `user` | `discovered`
