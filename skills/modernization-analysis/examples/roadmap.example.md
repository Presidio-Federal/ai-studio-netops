# Modernization roadmap

Shape only. Fill from `state/lifecycle.json` and `guidance.answers`.
Never copy these hostnames or PIDs.

## Current environment

One product group from SoT (`device_type` as written). Identity
confidence medium. Research stale or missing until Lifecycle
returns.

## Where we are going

Operator answers as written on `guidance.answers`. Empty if
they have not said yet — do not invent this section’s intent.

## Vendor constraints

Hardware replacement SKU and software train only if Cisco
already filled them on the estate row. Otherwise none.

## Sequence

1. Order — only with a Cisco SKU and quantity already on the
   estate. ServiceNow writes the ticket.
2. Stage / receive
3. Deploy on twin, then Test
4. Schedule the window and the people
5. Cutover or software upgrade

Dates only from Cisco EoX or the operator.

## Gaps

- Missing answers or missing vendor research, as on the estate.
