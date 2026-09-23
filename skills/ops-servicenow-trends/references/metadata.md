# Trends metadata

`servicenow/metadata-trends.json` is this visit’s lookup
(**metadata** Kind). Groups, categories, match terms, marker,
last-visit. **Not** the five-field envelope. Workspace first.
Do not put live group names or markers in the prompt.

## Read before ServiceNow MCP

1. `read_file` `servicenow/metadata-trends.json` if it exists.
2. If `last_visit_id` is set, open that stamp under
   `servicenow/trends/`.
3. `read_file` `inventory/prod.json` if it exists — device names,
   roles, tags. Optional.

This scan needs at least one of: `marker`, `match_terms[]`,
`assignment_groups[]`, `categories[]`.

`lookback_days` defaults to 14. `min_related_cases` defaults
to 3. Write those defaults if the file omitted them.

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
3. **Interactive:** ask which slice. Write the choice
   (`provenance` `user`).
4. **Schedule / no human:** do not ask. If exactly one slice
   fits, write it (`provenance` `discovered`) and collect.
   If more than one, pick the largest repeating class from
   that find, write it, collect. Still write the stamp.

Never stop a scheduled visit to wait for a human.

```text
Need: which ServiceNow slice to trend.
Options:
- <from find / groups / inventory>
Which?
```

## Write metadata

After resolve, and after every successful scan:

- `keys` — `[]`; scope labels and filters are not entity
  identity and do not create canonical keys
- `source_agent` — `ops-servicenow-trends`
- scope fields from prior file or this resolve
- `lookback_days` / `min_related_cases` — prior file or defaults
- `last_visit_id` / `last_collected_at` — this scan when
  collection succeeded; do not advance on MCP failure
