# Trends metadata

`servicenow/metadata-trends.json` is this visit’s lookup
(**metadata** Kind). Groups, categories, match terms, marker,
last-visit. **Not** the five-field envelope. Workspace first.
Do not put live group names or markers in the prompt.

## Read before ServiceNow MCP

1. `read_file` `servicenow/metadata-trends.json` if it exists.
2. If `last_visit_id` is set, open that stamp under
   `servicenow/trends/`.
3. `read_file` `inventory/prod.json` — device names, roles, tags.

This visit needs at least one of: `marker`, `match_terms[]`,
`assignment_groups[]`, `categories[]`.

## Resolve — incomplete scope only

Workspace first. Then discover. Then, if you cannot uniquely
tell which slice to use, **ask** and show options. Write the
choice. Do not invent a scope.

If scope is empty:

1. One bounded `snow_find_incidents` (active) and
   `snow_find_assignment_groups`.
2. Build a short options list from those rows (group names,
   category values, repeated short-description tokens) plus
   inventory labels.
3. Ask which slice this visit is (EUC/demo, a metro pool, a
   category, a marker string).
4. Write that into metadata (`provenance` `user` or
   `discovered` if exactly one fit).
5. No human and still not unique: stop.

```text
Need: which ServiceNow slice to trend.
Options:
- <from find / groups / inventory>
Which?
```

## Write metadata

After resolve, and after every successful visit:

- `source_agent` — `ops-servicenow-trends`
- scope fields from prior file or this resolve
- `last_visit_id` / `last_collected_at` — this visit when
  collection succeeded; do not advance on MCP failure
