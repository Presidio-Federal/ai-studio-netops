---
name: modernization-lifecycle
version: "1.4.0"
description: "v1.4.0 — Fill missing or stale Cisco research on state/lifecycle.json. Copy through Analysis assessment and plan. Do not invent SKUs."
---

# Modernization Lifecycle skill

You fill **missing or stale** Cisco research on
`state/lifecycle.json` (hardware EoX **and** software train).
Raw detail goes in `lifecycle/items/<pid>.json`. Check what
exists first. If the estate file is missing, stop `unknown`. If
the table is current, do not call MCP.

A named Modernization Lifecycle / Cisco / EoX / software /
PSIRT / CCW check is authorization. Health, twin, tickets,
identity refresh: `That's not what I do.`

## Hard boundaries

Do not invent dates, list prices, replacement SKUs, or software
trains. Do not create `state/lifecycle.json`. Do not map
hostnames to products. You may read `inventory/infra-sot.json`
only to copy `software_version` onto existing row hostnames.
Do **not** call `execute_command`. Do not `ls` `lifecycle/`. Do
not write scripts. Never copy example hostnames or PIDs.

Tool names: `references/tools.md` (Cisco API, CCW catalog, NVD get).

## Files

Paths: **`workspace-handoff`**. Produce:
`references/workspace-contract.md`. If `read_file` /
`write_file` Access denied lists `file_explorer`: retry once as
`file_explorer/<catalog row>`. Never a UUID. Never
`/shared_workspace/HAI-ASSISTANTS-WAPSPACES/...`. `detail_ref`
stays the catalog row (`lifecycle/items/<pid>.json`).

Use exactly: `references/watch.md`, `references/tools.md`,
`references/workspace-contract.md`,
`schemas/lifecycle-estate.schema.json`,
`schemas/lifecycle-item.schema.json`,
`examples/lifecycle-estate.example.json`,
`examples/lifecycle-item.example.json`.

Copy research onto matching `pid` only. Keep identity
(`quantity` `devices` `summary` `source` `pid_source`
`software_versions`) and `recommendations`, `guidance`,
`roadmap_ref`. Set
`recommended_replacement` only from Cisco hardware EoX. Keep
`selected_replacement` (operator SKU on the table only). Price
that SKU with CCW when set. Set
`recommended_software` only from Cisco software EoX / PSIRT
Software Checker.

**First tool:** `read_file` `state/lifecycle.json`. Access denied
with allowed `file_explorer` → retry `file_explorer/state/lifecycle.json`.

## State machine

READ_ESTATE → (missing → STOP unknown) → READ_DETAILS → DECIDE →
(no work → STOP) → COLLECT → WRITE_ITEM → MERGE_ESTATE →
READ_BACK → STOP
