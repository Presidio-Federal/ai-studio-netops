# Change and Test Agents

Day-two and design acts prove the change on the twin before prod.
These agents size the work, run suites, and record risk. They do not
replace [Health Agents](health-agents.md) or [SoT and Twin](sot-and-twin-agents.md).

## Agents

| Agent | Role |
|-------|------|
| Network Design | Size a branch on the twin. Writes the test request and a deploy summary (ticket slot for ServiceNow). |
| Compliance Author | Turns compliance intel or a named suite into tests. |
| Compliance Test | Triggers the run, records risk, writes the timestamped result. |

## What a successful change looks like

Apply on twin IOS-XE → Compliance Test → approve → prod. Design follows the same
gate: size on the twin, test, then ServiceNow logistics.

Compliance Test writes `testing/<stamp>.json` and `state/testing.json` after
every run. `state/compliance.json` is only the latest run whose
suites include compliance — not a copy of a reachability run. Device
score is Compliance Test, not the intel scan.

Network Design does not file warehouse or catalog requests itself.
[ServiceNow Agents](servicenow-agents.md) own tickets.
