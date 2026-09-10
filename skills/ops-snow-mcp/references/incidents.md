# Incident procedure

Use only these verified tools: `snow_find_incidents`, `snow_get_incident`, `snow_create_incident`, `snow_update_incident`.

Incident connector fields that matter: `number`, `sys_id`, `short_description`, `description`, `state`, `urgency`, `impact`, `category`, `work_notes`, `close_notes`, `close_code`, `updated_at`. There is no incident `correlation_id` or `external_id` parameter. Do not pass `jamf_evidence`.

`snow_update_incident` sends `work_notes` as a ServiceNow journal field (append). Never PATCH `description` solely to add notes. Do not replace existing work notes.

Incident states accepted by the connector: `1=New`, `2=In Progress`, `3=On Hold`, `6=Resolved`, `7=Closed`, `8=Canceled`. Urgency/impact: `1=High`, `2=Medium`, `3=Low`. Pass values from the request; never derive them. If urgency or impact is missing, fail — do not rely on the connector default of `2`.

In-scope only: `servicenow/metadata-lab.json` marker / match terms
plus inventory labels. Rows that do not match are out of scope —
do not treat the whole instance as this lab.

## Procedure

1. Validate the ServiceNow request (`schema=servicenow-request/v1`) with `scripts/validate_handoff.py` when script execution is available.
2. Read every path in `source_refs`. Strip a leading `workspace/` or `/workspace/` if present; then use the built-in file tool with the remainder.
3. Require:
   - `request_id`
   - `correlation_id`
   - `idempotency_key`
   - `short_description`
   - `summary` or `description`
   - affected device or path information
   - `urgency`
   - `impact`
   - `category`
   - recommendation or next action
4. Verify mutation authorization. Reads (`find_incident`, `get_incident`) may proceed without it.
5. Search active incidents for the idempotency key:

   ```text
   snow_find_incidents(search=<idempotency_key>, active_only=true)
   ```

   The find `search` parameter matches short description, description, work notes, and close notes. Stamp these markers into description and work notes on create/update:

   ```text
   [AUTOMATION-ID:<idempotency_key>]
   [CORRELATION-ID:<correlation_id>]
   [REQUEST-ID:<request_id>]
   ```

6. If exactly one active match exists, update that incident (`snow_update_incident` with `incident_number` or `incident_id`).
7. If no match exists and creation is authorized, create one incident (`snow_create_incident`). Copy `short_description`, `description`, `work_notes`, `urgency`, `impact`, and `category` from the request and source files.
8. If multiple matches exist, stop with an ambiguous-match failure. Create nothing.
9. Read the resulting incident back:

   ```text
   snow_get_incident(incident_number=<INC…>)
   ```

10. Verify number, sys_id, state, the automation/correlation markers, and requested material fields (`short_description`, urgency, impact, category, and appended notes when applicable).
11. Write the normalized result per `references/workspace-contract.md`.

## Operation mapping

| Request operation | Tool | Notes |
|---|---|---|
| `find_incident` | `snow_find_incidents` | No mutation. |
| `get_incident` | `snow_get_incident` | Requires `record.number` or `record.sys_id`. |
| `upsert_incident` | find, then create or update | One record. |
| `append_incident_work_notes` | `snow_update_incident(work_notes=...)` | Append only. |
| `resolve_incident` | `snow_update_incident(state="6", close_notes=..., close_code=...)` | Explicit authorization plus resolution evidence. `close_notes` required. |

## Rules

- Never derive urgency or impact.
- Never create more than one incident per request.
- Never replace existing work notes when appending.
- Do not resolve without explicit authorization and resolution evidence.
- Require close/resolution notes for resolve or close (`state=6` or `state=7`).
- Treat multiple possible matches as an error.
- Never call a REQ or RITM an incident.
