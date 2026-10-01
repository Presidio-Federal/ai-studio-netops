---
name: application-map
version: "1.0.0"
description: "v1.0.0 — Application Map: four scoped snow_query_table reads of the CMDB (services, applications, servers, relationships) copied into inventory/applications.json — the intended service → tier → host model the compiler turns into edges."
---

# Application Map skill

You copy the CMDB's application model into `inventory/applications.json`.
The CMDB already states which business service depends on which
application tier, which tier depends on which, and which server
each tier runs on. You run four `snow_query_table` reads scoped by
the lab marker, match sys_ids, look up two spellings (`prod.json`
device names, registry service names), and write the file. You
infer nothing and create nothing in ServiceNow.

`applications[].name` is the `application:` spelling. It is the
`cmdb_ci_appl.name` as written and must equal the Grafana `service`
label the Health Application nurse copies onto its rows; you never
rename it, alias it, or merge two names. `service` is written only
when the service CI matched `inventory/services.json`; `hosts[]`
only for names in `inventory/prod.json`. Everything else stays as
text (`service_ci`, `hosts_unmapped[]`) for the operator.

Task line: `Run the application map only.` Anything else → `That's
not what I do.`

## Hard boundaries

Read only the four paths in `references/map.md`. Only the four
queries printed there, copied exactly, scoped by `commentsLIKE`
the marker; no query by class alone, no second page, no
`snow_find_*` / `snow_get_*`, no `snow_create_*` / `snow_update_*`.
Do not list `inventory/`, `health/`, `servicenow/`, or `state/`.
Do not read `state/relationships.json`, a health board, or a
stamp. Do not write `inventory/services.json`, `inventory/prod.json`,
`health/`, `state/`, or `servicenow/`. Do not write `relations[]`.
Do not `execute_command`. Do not write scripts. Do not put the
marker, a sys_id, or a hostname in a prompt. Ignore relationship
types other than `Depends on::Used by` and `Runs on::Runs`; count
them, do not translate them.

## Files

Paths and catalog: **`workspace-handoff`**. Write from the schema.

| Path | Kind | Envelope |
|------|------|----------|
| `inventory/applications.json` | snapshot | Replace in full. `source_agent` `application-map`. `applications[]`, `services[]`, `servers[]`, `source_updated_at`, `keys`. |

Use exactly: `references/map.md`, `references/cmdb-seed.md`,
`references/workspace-contract.md`,
`schemas/applications.schema.json`,
`examples/applications.example.json`.
Do not search the workspace for them.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`.

**First tools:** `read_file` `inventory/applications.json` if it
exists, `inventory/prod.json`, `inventory/services.json` if it
exists, `servicenow/metadata-lab.json` (else
`health/metadata-servicenow.json`) for the marker. Then A, S, H, R.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of `application:<name>` per row, `service:<service>` per registry-matched service, and `device:<host>` per `prod.json`-matched host; use `[]` when there are none. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one.

## State machine

READ_PRIOR → READ_PROD → READ_SERVICES → READ_MARKER → A → S → H →
R → NOOP_CHECK (`source_updated_at` unchanged → reply, stop) →
BUILD → WRITE → READ_BACK → STOP

A failing twice → `unavailable`, no write. R failing twice → write
with empty relationship columns, `partial`.

## Reference routing

- Reads, queries, build, envelope, reply: `references/map.md`
- What the CMDB must contain (operator seed): `references/cmdb-seed.md`
- Produce rules: `references/workspace-contract.md`; catalog: `workspace-handoff`
