# SoT and Twin Agents

The systems of record stay outside the workspace. These agents keep
the chart honest: what devices exist, what config GitHub has, and
whether the lab still matches prod.

| System | Role |
|--------|------|
| GitHub | Full running-configs. Sync + Actions collect from IOS-XE. |
| NetBox | Devices, types, interfaces, IPs, cables — enough to rebuild CML. Not a second config dump. |
| Twin (CML) | Bootstrap → OOB → IOS-XE, then push GitHub configs. |

## Agents

| Agent | Role |
|-------|------|
| Onboard | Workspace control board. Turns inventory / config sync / NetBox planes on. Reset flips sync and NetBox off and runs them again. |
| Ops Network Sync | Collects access inventory (`inventory/prod.json`, `inventory/dev.json`) and runs the GitHub Actions jobs (collect, deploy twin, reconcile, drift). |
| Ops NetBox SoT | Ingests seed from prod inventory into NetBox. Modes: bootstrap (create missing), audit (compare, no writes), reconcile (apply approved diffs). A “refresh” is audit — it must not overwrite curated NetBox. |
| Digital Twin | Owns deploy and reconcile of the lab. Gathers workspace + NetBox + config presence, prints a plan, waits for go, then Sync runs the Actions. |

## What readers use

- `inventory/prod.json` — published access snapshot (RESTCONF ports,
  identity). Health Device reads the port from here.
- `inventory/infra-sot.json` — NetBox ids, interfaces, cables,
  software version.
- `state/network-sync.json` — this collect only; last-known-good
  snapshot is preserved on a failed collect.
- `state/netbox.json` — mode, counts, seed match.
- `state/workspace.json` — Onboard only: which planes are up.

The twin is a gate, not a planner. A passing test on a drifted lab is
not evidence. Fidelity cites Sync drift — it does not copy configs
into state.
