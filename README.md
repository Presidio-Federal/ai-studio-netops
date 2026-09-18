# AI Studio NetOps

AI Studio NetOps is a multi-agent system for understanding, testing, changing, and evolving network infrastructure.

The architecture treats the Studio workspace as a **patient chart**: a persistent shared case record that allows specialized agents to contribute knowledge without relying on agent-to-agent conversation history.

> **Agents distribute the work. The chart preserves the knowledge. Higher-level models concentrate the reasoning.**

## Why the Patient Chart

Network operations rarely follows a predictable sequence.

Health checks, compliance analysis, testing, configuration changes, incidents, and infrastructure discovery can occur independently, at different times, and using different models.

Traditional multi-agent workflows often depend on handoffs:

```text
Agent A → Agent B → Agent C
```

That makes continuity dependent on execution order and requires each agent to reconstruct context from previous conversations or summaries.

This architecture moves continuity into the workspace.

Specialists inspect authoritative systems, compare what they find with what is already known, and record meaningful changes. Higher-level analysis uses that shared record to interpret the environment and determine what should happen next.

The workspace is not a copy of the underlying systems. Splunk owns its logs, ThousandEyes owns its telemetry, GitHub owns approved configuration and tests, NetBox owns infrastructure records, and ServiceNow owns its workflow data.

The chart maintains the **evolving understanding of the environment**.

[Read the Patient Chart architecture →](documentation/patient-chart.md)

---

# Capabilities

The system is organized around several operational capabilities. Individual agents, skills, and tools implement these capabilities without requiring the rest of the system to understand their internal workflows.

## State of the Environment

A maintained analysis of what the current environment looks like.

The goal is not to continuously copy source-system data into the workspace. The system records material observations, changes, assessments, and current state so that other workflows have a concise and durable understanding of the environment.

### Health

Health combines observations from operational sources into a current assessment of the environment.

Specialists compare live information with previous observations and record meaningful changes. A higher-level analyzer correlates those observations using a SOAP-inspired model to maintain an assessment and actionable objectives.

**Question answered:**
*What is happening in the environment, what changed, and what requires attention?*

[Health architecture →](documentation/health-agents.md)

### Compliance

Compliance maintains both **coverage** and **posture**.

Coverage determines whether the environment is testing the controls that are relevant to the infrastructure actually deployed. Posture determines whether those implemented checks currently pass.

Published controls remain external, implemented checks live in Git, and detailed execution evidence remains with test results. The workspace maintains the meaningful compliance state and changes needed by higher-level analysis.

**Questions answered:**
*Are we testing the right things?*
*Are the things we test currently passing?*

[Compliance architecture →](documentation/compliance-agents.md)

---

## Source of Truth and Digital Twin

Maintains the infrastructure model required to understand and safely reproduce the environment.

GitHub owns approved network configuration. NetBox maintains infrastructure identity and relationships such as devices, interfaces, IP addresses, and cables. CML provides a digital twin constructed from those approved sources.

The digital twin is a test environment, not an independent source of truth.

**Question answered:**
*What infrastructure exists, how is it connected, and can we reproduce it?*

[SoT and Digital Twin architecture →](documentation/sot-and-twin-agents.md)

---

## Change and Validation

Turns an intended infrastructure change into something that can be evaluated, tested, and safely applied.

Proposed changes are developed against known environment state, validated using the available testing infrastructure, and applied through the Git-based configuration workflow.

Testing produces evidence and risk information rather than silently authorizing production changes.

**Question answered:**
*Can we make this change, what does it affect, and what evidence do we have that it is safe?*

[Change and testing architecture →](documentation/change-and-test-agents.md)

[Network operations architecture →](documentation/network-ops.md)

---

## Incident and Workflow Integration

Connects operational understanding with external workflow systems such as ServiceNow.

Tickets remain authoritative in their source platform. Relevant incident and workflow information can contribute to the shared understanding of the environment without duplicating the external system in the workspace.

**Question answered:**
*What operational work is already underway, and how does it relate to the current environment?*

[ServiceNow architecture →](documentation/servicenow-agents.md)

---

## Modernization

Uses the accumulated understanding of the environment to support longer-term infrastructure decisions.

Current infrastructure, lifecycle information, support status, topology, and other relevant evidence can be combined into modernization analysis and roadmap recommendations.

**Question answered:**
*Given what exists today, what should the environment become over time?*

[Modernization architecture →](documentation/modernization-agents.md)

---

# Architectural Principles

Across these capabilities, the same rules apply:

1. **State belongs to the case, not the agent.**
2. **Source systems remain authoritative.**
3. **Schemas are the communication contract.**
4. **Record meaningful change instead of copying source data.**
5. **Separate evidence from interpretation.**
6. **Keep detailed evidence outside reasoning context until it is needed.**
7. **Use higher-capability models where correlation and interpretation add value.**
8. **Do not make continuity dependent on agent execution order.**
9. **Keep specialist responsibilities narrow.**
10. **A new conversation must be able to resume from the shared record.**

The result is a system in which agents can remain specialized and largely stateless while the platform maintains a persistent understanding of the infrastructure.
