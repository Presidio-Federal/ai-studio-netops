# Roadmap markdown — Modernization Analysis

Write **`lifecycle/roadmap.md`** only after operator answers
are on `guidance` (`objectives_status` `stated` or `partial`
with a non-empty `answers`). Do not invent objectives. Do not
invent EoX dates, SKUs, or trains.

Replace the file in full. Do not paste it in chat.

The example is **shape only**. Never copy its hostnames or PIDs.

## Sections (this order)

1. **Current environment** — product groups, confidence
   (`guidance.identity_confidence` /
   `guidance.research_confidence`), what is unknown.
2. **Where we are going** — only `guidance.answers`. If still
   partial, say so.
3. **Vendor constraints** — Cisco dates, `recommended_replacement`,
   `recommended_software` already on the estate. Null stays
   null.
4. **Sequence** — phases a coordinator can run:
   - Order (SKU / qty from the estate; ServiceNow is the
     ticket writer)
   - Stage / receive
   - Deploy on twin, then Test
   - Schedule change windows and people
   - Cutover / software upgrade
   Put dates only when Cisco or the operator gave them.
5. **Gaps** — missing research, low-reliability identity,
   unanswered asks.

Do not add a canned “bandwidth vs downtime” section. Sequence
from this estate and their answers.

Do not write `state/modernization.json`.
