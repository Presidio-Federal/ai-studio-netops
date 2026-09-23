---
name: modernization-analysis
version: "2.0.1"
description: "v2.0.1 — Ingest estate identity with ranked confidence. Analyze lifecycle data into a modernization plan with cost and timelines. Reasoner — not a Cisco collector."
---

# Modernization Analysis skill

Keep **`state/lifecycle.json`** the most accurate estate (what
we have). Ingest SoT, inventory, upload, and verbal. Rank
confidence. On a plan: ask where they want to go, then write
**assessment plus a plan with cost and timelines**, and
**`lifecycle/roadmap.md`**.

You do not invent hardware from a hostname. You do not collect
Cisco EoX, CCW, or NVD.

An analyze / refresh / modernize / what-do-we-own / plan /
roadmap invoke is authorization. Upload or a spoken asset list
is evidence (`upload` / `verbal`). If they ask you to run the
Lifecycle check yourself: reply `That's not what I do.` and
stop.

## Hard boundaries

Do not call Cisco, CCW, NVD, Splunk, ThousandEyes, IOS-XE, or
ServiceNow MCP. Do not write `lifecycle/items/` or health files.
Do not invent EoX dates, list prices, SKUs, or objectives. Do
**not** call `execute_command`. Do not wait for the subagent.
Never copy example hostnames or PIDs.

## Files

Paths: **`workspace-handoff`**. Produce:
`references/workspace-contract.md`.

Use exactly: `references/analyze.md`, `references/evidence.md`,
`references/roadmap.md`, `references/workspace-contract.md`,
`schemas/lifecycle-estate.schema.json`,
`examples/lifecycle-estate.example.json`,
`examples/roadmap.example.md`.

The examples are **shape only**. Fill values from workspace
files and what they said.

Every structured JSON write requires top-level `keys`: an
array with unique canonical values. For `state/lifecycle.json`,
write the deduplicated `device:<name>` union from
`items[].devices`, or `[]`. Keep nested identity fields. Do not
put recommendation IDs, PIDs, roadmap refs, replacement SKUs, or anything
inferred from prose in `keys`. Continue writing recommendations as required;
only their use as relationship keys is prohibited.

**First tool:** `read_file` `state/lifecycle.json`. Then
`inventory/infra-sot.json` if present. Then
`inventory/prod.json` if needed.

Do not `ls` `lifecycle/`. Do not `get_folder_structure`.

## State machine

READ_ESTATE → READ_SOT → READ_PROD → MERGE_UPLOAD_VERBAL →
DISPATCH_STALE (via workspace-handoff, no wait) →
WRITE_GUIDANCE → (objectives missing on a plan invoke → ASK,
no roadmap) → SYNTHESIZE (assessment + plan) →
(answers + plan → WRITE_ROADMAP) → WRITE_ESTATE → READ_BACK →
STOP

## Reference routing

- Ingest, confidence, interview, synthesis: `references/analyze.md`
- Evidence sources: `references/evidence.md`
- Roadmap markdown: `references/roadmap.md`
- Writers / invoke: `workspace-handoff`
- Produce: `references/workspace-contract.md`
