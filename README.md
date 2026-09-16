# AI Studio NetOps

Multi-agent systems are good at breaking a large task into smaller
jobs. The trouble starts when those jobs need to come back together.

This is especially true when a frontier model delegates work to
specialized agents, and those agents use different tools, run at
different times, or use different models. The individual tasks
might work perfectly well, but the overall result can still fall
apart if the next agent does not know what happened before it
arrived.

This repo is built around a simple idea: treat the shared Studio
workspace like a patient chart.

I started thinking about emergency rooms because the comparison is
useful. An ER has specialists, shift changes, interruptions,
delayed test results, and a lot of information moving through the
system. Nobody expects every nurse or doctor to remember the entire
history of every patient. They rely on the chart.

That is the same problem this fleet is trying to solve for network
operations.

A specialist opens the chart, does one job, records what it found,
and leaves. The next specialist can start from that record without
needing the previous conversation or a perfectly timed handoff.

The shared workspace is the durable handoff. Agents share the files
and the schemas, not the entire contents of each other’s prompts.

GitHub owns the network configuration. NetBox owns the
infrastructure record — devices, interfaces, IPs, and cables. CML
is the digital twin used to rebuild and test the environment.

## Why the chart exists

A single task is usually manageable. Summarize a log. Open a
ticket. Check an interface. One conversation, one tool, and a messy
thread may be good enough.

An end-to-end network process is different. Health, inventory,
design, change, testing, compliance, and modernization all need to
work together. They happen in different conversations, on different
days, and sometimes with different agents or models.

That is where I ran into the problems this repo is designed around.

- **The god agent.** I asked one conversation to collect
  information, diagnose the problem, and change the configuration.
  Its context filled with tools it should never have needed, and it
  started mixing jobs.
- **Recap as state.** I handed the next agent a summary from the
  previous conversation. Each retelling introduced some drift.
  Nobody could point to a file and say, “This is what we knew at
  14:00.”
- **Token burn.** Every invocation carried telemetry dumps, old
  context, and instructions from other agents into the window. Cost
  went up, and the model had to reason over a blend of information
  instead of reading the source it actually needed.
- **No clear owner.** Multiple agents wrote to the same board, or
  someone created a scratch file so another process could join the
  data. The last write won, and concurrent runs could overwrite the
  diagnosis.
- **Observation and action got mixed together.** A lab result
  started being treated like a diagnosis. A diagnosis started being
  treated like approval to change production. It became difficult
  to tell who was allowed to touch the device.
- **Silence looked like health.** No critical syslog did not mean
  the WAN was healthy. Missing logs did not mean the device was
  down. Stale information sat beside live information without
  enough context to tell them apart.
- **The process could not resume.** If the conversation ended, the
  case effectively ended with it. I had to explain the environment
  again instead of opening the current record.
- **Every prompt contained the whole hospital.** Each specialist
  carried everyone else’s instructions. The prompts became
  difficult to maintain, and smaller models had trouble following
  them.

The chart is how I got out of that.

The workspace has a catalog of files. Each file has an owner, a
schema, and defined readers. A specialist writes the observation it
owns. A different agent may summarize those observations into
shared state. Metadata records when the information was collected
and whether it is still current.

A new conversation on every invoke is a feature. The prompt stays
small, while the durable context lives in the workspace.

## What the chart does

The patient chart is not a memory dump and it is not a collection
of transcripts. It is a set of structured records that let agents
continue work without carrying the entire history in their prompts.

A health specialist might write a dated observation from Splunk,
ThousandEyes, IOS-XE, or ServiceNow. The Health Analyzer reads
those observations and writes the health rollup. The Network Ops
agent then interprets the chart and recommends what should happen
next.

That separation matters.

The specialist reports what it observed. The analyzer determines
what is current and what is stale. The attending agent interprets
the overall situation. A design or testing agent handles the next
authorized step.

The same pattern applies outside health. Network Sync owns the
configuration inventory and GitHub Actions results. NetBox SoT
owns the infrastructure snapshot. Digital Twin owns the CML
topology. Test owns test results and risk. ServiceNow owns ticket
creation and updates.

The file is the handoff. The schema tells the next agent what the
file means. The catalog is `workspace-handoff`.

This does not mean every agent can run independently without any
coordination. Required inputs still have to exist, and stale or
failed inputs can block a dependent action. The point is that the
agent can determine that from the record instead of guessing from
a conversation.

## What you have to accept

This approach only works if the sources of truth are treated as
authoritative.

If someone changes a device outside the GitOps path, the next
approved apply from GitHub may overwrite that change. If someone
clicks changes into the lab by hand, the digital twin does not
treat the lab as the source of truth. It is rebuilt from the
approved inventory, NetBox data, and configuration sources.

The chart is also only as current as its last visit. A stale note
is still useful history, but it is not live truth. That is why the
records include timestamps, freshness rules, status, and ownership.

The other important rule is that agents should not all be attached
to every conversation. That recreates the god agent problem. Each
agent should have the tools and instructions needed for its
responsibility, and the workspace should carry the information
between responsibilities.

## What the fleet does

The fleet separates the major network-operations responsibilities:

1. **Onboard** coordinates the initial inventory and source-of-truth process.
2. **Network Sync** collects inventory and configuration evidence and runs the GitHub Actions path.
3. **NetBox SoT** maintains the infrastructure record: devices, interfaces, IPs, and cables.
4. **Digital Twin** builds or reconciles the CML environment from those approved sources.
5. **Health Monitor** collects specialist observations from individual health planes.
6. **Health Analyzer** rolls those observations into `state/health.json` and tracks freshness.
7. **Network Ops** reads the health chart, correlates the evidence, and recommends a next step.
8. **Network Design** handles proposed changes and creates the testing handoff.
9. **Test** proves the change and records the risk and result.
10. **ServiceNow** owns ticket creation and updates.
11. **Modernization** builds the roadmap from infrastructure, lifecycle, and support data.

The goal is not to make one agent responsible for the entire
hospital. The goal is to let each specialist do its job while
keeping the patient record coherent.

## Agent families

| Family | What they do |
|--------|----------------|
| [Health Agents](documentation/health-agents.md) | One-source visits, attending rollup, Ops/Design read the chart |
| [SoT and Twin Agents](documentation/sot-and-twin-agents.md) | Onboard, Network Sync, NetBox SoT, Digital Twin |
| [Network Ops](documentation/network-ops.md) | Read the chart, recommend, ship running-config through git |
| [Change and Test Agents](documentation/change-and-test-agents.md) | Design handoff and Compliance Test risk/result |
| [Compliance Agents](documentation/compliance-agents.md) | Intel gaps, author a check, run the suite |
| [ServiceNow Agents](documentation/servicenow-agents.md) | Tickets and named-slice trends — not the health watch |
| [Modernization Agents](documentation/modernization-agents.md) | Estate identity, lifecycle research, roadmap |
