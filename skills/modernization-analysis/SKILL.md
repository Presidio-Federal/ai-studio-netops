---
name: modernization-analysis
version: "2.5.0"
description: "v2.5.0 — assess_estate.py turns support dates, lead times, and CCW offers into a low and high budget and 30, 60, and 90 day order windows."
---

# Modernization Analysis skill

Keep **`state/lifecycle.json`** the most accurate estate (what
we have). Ingest SoT, inventory, upload, and verbal. Rank
confidence. On a plan: ask where they want to go, then write
**assessment plus a plan with cost and timelines**, and
**`inventory/assets/roadmap.md`**.

You do not invent hardware from a hostname. You do not collect
Cisco EoX, CCW, or NVD.

An analyze / refresh / modernize / what-do-we-own / plan /
roadmap invoke is authorization. Upload or a spoken asset list
is evidence (`upload` / `verbal`). If they ask you to run the
Lifecycle check yourself: reply `That's not what I do.` and
stop.

## Hard boundaries

Do not call Cisco, CCW, NVD, Splunk, ThousandEyes, IOS-XE, or
ServiceNow MCP. Do not write `inventory/assets/<pid>.json` or health files.
Do not invent EoX dates, list prices, SKUs, or objectives. Do
not write scripts. `execute_command` runs only
`scripts/assess_estate.py` under `execution_type: standard`.
Do not wait for the subagent. Never copy example hostnames
or PIDs.

## Files

Paths: **`workspace-handoff`**. Produce:
`references/workspace-contract.md`.

Use exactly: `references/analyze.md`, `references/evidence.md`,
`references/roadmap.md`, `references/workspace-contract.md`,
`schemas/lifecycle-estate.schema.json`,
`schemas/inventory-assets.schema.json`,
`examples/lifecycle-estate.example.json`,
`examples/inventory-assets.example.json`,
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

**First tool:** one `execute_command`, `execution_type: standard`.
Copy the path Studio shows for `scripts/assess_estate.py`. Pass
the `file_explorer` directory beside `skills` on that path as
`--workspace`.

```text
python3 <skill>/scripts/assess_estate.py assess --workspace <file_explorer> --mode estate
```

Use `--mode plan` when they asked for a plan or roadmap. Add
`--verbal <hostname>=<pid>` or `--upload <hostname>=<pid>` for
assets they named this turn. The last stdout line is the estate. If `unstamped_count` is set,
name `inventory/assets/devices.json` and the devices still missing a
`product_id`. Do not dispatch Lifecycle for those. Dispatch only
when `needs_lifecycle` is true. Do not open `state/lifecycle.json`
to fill the reply.

Then annotate the verdict on that same path, still `standard`:

```text
python3 <skill>/scripts/assess_estate.py annotate --workspace <file_explorer> --headline "<one line>" --understood "<what this estate shows>" --opinion "<assessment verdict>" --plan-opinion "<plan verdict>" --plan-status none
```

On a plan invoke add `--answers`, `--objectives stated`,
`--open-ask` (one per question, why then the choice), `--must`,
`--can-wait`, `--stage`, `--recommendation`, and `--selected
<pid>=<sku>` when they named a SKU. `--dispatched` after you
invoke Lifecycle. The script rolls `plan.cost` from prices
already on the rows.

If `needs_lifecycle` is true, follow **workspace-handoff** and
do not wait. Then annotate `--dispatched`.

Do not `ls` `lifecycle/`. Do not `get_folder_structure`.

## State machine

ASSESS_SCRIPT → ANNOTATE → (needs_lifecycle → DISPATCH, no wait)
→ (answers and a plan invoke → WRITE_ROADMAP) → STOP. The
script merges identity, confidence, coverage, and list-price
totals. Annotate sets the verdict, the asks, and the plan.

## Reference routing

- Ingest, confidence, interview, synthesis: `references/analyze.md`
- Evidence sources: `references/evidence.md`
- Roadmap markdown: `references/roadmap.md`
- Writers / invoke: `workspace-handoff`
- Produce: `references/workspace-contract.md`
