# AI Studio NetOps

This fleet treats the Studio workspace as a **patient chart**: a
shared case record, not a chain of agent-to-agent recaps.

Agents do not pass operational state to other agents. They
contribute structured knowledge to the case. Continuity lives in
the files and the schemas, not in the previous conversation.

The architecture is in
[Patient Chart Multi-Agent Architecture](documentation/patient-chart.md).
Health is the first family that implements it in prompts and
schemas: [Health Agents](documentation/health-agents.md).

GitHub owns the network configuration. NetBox owns the
infrastructure record — devices, interfaces, IPs, and cables. CML
is the digital twin used to rebuild and test the environment.

## Why the chart exists

A single task is usually manageable. Summarize a log. Open a
ticket. Check an interface.

An end-to-end network process is different. Health, inventory,
design, change, testing, compliance, and modernization happen in
different conversations, on different days, and sometimes with
different models. Continuity cannot depend on `Agent A → Agent B`
or on copying Splunk, ThousandEyes, and device dumps into the
workspace.

That is where I ran into the problems this repo is designed around.

- **The god agent.** One conversation collected, diagnosed, and
  changed config. Context filled with tools it should never have
  needed.
- **Recap as state.** Each retelling drifted. Nobody could point
  to a file and say what we knew at 14:00.
- **Token burn.** Telemetry dumps and other agents’ instructions
  rode along in every window.
- **No clear owner.** Concurrent writes clobbered the diagnosis.
- **Observation and action mixed.** A lab result was treated as a
  diagnosis; a diagnosis was treated as approval to change
  production.
- **Silence looked like health.** No critical syslog did not mean
  the WAN was healthy. Stale sat beside live without enough
  context.
- **The process could not resume.** When the conversation ended,
  the case ended with it.
- **Every prompt contained the whole hospital.** Specialists
  carried everyone else’s instructions.

The chart is how I got out of that. The workspace has a catalog of
files. Each file has an owner, a schema, and defined readers. A
specialist writes what materially changed in its domain. An
analyzer interprets those observations. Downstream agents act from
the record.

A new conversation on every invoke is a feature. The prompt stays
small. The durable context lives in the workspace. The catalog is
`workspace-handoff`.

## What you have to accept

This approach only works if the sources of truth stay
authoritative.

If someone changes a device outside the GitOps path, the next
approved apply from GitHub may overwrite that change. If someone
clicks changes into the lab by hand, the digital twin does not
treat the lab as the source of truth. It is rebuilt from the
approved inventory, NetBox data, and configuration sources.

The chart is only as current as its last visit. A stale note is
useful history, not live truth. That is why the records include
timestamps, freshness, status, and ownership.

Agents should not all be attached to every conversation. That
recreates the god agent. Each agent gets the tools for its job.
The workspace carries information between jobs.

## What the fleet does

1. **Onboard** coordinates the initial inventory and source-of-truth process.
2. **Network Sync** collects inventory and configuration evidence and runs the GitHub Actions path.
3. **NetBox SoT** maintains the infrastructure record: devices, interfaces, IPs, and cables.
4. **Digital Twin** builds or reconciles the CML environment from those approved sources.
5. **Health Monitor / Device / ServiceNow** query one source, compare to the last visit, and write a structured observation when that plane has something to record.
6. **Health Analyzer** interprets those observations as SOAP on `state/health.json`.
7. **Network Ops** reads the chart and ships running-config through git.
8. **Network Design** handles proposed changes and creates the testing handoff.
9. **Test** proves the change and records the risk and result.
10. **ServiceNow** owns ticket creation and updates.
11. **Modernization** builds the roadmap from infrastructure, lifecycle, and support data.

## Agent families

| Family | What they do |
|--------|----------------|
| [Architecture](documentation/patient-chart.md) | Case record, schemas, material change, SOAP at analysis |
| [Health Agents](documentation/health-agents.md) | Specialist lab slips + attending SOAP |
| [SoT and Twin Agents](documentation/sot-and-twin-agents.md) | Onboard, Network Sync, NetBox SoT, Digital Twin |
| [Network Ops](documentation/network-ops.md) | Read the chart, recommend, ship running-config through git |
| [Change and Test Agents](documentation/change-and-test-agents.md) | Design handoff and Compliance Test risk/result |
| [Compliance Agents](documentation/compliance-agents.md) | Intel gaps, author a check, run the suite |
| [ServiceNow Agents](documentation/servicenow-agents.md) | Tickets and named-slice trends — not the health watch |
| [Modernization Agents](documentation/modernization-agents.md) | Estate identity, lifecycle research, roadmap |
