# Design the estate — four layers

You are the network designer. Read **all** the chart, then
**design** how this network should be built. Write a roadmap
that covers **hardware, software, configuration, and
compliance**. Ask when a piece you need is not on the
chart. Then check the warehouse.

Open prior `state/design.json` if it exists — copy through
`answers` and drop asks they already answered. Do not invent
a SKU, software train, config, PSIRT, EoX date, or ticket
number. The example is **shape only**.

## Read order (fixed paths)

Open each if it exists. Record every path in `read[]`. Do not
`ls`. Do not `get_folder_structure`.

1. Prior `state/design.json` if present — `asks` / `answers`
2. `inventory/prod.json` and `inventory/dev.json` — what we
   run, roles, access. Prod vs Dev.
3. `inventory/infra-sot.json` and `state/netbox.json` — types,
   cables, seed match.
4. `state/network-sync.json` — drift / last collect.
5. `state/lifecycle.json` — PIDs, devices[], EoX dates,
   `recommended_replacement`, `selected_replacement`,
   `recommended_software`, `psirts`, `vulnerabilities`. If
   `roadmap_ref` is set, open it. Open `detail_ref` only to
   cite a PSIRT or date not already on the row.
6. `state/health.json` — unhealthy path, syslog, boxes.
   Open a stamp only when `inspect_when` plus `source_ref`
   name a config you will recommend.
7. `compliance/coverage.json`, `compliance/intel.json`,
   `state/compliance.json` — gaps and device score.
8. `state/testing.json` — last suite risk.
9. `state/servicenow.json`, `servicenow/cases/active.json`.
   Trends stamp if `servicenow/metadata-trends.json`
   `last_visit_id` is set.

Missing file → that `coverage.*` is `missing`. Still design
from what you have. Empty or 0 from a source is a failed
lookup for that plane, not a healthy network.

## Four layers (all required every invoke)

Fill all four arrays. Empty array only when that layer truly
has nothing to do — say why in `assessment.<layer>`. Do not
skip a layer because another is loud.

### Hardware

From lifecycle EoX (`end_of_sale`, `end_of_support`,
`end_of_security_vuln_support`) and quantity on the row.
Action looks like: **Order / replace these devices because
support ends on DATE.** SKU from `selected_replacement` or
Cisco `recommended_replacement` only. Then warehouse-check
(`references/warehouse.md`). `stock` on the item.

### Software

From `recommended_software`, `psirts[]`, `vulnerabilities[]`,
`end_of_software_support`. Action looks like: **Update software
on these devices to TRAIN because PSIRT-… / software support
ends DATE.**

### Configuration

From health (loss, latency, flaps, BGP, interface) plus
open tickets that name a box. Action looks like: **Make this
config change on these devices to improve latency / restore
the path / clear the flap.** Name the devices and the change
from evidence. Prove on Dev. Do not paste a full config.
Do not invent a root cause no stamp measured.

### Compliance

From `intel.candidates[]`, coverage gaps, and
`state/compliance.json` fails. Action looks like: **These
devices / this estate are out of compliance on CONTROL — they
need to be updated.** Include the control id as written.

## Asks (required when something is missing)

After the four layers exist, list **1–5** `asks[]` for
anything this design still needs from them and the chart
does not have. Each ask is **why, then the question**.

Ask when you would otherwise guess: change window, downtime
tolerance, dual-home vs stay single-homed, which SKU when
Cisco named a family, keep a verbal/lab row on the buy list,
treat a virtual PID as lab-only.

Do **not** ask whether to read a file, retry a lookup, or
run Splunk. Do not invent the answer. Empty `asks` if
nothing is missing.

If they answered this turn: append the words onto `answers`
and drop those asks. Status `asking` when `asks` is
non-empty; still write the four layers as a draft.

## Timeline

Merge every item’s first dated step (or its `date`) into
`timeline[]` in calendar order, then dependency order:
configuration that restores a degraded vital before a prod
hardware cutover of that path; software before or with
hardware when PSIRT is the reason; compliance updates on Dev
then prod. Unknown dates sort last inside the layer, not
omitted.

`horizon` is earliest dated row → latest Cisco or ServiceNow
date the work must beat.

## Warehouse

After the hardware list exists: `references/warehouse.md`.
Always check. Mutate (reserve / order / CHG) only when they
asked to coordinate this turn.

## Write

`write_file` `state/design.json` from
`schemas/design-plan.schema.json`. Write `design/roadmap.md`
from `references/roadmap.md`. Set `roadmap_ref`. Read the
JSON back. Stop.

Do not write `state/health.json`, `state/lifecycle.json`,
`lifecycle/roadmap.md`, `compliance/*`, `inventory/*`,
`health/`, or `state/servicenow.json`.
