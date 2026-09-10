# Change and Test Agents

Day-two and design acts prove the change on the twin before prod.
These agents size the work and record risk. The actual suite run
is [Compliance Test](compliance-agents.md). They do not replace
[Health Agents](health-agents.md) or [SoT and Twin](sot-and-twin-agents.md).

## Agents

| Agent | Role |
|-------|------|
| Network Design | Size a branch on the twin. Writes the test request and a deploy summary (ticket slot for ServiceNow). |
| Compliance Author | Turns compliance intel or a named ask into a check in git. |
| Compliance Test | Triggers `test.yml`, records risk, writes the timestamped result. |

## What a successful change looks like

Apply on twin IOS-XE → Compliance Test → approve → prod. Design
follows the same gate: size on the twin, test, then ServiceNow
logistics.

Compliance Test writes `testing/<stamp>.json` and
`state/testing.json` after every run. `state/compliance.json` is
only the latest run whose suites include compliance — not a copy
of a reachability run. Device score is Compliance Test, not the
intel scan.

A passing test on a drifted twin is not evidence. Fidelity belongs
in the [SoT and Twin](sot-and-twin-agents.md) gate.

Network Design does not file warehouse or catalog requests itself.
[ServiceNow Agents](servicenow-agents.md) own tickets.

New checks and NIST coverage live on
[Compliance Agents](compliance-agents.md).
