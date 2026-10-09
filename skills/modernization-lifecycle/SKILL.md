---
name: modernization-lifecycle
version: "1.6.1"
description: "v1.6.1 — visit_lifecycle.py researches each product_id on inventory/assets/devices.json, even when the estate still lists the CML type."
---

# Modernization Lifecycle skill

You fill **missing or stale** Cisco research on
`state/lifecycle.json` (hardware EoX **and** software train).
Raw detail goes in `inventory/assets/<pid>.json`. Check what
exists first. If the estate file is missing, stop `unknown`. If
the table is current, do not call MCP. A row is in scope only
when its `pid` is a `product_id` on `inventory/assets/devices.json`.
Do not write that file. Do not look up a CML node type.

A named Modernization Lifecycle / Cisco / EoX / software /
PSIRT / CCW check is authorization. Health, twin, tickets,
identity refresh: `That's not what I do.`

## Hard boundaries

Do not invent dates, list prices, replacement SKUs, or software
trains. Do not create `state/lifecycle.json`. Do not map
hostnames to products. Do not `ls` `lifecycle/`. Do not write
scripts. `execute_command` runs only `scripts/visit_lifecycle.py`.
`collect` is `mcp_orchestration`. `annotate` is `standard`.
Never copy example hostnames or PIDs.

Tool names: `references/tools.md` (Cisco API, CCW catalog, NVD get).

## Files

Paths: **`workspace-handoff`**. Produce:
`references/workspace-contract.md`. If `read_file` /
`write_file` Access denied lists `file_explorer`: retry once as
`file_explorer/<catalog row>`. Never a UUID. Never
`/shared_workspace/HAI-ASSISTANTS-WAPSPACES/...`. `detail_ref`
stays the catalog row (`inventory/assets/<pid>.json`).

Use exactly: `references/watch.md`, `references/tools.md`,
`references/workspace-contract.md`,
`schemas/lifecycle-estate.schema.json`,
`schemas/lifecycle-item.schema.json`,
`examples/lifecycle-estate.example.json`,
`examples/lifecycle-item.example.json`.

Every structured JSON write requires top-level `keys`: an
array with unique canonical values. For both the estate and
item file, write the deduplicated `device:<name>` union from
their nested `devices` fields, or `[]`. Keep nested identity
fields. Do not put PIDs, recommendation IDs, replacement SKUs, or anything
inferred from prose in `keys`. Continue preserving and enriching
recommendations in their existing fields.

Copy research onto matching `pid` only. Keep identity
(`quantity` `devices` `summary` `source` `pid_source`
`software_versions`) and `recommendations`, `guidance`,
`roadmap_ref`. Set
`recommended_replacement` only from Cisco hardware EoX. Keep
`selected_replacement` (operator SKU on the table only). Price
that SKU with CCW when set. Set
`recommended_software` only from Cisco software EoX / PSIRT
Software Checker.

**First tool:** one `execute_command`, `execution_type:
mcp_orchestration`. Copy the path Studio shows for
`scripts/visit_lifecycle.py`. Pass the `file_explorer` directory
beside `skills` on that path as `--workspace`.

```text
python3 <skill>/scripts/visit_lifecycle.py collect --workspace <file_explorer>
```

The last stdout line is the result. Do not open the estate to
fill the reply. If `needs_note` is not empty, one
`execute_command`, `execution_type: standard`, same path:

```text
python3 <skill>/scripts/visit_lifecycle.py annotate --workspace <file_explorer> --ask "<pid>=<why, then the choice>"
```

One `--ask` per `needs_note` PID. Why this estate, then the
choice. Do not pick a SKU. If stderr says `hai_mcp unavailable`,
follow `references/watch.md`. Any other failure: one line from
stderr, then stop.

## State machine

COLLECT_SCRIPT → (needs_note → ANNOTATE) → STOP. The script
reads, decides, calls MCP, and writes. Annotate sets only
`replacement_ask`.
