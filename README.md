# AI Studio NetOps

Move fast while removing risk. This is a fleet of AI Studio agents that
operate a production network: collect what is running, prove change on a
digital twin, watch the path and the devices, and plan refresh from
vendor lifecycle — without one agent doing every job.

GitHub holds running-configs. NetBox holds devices, interfaces, IPs, and
cables so the lab can be rebuilt. CML is the twin. The shared Studio
workspace is the chart the agents read and write. Agents share those
files, not each other’s prompts.

## What the fleet does

Start any act if the prior workspace files already exist.

1. **SoT** — Collect inventory and configs, ingest NetBox, deploy the twin.
2. **Day-two change** — Network Ops: evidence → git `dev` → GitOps → PR `main`.
3. **Design** — Read the chart. Roadmap at hardware, software, configuration, and compliance. Warehouse check; coordinate on ask.
4. **Ticket** — ServiceNow case → Network Ops → test → PR `main`.
5. **Refresh** — Estate identity from SoT, Cisco research, then a plan.

Compliance Test sits on every act that claims success. Compliance
intel finds gaps; it does not score devices. Health is the watch
that runs beside those acts.

A fact lives in one workspace file, has one writer, and is cited
downstream. Producers collect one source. Summarizers own one state
file (findings, not plans). Network Ops implements running-config
change through git. Network Design owns the four-layer roadmap.

## Agent families

| Family | What they do |
|--------|----------------|
| [Health Agents](documentation/health-agents.md) | Watch the path, syslog, devices, and lab tickets; assess and trend |
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
Lifecycle share the estate table. Compliance Test writes run results. The catalog
in `workspace-handoff` is the contract.

Health Analyzer does not recommend. Modernization fills Cisco
dates, PSIRTs, and replacement SKUs. Network Design turns that
chart into hardware, software, configuration, and compliance
work, then checks the warehouse. Network Ops ships running-config
fixes through git. Compliance proposes intel;
Compliance Test scores the run.
