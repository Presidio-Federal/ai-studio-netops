# Modernization Agents

Refresh: what is in the estate, what Cisco says about it, and what to
do next. Identity comes from SoT and inventory as written — device
type, node definition, serial PID. Never a hostname-to-SKU map.

Modernization interviews and plans. Modernization-Lifecycle collects
vendor research. They share one estate table.

## Agents

| Agent | Role |
|-------|------|
| Modernization | Identity, operator choices, plan |
| Modernization-Lifecycle | Hardware EoX, software train, PSIRT, NVD, CCW |

## Estate

`state/lifecycle.json` is one row per evidence product id. The
operator’s selected SKU lives only on that row. Headline,
`next_action`, `guidance`, `recommendations[]`, and
`lifecycle/roadmap.md` **are** the plan.

Lifecycle writes Cisco facts onto matching `pid` rows and dumps
detail at `lifecycle/items/<pid>.json`. It does not invent a
replacement SKU. Family-only bulletin becomes an ask on the row.
`recommended_software` comes from Cisco software EoX / PSIRT, never
from a CCW part number. Empty hardware EoX on a virtual PID is
unavailable research, not a failed estate.

## How a refresh runs

1. Modernization seeds identity from inventory / NetBox fields as
   written.
2. Missing or expired research: `Run the Modernization Lifecycle
   check only.` Invoke and continue — do not wait.
3. Lifecycle merges research and writes the per-PID dump.
4. Plan invoke: Modernization asks why, then the choice. After
   answers, it writes `recommendations[]` and the roadmap (order,
   stage, deploy, schedule, cutover).

A plan invoke may **read** [Health Agents](health-agents.md)
`state/health.json`. It does not collect telemetry and does not
write the health chart.
