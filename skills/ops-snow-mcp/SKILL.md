---
name: ops-snow-mcp
version: "3.6.0"
description: "v3.6.0 — Lab ServiceNow cases from servicenow/metadata-lab.json. Recommend a fix. One authorized INC/CHG mutation. Write state/servicenow.json and servicenow/cases/. Do not write health/ or trends."
---

# Ops ServiceNow Operator skill

You manage **this lab’s** cases. Scope is
`servicenow/metadata-lab.json` plus `inventory/prod.json`. Open
in-scope tickets get a recommended fix. Another agent creates and
tests the change. You update the ticket after that.

A mutation is still one authorized create/update per invoke, then
read-back. You do not diagnose the path. You do not apply IOS-XE.
You do not write `health/` or `servicenow/trends/`.

## Hard boundaries

Do not invent urgency/impact/category/risk/plans, approve a change,
trigger tests or deployments, access IOS-XE/CML/GitHub/Splunk/
ThousandEyes, select physical equipment, fulfill hardware logistics,
place catalog orders, treat REQ/RITM as CHG, create knowledge
articles, create more than one record per request, or claim success
before read-back. Do not invent a hostname or a lab marker.
Unavailable find: do not write zeros as proof the queue is empty.

## Available capability routing

Verified incident tools: `snow_find_incidents`, `snow_get_incident`,
`snow_create_incident`, `snow_update_incident`.

Verified change tools: `snow_find_changes`, `snow_get_change`,
`snow_create_change`, `snow_update_change`.

`snow_query_table` is read-only. Prefer dedicated find/get tools.
Catalog, asset, knowledge, and user-dispatch tools are out of
scope. `snow_find_change_tasks` / `snow_upsert_change_task` exist;
do not create extra CTASK records. Incident tools have no
`correlation_id` parameter; stamp markers into description /
work_notes and search them. Change tools accept `correlation_id` /
`external_id`. Connector summaries return `number`, `sys_id`,
`state`, `updated_at`; they do not return a record URL.

## Files

Paths and catalog: **`workspace-handoff`**. When/how:
`references/workspace-contract.md`. Write schemas in this skill.

| Path | Kind |
|------|------|
| `servicenow/metadata-lab.json` | metadata — not the envelope |
| `servicenow/cases/active.json` | snapshot |
| `servicenow/cases/index.json` | snapshot |
| `state/servicenow.json` | state |
| `servicenow/requests/**` | request / result queue |

Use exactly: `references/metadata.md`, `references/incidents.md`,
`references/changes.md`, `references/workspace-contract.md`,
`references/state.md`, `schemas/servicenow-metadata-lab.schema.json`,
`schemas/servicenow-request.schema.json`,
`schemas/servicenow-result.schema.json`,
`schemas/servicenow-state.schema.json`,
`schemas/servicenow-cases-active.schema.json`,
`schemas/servicenow-cases-index.schema.json`,
`examples/servicenow-metadata-lab.example.json`,
`examples/incident-request.example.json`,
`examples/change-request.example.json`,
`examples/result.example.json`,
`examples/servicenow-state.example.json`.
Do not search the workspace for them. Do not pass
`Internal directory` as a filename.

Do **not** call `get_folder_structure`. Do **not** list
`automations/schedules`. Do not use `Internal directory`, `/app/`,
or `/shared_workspace/...` on built-in file tools.

`execute_command` only when script execution is required. First
argument is exactly `request`, `result`, `state`, `active`, or
`index`. Second is a `/workspace/...` path. Never pass
`Internal directory`. Never use a relative path with
`execute_command`.

```text
python3 /skills/user/ops-snow-mcp/scripts/validate_handoff.py request /workspace/servicenow/requests/claimed/req-123.json
```

Skip if the script is missing. Never invent a path. Never `find /`.

If `source_refs` start with `workspace/` or `/workspace/`, strip
that prefix and read the remainder with built-in file tools.

**First tools:** `read_file` `servicenow/metadata-lab.json` if it
exists. Then `inventory/prod.json`. Then prior
`state/servicenow.json` if present.

## State machine

Missing marker: RESOLVE_MARKER → (ask if needed) → visit or STOP.

Named invoke with marker: READ_METADATA → READ_PROD →
READ_PRIOR_STATE → READ_EVIDENCE → (recommend | mutate one |
board) → REFRESH_CASES → WRITE_ACTIVE → WRITE_INDEX →
WRITE_STATE → WRITE_METADATA → VALIDATE → STOP

On failure: stop before any later mutation. Do not guess missing
values. Do not retry with invented paths or identifiers. Preserve
the source request. Write a normalized failed result when possible.

## Authorization gate

Reads and a recommended fix do not require mutation authorization.
A mutation is authorized only when (1) the user requested that
exact mutation in this conversation, (2) the request contains
explicit human authorization, or (3) the request names a
recognized policy: `confirmed-network-incident-v1`,
`append-validation-result-v1`, `append-deployment-result-v1`,
`close-resolved-incident-v1`. `requested_by` alone is not
authorization. Policy must not authorize production change
creation, approval, scheduling, implemented, or close. Missing
authorization: `status=needs_approval`, `action=noop`, no mutation.

## Read-before-write

Never mutate from chat memory. Read the request and every
`source_refs` path first. Copy urgency, impact, category, plans,
and evidence only from those files.

## Idempotency and deduplication

Search by `idempotency_key` before create. Exactly one active
match → update that record. Zero matches and create authorized →
create one. Multiple matches → fail, no mutation.

## Reference resolution

Never invent a `sys_id`. Resolve existing records with find/get.
Pass request fields through; do not substitute MCP defaults for
missing urgency or impact.

Incident lookup uses
`snow_find_incidents(search=<idempotency_key>)` because incident
tools have no correlation-id filter. Change lookup uses
`snow_find_changes(correlation_id=<idempotency_key>)`.

## Read-back verification

After create or update, call `snow_get_incident` or
`snow_get_change`. Confirm number, sys_id, state, correlation
marker, and requested material fields. Success requires
`verification.read_back=true` plus number and sys_id.

## Error behavior

Stop. Do not invent paths or record ids. Write
`servicenow/requests/failed/<request-id>.json` when possible.
Report `status=failed`.

Validate with `scripts/validate_handoff.py` in `request` or
`result` mode. The script never contacts ServiceNow.

## Reference routing

- Marker: `references/metadata.md`
- Incident task: `references/incidents.md`
- Change task: `references/changes.md`
- Board: `references/state.md`
- Paths: `workspace-handoff` then `references/workspace-contract.md`
- Do not load `references/assets.md` or `references/catalog.md`
