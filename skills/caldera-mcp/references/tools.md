# Tools this visit calls

Caldera only. Names from `docs/mcp-index.md`. Do not call CML,
IOS-XE, Elastic, or Splunk on this visit.

| Tool | Use |
|------|-----|
| `caldera_status` | `GET /api/v2/health`. |
| `caldera_get` | List reads. Pass `include`. |
| `caldera_write` | `POST` an adversary, a source, or an operation. `PATCH` an operation state. |
| `caldera_delete` | Only when the operator names the object and says delete. |

| What | Path | include |
|------|------|---------|
| Agents | `/api/v2/agents` | `paw,host,group,platform,last_seen,trusted,host_ip_addrs` |
| Adversaries | `/api/v2/adversaries` | `adversary_id,name,atomic_ordering` |
| Abilities | `/api/v2/abilities` | `ability_id,name,tactic,technique_id,technique_name` |
| Planners | `/api/v2/planners` | `id,name` |
| Sources | `/api/v2/sources` | `id,name` |
| One source | `/api/v2/sources/{id}` | `id,name,facts` |
| Operations | `/api/v2/operations/summary` | `id,name,state,start,group,adversary` |
| Links | `/api/v2/operations/{id}/links` | `id,status,paw,host,finish,ability` |

Drop any field named `command`, `plaintext_command`, `output`, or
`executor`. A fact you keep has `trait` and `value` only.

Operation body:

```json
{
  "name": "<group>-<YYYYMMDDTHHMMZ>",
  "group": "<group>",
  "autonomous": 1,
  "planner": { "id": "<planner whose name is atomic>" },
  "adversary": { "adversary_id": "<id from campaigns/adversaries/relevant.json>" },
  "source": { "id": "<id>" }
}
```

`PATCH` body is `{"state":"paused"}`, `running`, or `finished`, and
only when the operator says pause, resume, or finish.
