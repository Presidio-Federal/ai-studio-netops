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

## Resolve — incomplete marker only

Workspace first (this metadata). Then discover. Then, if you cannot
uniquely tell which customer/lab string to use, **ask** and show
options. Write the choice. Do not invent a marker.

If `servicenow.marker` is missing:

1. One bounded find (`snow_find_incidents` active, then changes if
   needed). Use inventory `name` / lab title from `prod.json` only
   as search hints — not as invented markers.
2. From those rows plus inventory labels, build a short options
   list (candidate marker strings, device names, lab title).
3. Human: ask which option is this lab. Write `servicenow.marker`
   (`provenance: user` or `discovered` if exactly one fit).
4. No human and still not unique: stop. Do not invent it.

```text
Need: text that identifies this lab’s tickets.
Options:
- <from find / inventory>
Which?
```

Optional `match_terms[]` only if they named extra strings.

Do not create tickets.

## Write metadata

After resolve, and after every successful collection, `write_file`
`health/metadata-servicenow.json`:

- `source_agent` — `health-servicenow`
- `servicenow.marker` / `match_terms` — from prior file or this resolve
- `servicenow.last_visit_id` / `last_collected_at` — this visit when
  collection succeeded; do not advance on MCP failure
- `provenance.servicenow` — `user` | `discovered`
