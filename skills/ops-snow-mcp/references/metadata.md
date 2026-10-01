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

Workspace first. If `servicenow.marker` is already set, keep it.
If it is missing, set it from `inventory/prod.json`, the same way
the Health ServiceNow nurse does:

1. `lab_title` when that string is non-empty.
2. Else `source.name`.

Write it with `provenance: discovered` and continue. Do not ask.
Do not run a find to "confirm" it: the marker is the lab title by
contract, it is written into `comments` on this lab's CMDB CIs,
and a ticket set with zero marker hits is a normal state (lab
tickets are usually matched by device name). A device `name` is
not the marker. `prod.json` missing both strings: do not invent a
marker; say so in one line and stop.

Only when the operator **types** a different marker on the invoke
do you write `provenance: user`.

## Write metadata

After resolve, and after every successful board or mutation:

- `source_agent` — `ops-snow-mcp`
- `servicenow.marker` / `match_terms` — from prior file or this
  resolve
- `servicenow.last_visit_id` / `last_collected_at` — this invoke
  when find/get succeeded; do not advance on MCP failure
- `provenance.servicenow` — `user` | `discovered`
