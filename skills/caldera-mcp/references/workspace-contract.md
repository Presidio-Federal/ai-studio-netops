# Workspace — Caldera

This workspace belongs to the Caldera agent. The network-ops chart
is a different workspace. Do not read or write its files.

The skill owns these schemas. Do not invent a second tree.

## Collect

A line that says to read the network, or refresh the network, is
the collect. Use the network read tools attached to this agent.
Write one file, then stop.

Keep a device only when a tool returned its name. Copy addresses
the tool returned. `role` is `host` for a Linux agent host, `network`
for a router or firewall, `service` for an application the traffic
test should reach. `group` is set only when the tool or the operator
named the Caldera group for that host. Leave it null otherwise.

Do not call Caldera on a collect. Do not write `security/`.

## Run

Read `inventory/network.json` before any Caldera call. The run does
not refresh the network unless the operator also said to refresh.
A refresh and a run are two turns.

## When to write

| File | Kind | When |
|------|------|------|
| `inventory/network.json` | snapshot | Collect. Replaced in full. |
| `security/metadata.json` | metadata | Every run. |
| `security/<stamp>.json` | result | One new file per run. Never overwrite. |

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. Technique ids stay fields.
