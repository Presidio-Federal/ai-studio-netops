---
name: caldera-mcp
version: "2.1.0"
description: "v2.1.0 — Caldera nurse: keep relevant agents, abilities, adversaries, and facts, and run a test from those abilities."
---

# Caldera skill

One visit. You keep the campaign chart and, when the line says to
run, you start one operation from abilities already on that chart.
You do not gather network data. You do not call CML or IOS-XE. You
do not change device config. You do not write `health/`, `state/`,
or `campaigns/network/`.

A line that says to refresh the campaign, or names Caldera with no
run, is a collect. A line that names a group and says to run is
authorization for that operation. Do not ask again.

The chart is `campaigns/`. Subdirectories are `agents`, `abilities`,
`adversaries`, `facts`, and `operations`. Keep a row only when it
is a lab campaign. Drop the rest of the Caldera catalog. An ATT&CK
technique id is a field, not a key.

## Hard boundaries

Do not `POST` `/api/v2/abilities`. The server rejects ability
writes, payloads, deploy commands, and link command updates. A new
test is a new adversary whose `atomic_ordering` is ability ids
already in `campaigns/abilities/relevant.json`, plus facts already
in `campaigns/facts/lab.json`.

Do not copy `command`, `plaintext_command`, `output`, or `executor`
into the workspace or the reply.

Do not keep an ability whose tactic is exfiltration, lateral
movement, impact, credential access, or defense evasion. Do not
start Everything Bagel, Thief, Ransack, Worm, Lateral Movement, or
stockpile Discovery.

An empty `group` hits every agent. Do not send one. Do not start a
second operation while one with the same adversary and group is
`running`.

This visit does not push a firewall rule. `next_test` on the board
is the next campaign.

## Files

| Path | Kind | When |
|------|------|------|
| `campaigns/metadata.json` | metadata | Every visit. |
| `campaigns/agents/enrolled.json` | snapshot | Every collect. Replaced. |
| `campaigns/abilities/relevant.json` | snapshot | Every collect. Replaced. |
| `campaigns/adversaries/relevant.json` | snapshot | Every collect. Replaced. |
| `campaigns/facts/lab.json` | snapshot | Every collect. Replaced. |
| `campaigns/operations/<stamp>.json` | result | A run, or a collect that finds a new or changed lab operation. Never overwrite. |

Paths: `references/workspace-contract.md`. Tools: `references/tools.md`.
Steps: `references/visit.md`.

## State machine

Collect: READ boards → CALDERA lists → WRITE the five boards → STOP.

Run: READ the five boards → MATCH group and facts → CREATE the operation → WRITE `campaigns/operations/<stamp>.json` and update metadata → STOP.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. An enrolled host name is `device:`. A technique id is never a key.
