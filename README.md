# AI Studio NetOps

This fleet is built to run like an ER, not like one clever intern
who remembers the whole hospital. The shared Studio workspace is
the **patient chart**. Agents share those files, not each other’s
prompts. GitHub holds running-configs. NetBox holds devices,
interfaces, IPs, and cables so the lab can be rebuilt. CML is the
twin.

A specialist opens the chart, does one job, writes the note, and
leaves. The next person starts from the record. That is how you
move fast without losing the plot.

## Why the chart exists

Here are the challenges I experienced when trying to deploy a
fleet of agents to optimize an entire business process, not just
an individual task.

A single task is easy. Summarize this log. Open this ticket. One
chat, one tool, you can live with a messy thread. An end-to-end
process is not that. Health, inventory, design, change, test, and
refresh all have to line up — and they happen in **different**
conversations, on **different** days, often by **different**
agents. The moment I put that in one window, it fell apart.

- **The god agent.** I asked one conversation to collect, diagnose,
  and change config. Context filled with tools it should never
  touch. It started guessing paths and mixing jobs.
- **Recap as state.** I handed the next agent a story from the last
  chat. Each retell drifted. Nobody could point at a file and say
  “this is what we knew at 14:00.”
- **Token burn.** Every invoke dragged four telemetry dumps, last
  week’s thread, and another agent’s prompt into the window. Cost
  went up. Accuracy went down. The model was judging a blend it
  was told, not a source it queried.
- **No owner.** Two agents wrote the same board. Someone invented a
  scratch file so a script could join git. The last write won.
  Concurrent runs clobbered the diagnosis.
- **Observation, opinion, and change in one turn.** Labs got treated
  as a diagnosis. A diagnosis got treated as a merge. I could not
  tell who was allowed to touch the box.
- **“It’s fine” from one quiet source.** No critical syslog was not
  a healthy WAN. Missing logs were not a down device. Stale data
  sat next to live data with no date on either.
- **Couldn’t resume.** If the chat died, the case died. I had to
  re-explain the estate instead of opening the chart.
- **Prompts that contained the whole hospital.** Every specialist
  carried everyone else’s playbook. They were unmaintainable, and
  MiniMax could not follow them.

The chart is how I got out of that. One fact, one file, one writer.
New conversation on every invoke — that is a feature. Initial
context stays small. Memory lives on disk. Nurses write what they
observed. The attending writes what we think. Ops ships through
git. You can start any act if the prior files already exist.

## What you have to accept

This only works if the underlying change process uses these
workflows. If someone changes a device outside GitOps, the next
apply from git `main` will overwrite it. Same for a lab box that
was clicked into by hand — the twin is rebuilt from GitHub and
NetBox, not from memory.

The chart is only as current as the last visit. Stale notes are
labeled stale; they are not live truth. Readers have to read the
file instead of re-collecting. If you attach every agent to every
chat, you are back to the god agent.

## What the fleet does

1. **SoT** — Collect inventory and configs, ingest NetBox, deploy the twin.
2. **Day-two change** — Network Ops: evidence → git `dev` → GitOps → PR `main`.
3. **Design** — Read the chart. Roadmap at hardware, software, configuration, and compliance. Warehouse check; coordinate on ask.
4. **Ticket** — ServiceNow case → Network Ops → test → PR `main`.
5. **Refresh** — Estate identity from SoT, Cisco research, then a plan.

Compliance Test sits on every act that claims success. Health is
the watch that runs beside those acts. Config text stays in git.
NetBox is not a second running-config.

## Agent families

| Family | What they do |
|--------|----------------|
| [Health Agents](documentation/health-agents.md) | Patient chart: one-source nurse visits, attending assessment, Ops/Design read the chart |
| [Modernization Agents](documentation/modernization-agents.md) | Ingest estate with ranked confidence; plan with cost and timelines |
| [SoT and Twin Agents](documentation/sot-and-twin-agents.md) | Ops Network Sync inventory, Ops NetBox SoT, and the CML lab that must match prod |
| [Change and Test Agents](documentation/change-and-test-agents.md) | Design: long-horizon roadmap + warehouse; Network Ops: git `dev` config change; Compliance Test scores the run |
| [Compliance Agents](documentation/compliance-agents.md) | Intel gaps, author a check, run the suite |
| [ServiceNow Agents](documentation/servicenow-agents.md) | Lab cases and named-slice trends — not the health watch |
| [Network Ops](documentation/network-ops.md) | Operate: evidence + SoT → git `dev` → merge `main` |

## How they coordinate

Each agent writes only the files it owns. Health nurses write visit
stamps. Health Analyzer writes `state/health.json`. Ops Network Sync
writes inventory. Ops NetBox SoT writes the infra snapshot. Network
Ops writes `state/network-ops.json`. Modernization Analysis and
Lifecycle share the estate table. Compliance Test writes run results.
The catalog in `workspace-handoff` is the contract.

Health Analyzer does not recommend. Modernization fills Cisco
dates, PSIRTs, and replacement SKUs. Network Design turns that
chart into hardware, software, configuration, and compliance
work, then checks the warehouse. Network Ops ships running-config
fixes through git. Compliance proposes intel; Compliance Test
scores the run.
