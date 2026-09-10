# ServiceNow Agents

Cases for **this lab** and ticket trends for a named slice
(EUC/demo, a group, a category). They are not the ServiceNow
**health** watch — that is [Health ServiceNow](health-agents.md),
which is read-only and does not vote vitals.

Scope lives in workspace metadata, the same way Health keeps
Splunk index / TE tests / the ServiceNow marker out of the prompt.
You point an agent at data by editing that file (or answering
when it asks). Live ids are not in the prompt.

## Agents

| Agent | Role | Writes |
|-------|------|--------|
| Ops ServiceNow Trends | Cluster tickets in the named slice. Recommend KB, restaff, or a problem. | `servicenow/metadata-trends.json`, `servicenow/trends/<stamp>.json` |
| Ops ServiceNow Operator | Open in-scope lab tickets, recommend a fix, then update the INC after another agent tests the change. | `servicenow/metadata-lab.json`, `state/servicenow.json`, `servicenow/cases/` |

Health ServiceNow never writes `state/servicenow.json` or
`servicenow/trends/`. Trends and Operator never write `health/`.

## Metadata

| File | Who | What you set |
|------|-----|----------------|
| `servicenow/metadata-trends.json` | Trends | Assignment groups, categories, match terms, optional marker. First visit reads this, then `inventory/prod.json`. |
| `servicenow/metadata-lab.json` | Operator | Lab marker + match terms. Same discover-then-ask pattern as `health/metadata-servicenow.json`. |
| `health/metadata-servicenow.json` | Health ServiceNow | Lab marker for the **health** stamp. Separate file. |

Missing scope is not a failure. The agent reads, discovers options,
asks if more than one fit, and writes the choice. It does not invent
a marker or treat the whole shared instance as this lab.

## Trends

One visit writes one new stamp under `servicenow/trends/`. Never
overwrite. Cap 10. Inventory names the engineering side
(`inventory/prod.json`). Find/get plus knowledge **read** — no
create, no update. Password-reset class noise can recommend a KB;
repeating path/site can recommend a problem or restaff. It does not
file the ticket and does not invent a network change.

## Operator

In-scope only: marker / match terms / inventory labels. Shared-
instance rows are out of scope.

Open lab INC → recommend the fix from the ticket + inventory. Do
not apply IOS-XE. Next is Design / Test unless they only wanted
the board. After a tested change they named, update that INC and
read it back. One mutation per invoke. Dedup by `idempotency_key`.
