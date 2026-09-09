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
2. **Day-two change** — Apply on twin IOS-XE, test, approve, then prod.
3. **Design** — Size a branch on the twin, test, ServiceNow logistics.
4. **Ticket** — ServiceNow case → twin → test → prod.
5. **Refresh** — Estate identity from SoT, Cisco research, then a plan.

Test and compliance sit on every act that claims success. Health is the
watch that runs beside those acts.

A fact lives in one workspace file, has one writer, and is cited
downstream. Producers collect one source. Summarizers own one state
file (findings, not plans). Network Ops reads the chart. Later Dev,
Sec, and Ops lane agents will own proposals and the twin gate.

## Agent families

| Family | What they do |
|--------|----------------|
| [Health Agents](documentation/health-agents.md) | Watch the path, syslog, devices, and lab tickets; assess and trend |
| [Modernization Agents](documentation/modernization-agents.md) | Ingest estate with ranked confidence; plan with cost and timelines |
| [SoT and Twin Agents](documentation/sot-and-twin-agents.md) | Inventory, NetBox, and the CML lab that must match prod |
| [Change and Test Agents](documentation/change-and-test-agents.md) | Size a change, run suites, record risk |
| [Compliance Agents](documentation/compliance-agents.md) | Coverage against the job catalog and NIST titles |
| [ServiceNow Agents](documentation/servicenow-agents.md) | Cases and logistics — not the health watch |
| [Network Ops](documentation/network-ops.md) | Attending: read the chart, do not collect |

## How they coordinate

Each agent writes only the files it owns. Health nurses write visit
stamps. Health Analyzer writes `state/health.json`. Ops Network Sync
writes inventory. Ops NetBox SoT writes the infra snapshot. Modernization Analysis and
Lifecycle share the estate table. Test writes run results. The catalog
in `workspace-handoff` is the contract.

Health Analyzer does not recommend. Modernization plans refresh.
Compliance proposes intel. A passing test on a drifted twin is not
evidence — fidelity belongs in the gate.
