# Modernization Agents

Refresh is the fifth network-ops act: take estate identity from
inventory / SoT, research Cisco lifecycle on the same table, then
write a plan when the operator asks.

Prompts and skills for these agents are **not in this checkout
yet**. The contract is the `workspace-handoff` catalog.

## Intended agents

| Agent | Skill | Owns |
|-------|-------|------|
| Modernization | `modernization` | Identity on `state/lifecycle.json`, operator SKU, plan invoke (`recommendations[]`, `lifecycle/roadmap.md`) |
| Modernization-Lifecycle | `modernization-lifecycle` | Cisco research merge onto the same table; per-PID dumps under `lifecycle/items/<pid>.json` |

Both agents merge `state/lifecycle.json`. Modernization writes
identity, guidance, and the plan. Lifecycle writes hardware EoX,
software train, PSIRT, NVD, and CCW onto matching `pid` rows and
does not overwrite higher-reliability identity.

## Workspace files

| Path | Kind | Writer |
|------|------|--------|
| `state/lifecycle.json` | state | Modernization and Modernization-Lifecycle |
| `lifecycle/items/<pid>.json` | observation | Modernization-Lifecycle |
| `lifecycle/roadmap.md` | observation | Modernization (after operator answers) |

Rows are keyed by evidence product id (`device_type` /
`node_definition` / serial PID) — never hostname-to-SKU. The
operator’s selected replacement lives only on the table row, not on
the per-PID dump.

Modernization may **read** `state/health.json` on a plan invoke. It
does not write the health chart.

## How they split work

1. Modernization seeds identity from SoT / inventory.
2. If a row is missing EoX or expired and Lifecycle is attached,
   Analyzer-style dispatch is: `Run the Modernization Lifecycle check
   only.` — invoke and continue; do not wait.
3. Lifecycle merges research onto matching `pid` and writes
   `lifecycle/items/<pid>.json`.
4. On a plan invoke, Modernization writes `recommendations[]` and
   `lifecycle/roadmap.md` after `guidance.answers` is non-empty.

When these prompts land in `agents/`, this page will point at the
files.
