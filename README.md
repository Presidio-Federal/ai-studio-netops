# AI Studio NetOps

This repository authors **agent prompts** and **skills** for Presidio
AI Studio. Cursor is the authoring environment. Studio is where the
agents run.

Studio agents share a workspace chart, not each other’s prompts. Each
agent writes only the files it owns. GitHub, NetBox, and the CML twin
remain the systems of record.

## Agent families

| Family | What they do |
|--------|----------------|
| [Health Agents](documentation/health-agents.md) | Collect one telemetry plane per visit and roll the chart |
| [Modernization Agents](documentation/modernization-agents.md) | Estate identity, Cisco research, and refresh plans |

More families will be documented here as their prompts land in this
repo.

## In this repo

| Path | Role |
|------|------|
| `agents/` | Lean Studio prompts (identity, ownership, reply contract) |
| `skills/` | Workflows, schemas, and tool contracts. Zip root is `<name>/SKILL.md` |
| `documentation/` | Published descriptions of the agent families |
| `skills/workspace-handoff/` | Shared catalog: who writes which workspace file |

Health prompts and skills are in this checkout. Modernization is
described from the catalog; its prompt and skill files are not here
yet.

## Local only (not on GitHub)

| Path | Role |
|------|------|
| `docs/` | Notes and files for Cursor to read |
| `plans/` | Local design plans |
| `.cursor/rules/` | Cursor authoring rules |

## Studio vs this repo

| Studio | This repo |
|--------|-----------|
| `/workspace/` | `.workspace/` (local mirror, not committed) |
| `/skills/user/<skill>/` | `skills/<skill>/` |
