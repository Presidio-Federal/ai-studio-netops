---
name: caldera-mcp
version: "1.0.0"
description: "v1.0.0 — Caldera skill: read the workspace network, then create and run a traffic operation on an enrolled agent group."
---

# Caldera skill

This workspace is the security workspace. It is not the network-ops
chart. Do not write `health/`, `state/health.json`, or
`inventory/prod.json`.

Two jobs. A line that says to read or refresh the network is a
collect. A line that names a group and says to run the traffic test
is authorization to create that operation. Do not ask a second time.
Anything else that would create, change state, open a potential
link, or delete waits for that line.

The job is traffic. Agents that are already enrolled open connections
to addresses in the workspace inventory. The visit records the
operation. It does not judge whether Elastic or Splunk alerted.

## Hard boundaries

Do not write an ability, a payload, a deploy command, or a link
command. The server rejects those paths. Do not copy `command`,
`plaintext_command`, `output`, or `executor` into the workspace or
the reply. Do not print them.

Do not start an adversary whose abilities are exfiltration, lateral
movement, impact, defense evasion, or credential access. Names that
are refused for a traffic run: Everything Bagel, Thief, Ransack,
Worm, Lateral Movement, Defense Evasion, Alice, Super Spy, Stowaway,
Collection, Terminal, Enumerator, Check, Undercover, Nosy Neighbor.
Stockpile Discovery is local host commands. It is not a traffic run.

An empty `group` hits every agent. Do not send one. Do not start a
second operation while one with the same adversary and group is
`running`.

## Files

| Path | Kind | When |
|------|------|------|
| `inventory/network.json` | snapshot | Collect, and again when the operator says the network changed. |
| `security/metadata.json` | metadata | Every run. Agents and the latest operation. |
| `security/<stamp>.json` | result | After an operation is created or a running one is read. Never overwrite. |

Schemas and examples live in this skill. Paths: `references/workspace-contract.md`.
Tools and paths: `references/tools.md`. Steps: `references/run.md`.

## State machine

Collect: READ_BOARD → NETWORK_TOOLS → WRITE `inventory/network.json` → STOP.

Run: READ `inventory/network.json` → LIST agents, adversaries, planners, sources → MATCH → CREATE → WRITE the stamp and the board → STOP.

Missing `inventory/network.json` on a run: one line, `Need: inventory/network.json`, and stop. Do not invent destinations from chat.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. A host that matches `inventory/network.json` `devices[].name` is `device:`. A site name from that file is `site:`. An ATT&CK technique id is a field, not a key.
