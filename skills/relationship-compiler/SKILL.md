---
name: relationship-compiler
version: "1.3.0"
description: "v1.3.0 — Relationship compiler: compile_graph.py copies nurse and CMDB columns into state/relationships.json; it infers nothing."
---

# Relationship compiler skill

You are the **relationship compile** skill. You turn the edges other
writers already recorded as columns into one graph file,
`state/relationships.json`. You do not measure, judge, or infer.
If a rule in `references/compile.md` does not name the column, the
edge does not exist.

Three layers, kept apart by `basis`:

- `intended` — an operator or git declared it (`prod.json`
  `links[]`; `inventory/applications.json` `service`, `hosts[]`,
  `depends_on[]`).
- `observed` — a tool payload contained it and a writer recorded it
  as a column (CDP neighbor, BGP `peer`, a NetFlow conversation's
  `src_device` / `dst_device` / `exporter`, an application probe
  row's `application` and `site`, a container row's `application`
  and `device`, a host row's `device` and `site`, a ticket's typed
  columns and `rfc`, a run's `git.commit_sha` + `devices[]` /
  `interfaces[]`, a compliance result row's `device` with its
  `test:` / `control:` keys).
- `asserted` — Health Analyzer or Network Ops concluded it
  (`relations[]` on their state files); copied through.

An edge lives on `(from, to, rel, basis)` with `first_seen`,
`last_seen` (source time, never compile time), `seen_count`,
`sources[]`, `status` (`current` / `stale`), and `sides` (1 or 2)
on cables and peerings. `drift[]` lists where `intended` and
`observed` disagree — mechanically, and only where something was
declared: cables against `prod.json` `links[]`, application-on-host
against `applications.json`.

## Hard boundaries

Read only the fifteen paths in `references/compile.md`. Do not list
`health/`, `state/`, `inventory/`, or `operational/`. Do not open a
stamp. Do not read `inventory/infra-sot.json`,
`compliance/intel.json`, or `inventory/services.json`. Do not call
an MCP tool. Call `execute_command` only to run
`scripts/compile_graph.py`. `execution_type` is `standard`. Do not
write scripts. Do not write under `automations/schedules/`. The
script writes only `state/relationships.json`. Do not add an edge
from prose (`issue`,
`note`, `headline`), from a ticket key whose typed column is null,
from a NetFlow row whose device column is null, from a container
whose `device` is null, from a container `name` or `service` text,
or from a neighbor with `far` null. An `application:` key is the
`application` column as written; a NetFlow row has none. Do not
invent a key. Do not restate an edge with a different `rel` than
the table gives.

## Files

Paths and catalog: **`workspace-handoff`**. Write from the schema.

| Path | Kind | Envelope |
|------|------|----------|
| `state/relationships.json` | state | Five-field. Replace in full. `source_agent` `relationship-agent`. Required `compiled_at`, `coverage`, `watermarks`, `edges`, `drift`, `keys`. |

Use exactly: `references/compile.md`,
`schemas/relationships-state.schema.json`,
`examples/relationships-state.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**First tool:** `compile` under `execution_type: standard`. The
script reads the fixed list in `references/compile.md` and writes
the file. Reply from its last stdout line.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every `edges[].from` and `edges[].to`; use `[]` when there are none. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Drift rows, paths, and shas never become keys on their own.

## State machine

COMPILE_SCRIPT → STOP. Watermarks unchanged: the script writes
nothing and the last line has `wrote` null.

No source returned content: `status` `unknown`, `edges` carried
forward from the prior file (or `[]`), still write.

## Reference routing

- Read list, copy table, upsert, drift, envelope: `references/compile.md`
- Catalog, task line, who reads this file: `workspace-handoff`
