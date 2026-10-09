---
name: ops-servicenow-trends
version: "1.3.0"
description: "v1.3.0 — ServiceNow trend visit runs visit_trends.py; clusters repeating titles, stamp under servicenow/trends; does not mutate records."
---

# Ops ServiceNow Trends skill

One scan per conversation. A schedule line or a chat that
names trends is authorization. Run `scripts/visit_trends.py`
(`references/watch.md`). The script writes one new stamp. Do not
mutate ServiceNow.

Write `servicenow/trends/<stamp>.json`. Update
`servicenow/metadata-trends.json` when scope or
`last_visit_id` changes. Do not write `state/`. Do not list
`servicenow/trends/` to find a prior stamp.

If they ask for a health visit or to mutate a ticket or KB:
reply `That's not what I do.` and stop.

## Hard boundaries

The script reads with `snow_query_table` (find has no lookback)
and `snow_find_knowledge`. The manual fallback may use the
find/get tools in `references/watch.md`. Never `snow_create_*`,
`snow_update_*`, catalog, or assets. Do not
write `health/`, `state/servicenow.json`, `servicenow/cases/`,
`trends.json`, `trend-analysis.json`, or `health-board.md`.
Do not invent files or ticket numbers. Unavailable: counts
**null**, never `0`. Do not write under
`automations/schedules/`. Call `execute_command` only to run
`scripts/visit_trends.py`. Do not write scripts.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. The script validates and
writes the stamp and metadata. On the manual fallback, persist
with `write_file` on catalog paths. Do not run a validator
yourself.

| Path | Kind | Envelope |
|------|------|----------|
| `servicenow/metadata-trends.json` | metadata | Scope and last-visit. **Not** five-field. |
| `servicenow/trends/<stamp>.json` | observation | Never overwrite. Required `metrics`. |

Use exactly: `references/watch.md`, `references/metadata.md`,
`references/workspace-contract.md`,
`schemas/servicenow-metadata-trends.schema.json`,
`schemas/servicenow-trend.schema.json`,
`examples/servicenow-metadata-trends.example.json`,
`examples/servicenow-trend.example.json`.
Do not search the workspace for them.

Every JSON write requires top-level `keys`: a deduplicated
canonical union, or `[]`. Metadata normally has `[]`. For a
trend observation derive `incident:<number>` only from
`example_numbers[]` and `open_consuming[].number`, and
`device:<name>` only from `clusters[].devices`. Keep those
nested identity fields. Do not key KB numbers, themes,
assignees, recommendations, prose, or source refs. An explicit
location is `site:` (never `location:`).

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**Visit — first tool:** one `execute_command`,
`execution_type: "mcp_orchestration"`, the collect command in
`references/watch.md`. Add `--schedule` when the task is a
schedule line. If the summary `needs_scope` is true, ask with
those options and stop. If `needs_note` is non-empty, one
`annotate` command under `execution_type: "standard"`. Reply
from the summary line. If stderr says `hai_mcp unavailable`,
follow the manual order in `references/watch.md`. Never
overwrite a timestamped file.

## State machine

READ_METADATA is inside the script. COLLECT_SCRIPT → [ASK_SCOPE]
→ [ANNOTATE] → STOP. Manual fallback, only when hai_mcp is
unavailable: READ_METADATA → READ_PRIOR_STAMP →
RESOLVE_IF_NEEDED → PICK_STAMP → COLLECT → WRITE_CHECK →
READ_BACK → WRITE_METADATA → READ_BACK → STOP

On collection failure: still write that check
(`unavailable`, null counts). Do not advance
`last_visit_id`.

## Reference routing

- Visit steps, budget: `references/watch.md`
- Scope: `references/metadata.md`
- Paths: `workspace-handoff`; produce: `references/workspace-contract.md`
