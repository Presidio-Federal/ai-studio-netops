# Caldera tools

Names from `docs/mcp-index.md`. Four tools. Paths are Caldera API v2.

| Tool | Use |
|------|-----|
| `caldera_status` | `GET /api/v2/health`. Returns `{ok, application, version, access, plugins}`. |
| `caldera_get` | `GET` an allowlisted path. Pass `include` on every list. Returns `{ok, path, status_code, data}`. |
| `caldera_write` | `POST`, `PUT`, or `PATCH`. Returns `{ok, method, path, status_code, data}`. |
| `caldera_delete` | `DELETE` an object path. Returns `{ok, path, status_code, data}`. |

`POST /api/v2/operations/{id}/report` is a read. Call it with
`caldera_write`. Prefer the links list below. If a body contains a
command field, drop that field before you write or reply.

## Reads

Pass `include` so the payload stays small. If the server still
returns a command field, ignore it.

| What | Path | include |
|------|------|---------|
| Agents | `/api/v2/agents` | `paw,host,group,platform,architecture,last_seen,trusted,exe_name,host_ip_addrs` |
| Adversaries | `/api/v2/adversaries` | `adversary_id,name,description,atomic_ordering` |
| One adversary | `/api/v2/adversaries/{id}` | `adversary_id,name,description,atomic_ordering` |
| Abilities | `/api/v2/abilities` | `ability_id,name,tactic,technique_id,technique_name` |
| Planners | `/api/v2/planners` | `id,name` |
| Sources | `/api/v2/sources` | `id,name` |
| One source | `/api/v2/sources/{id}` | `id,name,facts` |
| Operation summary | `/api/v2/operations/summary` | `id,name,state,start,group,adversary,planner,source` |
| Links | `/api/v2/operations/{id}/links` | `id,status,paw,host,decide,finish,ability` |

A fact you keep has `trait` and `value` only.

## Writes that stay on the allowlist

Confirm with a line that names the group and says to run, except
where `run.md` says the run line already is that confirm.

| Action | Call |
|--------|------|
| Create an operation | `caldera_write` `POST /api/v2/operations` |
| Pause, resume, or finish | `caldera_write` `PATCH /api/v2/operations/{id}` body `{"state":"paused"}` or `running` or `finished` |
| Update source facts | `caldera_write` `PUT /api/v2/sources/{id}` |

Operation body, these fields only:

```json
{
  "name": "<group>-traffic",
  "group": "<group>",
  "autonomous": 1,
  "planner": { "id": "<planner whose name is atomic>" },
  "adversary": { "adversary_id": "<id>" },
  "source": { "id": "<id>" }
}
```

`autonomous` `1` starts the operation. `group` is the agent group
from the workspace, not an empty string.

Source facts for a traffic run use `app.url` and `remote.host.ip`.
Values come from `inventory/network.json`. Do not add file-extension
facts or a malicious-url fact.

## Rejected by the server

Do not call these. A 4xx here is not a retry.

- `/api/v2/config/{name}`
- `/api/v2/deploy_commands` and `/api/v2/deploy_commands/{ability_id}`
- `/api/v2/payloads` and `/api/v2/payloads/{name}`
- `POST`, `PUT`, `PATCH`, or `DELETE` on `/api/v2/abilities`
- `PATCH /api/v2/operations/{id}/links/{link_id}`
