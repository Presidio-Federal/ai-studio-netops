# Incident procedure

Use only these verified tools: `snow_find_incidents`, `snow_get_incident`, `snow_create_incident`, `snow_update_incident`.

Incident connector fields that matter: `number`, `sys_id`, `short_description`, `description`, `state`, `urgency`, `impact`, `category`, `work_notes`, `close_notes`, `close_code`, `updated_at`, and `extra_fields` (typed `u_` columns, connector ≥ 1.2.0 — see below). There is no incident `correlation_id` or `external_id` parameter. Do not pass `jamf_evidence`.

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

   When you passed `extra_fields`, also read those columns back —
   the get tool does not return them:

   ```text
   snow_query_table(table="incident", query="number=<INC…>", fields="number,<the u_ columns you wrote>", limit=1)
   ```

10. Verify number, sys_id, state, the automation/correlation markers, and requested material fields (`short_description`, urgency, impact, category, appended notes, and every typed column you wrote — same value as the request).
11. Write the normalized result per `references/workspace-contract.md`.
    Its top-level `keys` contains the source-supported
    `incident:<number>` and any explicit `device:<name>` values
    present in that artifact; do not derive keys from markers
    or prose.

## Typed entity columns (edges as columns)

The instance may carry typed columns on `incident` — a device
name, an interface, an IP, a service. Health ServiceNow discovers
their names once and records them in
`health/metadata-servicenow.json` as `servicenow.entity_fields`
(`device`, `interface`, `ip`, `service`; each a column name such
as `u_device_name`, or null when the instance has none). A ticket
with the device in its typed column is a ticket every reader can
join on without parsing prose. Filling that column is your job on
every create and update that names one entity.

Before the mutation, on `upsert_incident`, `append_incident_work_notes`,
and `resolve_incident`:

1. `read_file` `health/metadata-servicenow.json` if it exists.
   Absent, or every `entity_fields` value null → skip this section;
   write nothing extra; do not invent a column name.
2. Take `record.entity` from the request. Absent or null → if
   `record.affected_devices` has exactly one name, that name is
   `entity.device`; two or more → no typed columns (a column holds
   one value; the others stay in prose and in `keys`).
3. `entity.device` must be a `devices[].name` in
   `inventory/prod.json`, `entity.service` a `services[].name` in
   `inventory/services.json`. A name that matches neither → fail
   the request (`status=failed`, reason names the value). Do not
   fix the spelling yourself.
4. Build `extra_fields`: one `<column>: <value>` per non-null
   `entity` member whose `entity_fields` column is non-null.
   Write `interface` only when `device` is also present.
   Nothing to write → omit `extra_fields`.

```text
snow_update_incident(incident_number="INC0085085",
  work_notes="…",
  extra_fields={"u_device_name": "WAN-04", "u_interface_name": "GigabitEthernet6"})
```

`extra_fields` is accepted by `snow_create_incident`,
`snow_update_incident`, `snow_create_change`, `snow_update_change`
(connector ≥ 1.2.0). Keys must start with `u_`; the connector
rejects anything else and writes nothing. If the tool answers that
`extra_fields` is unknown, the connector is older: complete the
mutation without it, and put `typed columns: connector has no
extra_fields` in the result `message`. Never put the device name
into `cmdb_ci` as a substitute — that is a reference field and
will not resolve.

Read back with `snow_query_table` (step 9). A column that reads
back different from what you sent is a failure of this step,
reported in the result; the notes you appended still stand.

The result's `keys` gain `device:<name>` (and
`interface:<device>/<interface>`, `service:<name>`) from
`record.entity` — those are explicit identity fields.

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
