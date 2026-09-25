# Produce — Health Analyzer

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`. Do not
invent files. Persist with `write_file` on the catalog path.

Every completed analysis replaces **`state/health.json`**.
Do not write `health/<source>/` or other catalog files.

## When to write

| File | Kind | When |
|------|------|------|
| `state/health.json` | state | Every completed analysis; replace in full. |

Envelope `status`: `ok` when current vital consults were rolled up
and none degraded; `partial` when a vital plane is missing or
`not_requested`; `stale_chart` when a needed vital plane was stale
or dispatched; `degraded` when a voting vital consult is degraded;
`unknown` when no vital observation is usable.

`headline` is one line of `assessment.opinion`. `assessment`,
`trend_analysis`, `soap`, `problems`, `orders`, and `relations`
are required (arrays may be empty). `next_action` is `soap.plan`,
the prose of `orders[0]` or `none`.

`problems[]` is carried forward from the prior chart by `id`;
never renumber or drop an unresolved problem. `series.<plane>` is
a reference to that nurse's board; copy no points. `read[]` lists
at most ten paths.

After the write, if `orders[]` holds `Run the relationship compile
only.` and that writer is attached, invoke it and do not wait.

Do not write visit files under `health/`.

Analysis steps: `references/analyze.md`.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
