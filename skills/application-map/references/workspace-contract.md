# Produce — Application Map

Paths, Kind, catalog: **`workspace-handoff`**. Write schema lives
in this skill. Do not `execute_command`. Do not invent files.
Persist with `write_file` on the catalog path.

| File | Kind | When |
|------|------|------|
| `inventory/applications.json` | snapshot | Every run where the CMDB moved (`source_updated_at` differs from the prior file) or no prior exists. Replace in full. |

Do not write `inventory/prod.json`, `inventory/services.json`,
`health/`, `state/`, `servicenow/`, or anything under
`automations/`. Do not write `relations[]`; the Relationship agent
turns `service`, `hosts[]`, and `depends_on[]` into `intended`
edges and drift.

Read only the four paths in `references/map.md`. Do not read
`inventory/infra-sot.json`, a health stamp, or
`state/relationships.json`.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of `application:<name>` per row, `service:<service>` per non-null registry-matched service, and `device:<host>` per `prod.json`-matched host; use `[]` when there are none. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. A `service_ci` that did not match the registry and a host in `hosts_unmapped[]` never become keys.
