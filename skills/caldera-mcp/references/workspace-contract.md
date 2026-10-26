# Workspace — campaigns

This agent's chart is `campaigns/`. Network topology, CML, and
IOS-XE belong to other agents. Do not write `campaigns/network/`,
`inventory/`, `health/`, or `state/`. Do not write
`inventory/network.json` or `security/`.

The skill owns these schemas. One writer. A collect replaces each
board. An operation stamp is append-only. Keep 10 stamps under
`campaigns/operations/` and delete older after a write. Do not
delete the boards.

## When to write

| File | Kind | When |
|------|------|------|
| `campaigns/metadata.json` | metadata | Every visit. |
| `campaigns/agents/enrolled.json` | snapshot | Every collect. |
| `campaigns/abilities/relevant.json` | snapshot | Every collect. |
| `campaigns/adversaries/relevant.json` | snapshot | Every collect. |
| `campaigns/facts/lab.json` | snapshot | Every collect. |
| `campaigns/operations/<stamp>.json` | result | Material operation only. |

A quiet collect rewrites the boards and does not add a stamp.

## Relevant

A row that is not a trusted enrolled agent, not a `lab-` adversary,
and not a discovery scan, probe, sweep, or port ability does not
get a file. Do not store the Caldera catalog.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. Technique ids stay fields.
