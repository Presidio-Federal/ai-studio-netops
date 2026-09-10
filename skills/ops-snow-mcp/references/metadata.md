# Lab metadata

`servicenow/metadata-lab.json` is this agent’s lookup
(**metadata** Kind). Marker, match terms, last-visit. **Not** the
five-field envelope. Workspace first. Do not put live marker text
in the prompt. This is not `health/metadata-servicenow.json` and
not `servicenow/metadata-trends.json`.

## Read before ServiceNow MCP

1. `read_file` `servicenow/metadata-lab.json` if it exists.
2. `read_file` `inventory/prod.json` — labels and lab title.
3. Prior `state/servicenow.json` if it exists.

This visit needs `servicenow.marker`. Optional `match_terms[]`
only if they named extra strings.

In-scope = marker / match terms / inventory labels in
short_description, description, or work_notes. Shared-instance
rows are out of scope.

## Resolve — incomplete marker only

Workspace first. Then discover. Then, if you cannot uniquely tell
which customer/lab string to use, **ask** and show options. Write
the choice. Do not invent a marker.

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

## Write metadata

After resolve, and after every successful board or mutation:

- `source_agent` — `ops-snow-mcp`
- `servicenow.marker` / `match_terms` — from prior file or this
  resolve
- `servicenow.last_visit_id` / `last_collected_at` — this invoke
  when find/get succeeded; do not advance on MCP failure
- `provenance.servicenow` — `user` | `discovered`
