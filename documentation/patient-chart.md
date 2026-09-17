# Patient Chart Multi-Agent Architecture

This is the coordination model for the fleet. Health is the first
family that implements it in schemas and prompts:
[Health Agents](health-agents.md). Paths and writers live in
`workspace-handoff`. The Studio workspace is the case record.

## Background

Multi-agent systems are commonly designed around agent-to-agent
handoffs. One agent performs work, summarizes its findings, and
passes context to the next agent.

This works well for deterministic workflows where execution follows
a predictable sequence. IT operations is different.

Operational agents may execute on independent schedules, respond to
different events, use different models, or not execute at all during
a particular workflow. At the same time, the underlying environment
may contain enormous amounts of telemetry distributed across
observability platforms, network devices, ITSM systems, and other
sources.

The architecture therefore requires a mechanism for maintaining
continuity that does not depend on the order in which agents execute
or on one agent successfully transferring its context to another.

## The Challenge

### Handoff-Dependent Continuity

A traditional multi-agent workflow often assumes:

```text
Agent A → Agent B → Agent C
```

State is carried through the execution path. If the sequence
changes, an agent fails, or another specialist joins later,
continuity must be reconstructed.

This tightly couples operational state to orchestration.

### Repeated Context Reconstruction

Agents are generally stateless between executions. Each invocation
requires the system to provide enough context for the agent to
understand the current situation.

As operational history grows, this can result in increasingly large
prompts, summaries, and handoff messages.

### Excessive Operational Data

IT systems already maintain large authoritative datasets.

ThousandEyes may collect measurements every 30 seconds. Splunk may
contain millions of log events. Network devices expose extensive
operational state. ServiceNow maintains incidents and workflow
history.

Copying this information into an agent workspace creates another
telemetry repository without improving understanding.

### Mixed Model Behavior

Different agents may be powered by different models, including
combinations of local and frontier models.

Passing natural-language reasoning between models introduces
interpretation differences. Those differences can compound as
information moves through a chain of agents.

The architecture should not require models to reason identically in
order to collaborate reliably.

## Design Inspiration: The Patient Chart

Healthcare has addressed a similar coordination problem for
decades.

A hospitalized patient may interact with nurses, physicians,
specialists, technicians, and other caregivers across multiple
shifts. These individuals do not need to interact directly with
every previous caregiver to maintain continuity.

Continuity exists in the patient record.

The chart provides a persistent representation of what has been
observed, what is believed, what actions have been taken, and what
should happen next.

The same principle applies to multi-agent operations:

> Agents do not pass operational state to other agents. Agents
> contribute knowledge to a shared case.

Agents can therefore remain largely stateless while the overall
system remains stateful.

## Architecture Principles

### 1. The Case Owns State

Operational state belongs to a persistent shared case record rather
than an individual agent or orchestration sequence.

Agents read the portions of the case relevant to their
responsibilities, perform specialized work, contribute new
information when appropriate, and exit.

This allows agents to execute asynchronously without losing
continuity.

### 2. Schemas Are the Communication Contract

Agents communicate through structured data contracts rather than
arbitrary prose.

A schema defines what an observation means regardless of which
model produced it.

This allows different models and agent implementations to
collaborate without requiring them to reproduce one another's
reasoning.

### 3. Source Systems Remain Authoritative

The chart is not a replacement for Splunk, ThousandEyes,
ServiceNow, network devices, or other operational platforms.

Raw data remains in the authoritative system.

The chart stores the operationally significant information derived
from those systems and maintains references to supporting evidence
when deeper investigation is required.

### 4. Record Material Change, Not Repeated State

Specialist agents should not continuously reproduce information
already available in source systems.

Instead, they answer a more useful question:

> Given what is already known about this case, what has materially
> changed?

The standard specialist interaction becomes:

```text
Read → Query → Compare → Detect Significance → Write or Exit
```

If nothing meaningful has changed, the agent does not need to add
another case entry.

Agent execution and health are tracked separately from case
knowledge.

### 5. Separate Observation From Interpretation

Specialist agents should generally report evidence within their
domain rather than make broad diagnoses.

For example:

**Observation**

> Packet loss increased from a baseline below 1% to 12% and has
> remained elevated for 11 minutes.

is different from:

**Assessment**

> The ISP circuit is failing.

The first describes evidence. The second interprets it.

Preserving this distinction allows assessments and hypotheses to
evolve while maintaining the original evidence and its provenance.

## Agent Interaction Model

Specialist agents follow a common operational pattern:

```text
READ CASE
    │
    ▼
QUERY AUTHORITATIVE SOURCE
    │
    ▼
COMPARE WITH PRIOR KNOWLEDGE
    │
    ▼
DETECT MATERIAL CHANGE
    │
    ├──── No Change ────► EXIT
    │
    ▼
WRITE STRUCTURED OBSERVATION
    │
    ▼
EXIT
```

This pattern allows prompts to remain relatively consistent across
specialists.

Skills primarily define:

- Available tools and source-specific procedures
- Relevant data
- Comparison logic
- Domain-specific thresholds
- Output schemas
- Evidence requirements

The agent's responsibility is intentionally narrow: determine
whether its domain contributes new, relevant information to the
case.

## The Patient Chart

The chart is best understood as a record of the system's evolving
operational understanding.

It may contain several classes of information:

### Observation

A meaningful fact discovered by a specialist.

### Assessment

An interpretation of one or more observations.

### Plan

An objective or investigation that should occur next.

### Action

An intervention performed against the environment.

### Outcome

The observed result of an action.

These records should retain timestamps, provenance, confidence
where appropriate, and references to underlying evidence.

The chart should generally be append-oriented so that previous
observations and assessments remain available.

This creates three useful histories:

```text
What happened → What was observed → What the system believed
```

## Analysis and SOAP

SOAP is not intended to be the schema used by every specialist.

Most specialist agents primarily contribute objective observations.

SOAP is applied at the analysis layer, where a higher-capability
model has enough cross-domain information to interpret the case.

### S — Symptoms

What impact is being reported?

Examples include user complaints, application impact, ServiceNow
incidents, or degraded service.

### O — Objective Evidence

What have the specialist agents observed?

This may include network telemetry, logs, device state, application
measurements, or other structured findings.

### A — Assessment

What does the combined evidence currently indicate?

The assessment correlates observations, evaluates competing
hypotheses, and describes the current understanding of the case.

### P — Plan

What should happen next?

The Plan should produce actionable objectives rather than only
narrative recommendations. Those objectives can invoke additional
specialist work, creating another investigation cycle. They are
not a copy of a stamp the analyzer already read, and they are not
a SKU, git change, or test plan. Treatment and test live on the
agents that are authorized to act.

## The Analysis Loop

```text
                 FRONTIER ANALYZER
                       SOAP
                         │
                         ▼
                 ACTIONABLE OBJECTIVES
                         │
                         ▼
                  SPECIALIST AGENTS
                         │
              Read → Query → Compare
                         │
                 Material Change?
                    │         │
                   No        Yes
                    │         │
                   Exit       ▼
                         PATIENT CHART
                              │
                         New Evidence
                              │
                              └──────► ANALYZER
```

The frontier model is therefore used primarily where higher-order
reasoning provides value: correlation, ambiguity resolution,
hypothesis generation, assessment, and planning.

Smaller or local models can perform more deterministic specialist
functions such as querying systems, comparing known state,
detecting significant changes, and producing structured
observations.

## Architecture Evolution

The architecture was developed incrementally rather than beginning
with the healthcare abstraction.

### Building Block 1: Schema

Unstructured agent outputs were replaced with defined schemas.

**Result:** More accurate and predictable agent interactions and
handoffs.

### Building Block 2: Relevance

Schemas and agent instructions were refined so specialists
processed only information relevant to their responsibilities.

**Result:** Smaller contexts, reduced token consumption, and less
ambiguity.

### Building Block 3: Change

Specialists stopped repeatedly reporting current state and instead
identified material changes relative to previous knowledge and
baseline behavior.

**Result:** Less redundant information, lower processing costs, and
a cleaner operational record.

### Building Block 4: Interpretation

A higher-capability analyzer was introduced to synthesize
specialist observations using SOAP and produce actionable
objectives.

**Result:** Continuous observation could be separated from
expensive higher-order reasoning.

## Healthcare and Emergency Response Patterns

The architecture borrows different concepts for different
communication requirements.

**Patient Chart** provides persistent continuity and shared
operational understanding.

**SOAP** structures analysis and planning at the attending layer.

**SBAR** can provide concise escalation when another agent or human
requires immediate situational awareness.

**I-PASS** can structure explicit transfers of responsibility
between agents, systems, or humans.

These frameworks are not competing schemas. They address different
coordination problems. They are not the visit-file format.

## Architectural Outcome

The resulting system separates four concerns:

**Specialists provide evidence.**

**The chart provides continuity.**

**The analyzer provides interpretation.**

**Orchestration provides objectives and execution.**

This separation allows individual agents to remain relatively
simple and stateless while the overall system maintains a
persistent understanding of an evolving operational situation.

The patient chart therefore serves as more than agent memory. It
becomes the **coordination, compression, and continuity layer**
between operational systems and reasoning models.

The central architectural principle is:

> **Move continuity out of agents and orchestration into a
> persistent shared case record. Let specialists document what
> materially changed, and let higher-capability models interpret
> the accumulated evidence and determine what should happen next.**
