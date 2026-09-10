# Change procedure

Verified change tools exist: `snow_find_changes`, `snow_get_change`, `snow_create_change`, `snow_update_change`. Change writes are supported. Do not substitute a catalog order. Never call a REQ or RITM a CHG.

`snow_query_table` can read `change_request` but dedicated find/get tools are required when they exist.

Change connector fields that matter: `number`, `sys_id`, `short_description`, `description`, `justification`, `implementation_plan`, `risk_impact_analysis` (alias `risk_and_impact_analysis`), `test_plan`, `backout_plan`, `state`, `risk`, `impact`, `type`, `start_date`, `end_date`, `work_notes`, `correlation_id` / `external_id`, `category`, `updated_at`.

`snow_update_change` appends `work_notes` as a journal entry. There is no change `close_notes` parameter; closing notes go in `work_notes`.

Connector state names include `new`, `assess`, `authorize`, `scheduled`, `implement`, `review`, `closed`, `canceled`. Risk: `very high`, `high`, `moderate`/`medium`, `low`, `none`. Impact: `high`/`1`, `medium`/`2`, `low`/`3`. Type: `standard`, `normal`, `emergency`.

`snow_find_change_tasks` and `snow_upsert_change_task` exist. Do not create a CTASK as a second record for the same request.

In-scope only: `servicenow/metadata-lab.json` marker / match terms
plus inventory labels. Rows that do not match are out of scope.

## Procedure

1. Validate the ServiceNow request (`schema=servicenow-request/v1`).
2. Read the referenced change plan from `source_refs`.
3. Require:
   - `request_id`
   - `correlation_id`
   - `idempotency_key`
   - `objective`
   - `short_description`
   - business justification
   - affected devices and scope
   - implementation plan
   - risk and impact analysis
   - test plan
   - backout plan
   - requested implementation window when applicable (`start_date` / `end_date`)
4. If validation or deployment evidence is referenced, read it and use only facts it contains. Never invent test or rollback evidence.
5. Verify mutation authorization. Production change creation, approval, scheduling, marking implemented, and closing a change require explicit human or conversation authorization. Policies `append-validation-result-v1` and `append-deployment-result-v1` may append notes only.
6. Search for an existing change by idempotency key:

   ```text
   snow_find_changes(correlation_id=<idempotency_key>, active_only=true)
   snow_find_changes(search=<idempotency_key>, active_only=true)
   ```

   On create, set `correlation_id` / `external_id` to the idempotency key. Also stamp:

   ```text
   [AUTOMATION-ID:<idempotency_key>]
   [CORRELATION-ID:<correlation_id>]
   [REQUEST-ID:<request_id>]
   ```

7. Update exactly one match (`snow_update_change` with `number` or `change_id`) or create one when authorized (`snow_create_change`).
8. Treat multiple matches as an error. Create nothing.
9. Read the record back:

   ```text
   snow_get_change(number=<CHG…>)
   ```

10. Verify number, sys_id, state, `correlation_id`, and requested material fields (plans, justification, appended validation/deployment notes when applicable).
11. Write the normalized result per `references/workspace-contract.md`.

## Operation mapping

| Request operation | Tool | Notes |
|---|---|---|
| `find_change` | `snow_find_changes` | No mutation. |
| `get_change` | `snow_get_change` | Requires `record.number` or `record.sys_id`. |
| `upsert_change` | find, then create or update | Human/conversation authorization. Not policy-authorized. |
| `append_change_validation` | `snow_update_change(work_notes=...)` | Facts from validation evidence only. |
| `append_change_deployment` | `snow_update_change(work_notes=...)` | Facts from deployment evidence only. |
| `close_change` | `snow_update_change(state="closed", work_notes=...)` | Explicit human/conversation authorization. Close notes required in `work_notes`. |

## Rules

- Never claim approval. There is no approve tool. `cab_required` is a returned field, not an action.
- Never approve a record.
- Never advance a record to `scheduled`, `implement`, `closed`, or another protected state without explicit authorization for that transition.
- Never invent test or rollback evidence.
- Never substitute a catalog request.
- Copy plan fields from the change plan; do not invent them.
- One change record per request.
