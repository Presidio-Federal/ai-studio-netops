# ServiceNow Agents

Ticketing and logistics for design and incident work. These agents
file and track cases. They are not the ServiceNow **health** watch —
that is [Health ServiceNow](health-agents.md), which is read-only and
does not vote vitals.

## Agents

| Agent | Role |
|-------|------|
| ServiceNow | Open cases, history, and the request queue. Writes `state/servicenow.json` and `servicenow/cases/`. |
| ServiceNow Operator | Operator-facing path over the same instance. |

The MCP cannot create `change_request`. A planned Network Change agent
was dropped for that reason. Catalog REQs are the create path that
exists.

Health ServiceNow never writes `state/servicenow.json`. ServiceNow
never writes `health/servicenow/<stamp>.json`.
