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
| Ops ServiceNow Trends | Nightly/on-demand scan of the named slice. Cluster tickets; recommend a KB when close_notes agree. | `servicenow/metadata-trends.json`, `servicenow/trends/<stamp>.json` |
| Ops ServiceNow Operator | Who can go onsite; if they are on a Trends KB ticket, recommend a draft to free them. Lab cases and INC updates. | `servicenow/metadata-lab.json`, `state/servicenow.json`, `servicenow/cases/` |

Health ServiceNow never writes `state/servicenow.json` or
`servicenow/trends/`. Trends and Operator never write `health/`.

## Metadata

| File | Who | What you set |
|------|-----|----------------|
| `servicenow/metadata-trends.json` | Trends | Assignment groups, categories, match terms, optional marker, lookback (default 14 days), cluster threshold (default 3). |
| `servicenow/metadata-lab.json` | Operator | Lab marker + match terms. Same discover-then-ask pattern as `health/metadata-servicenow.json`. |
| `health/metadata-servicenow.json` | Health ServiceNow | Lab marker for the **health** stamp. Separate file. |

Missing scope is not a failure. The agent reads, discovers options,
asks if more than one fit, and writes the choice. It does not invent
a marker or treat the whole shared instance as this lab.

## Trends

Nightly or on demand. Same visit order as Health: read
metadata, pick a stamp, collect, `write_file` the catalog
path, read it back. A schedule line is authorization — do
not ask, do not `lstat` the schedule folder. Recommend a KB
only when close_notes agree. Cap 10. Find/get plus knowledge
**read** — no create, no `trends.json`. On MCP failure still
write the stamp (`unavailable`).

## Operator

**Onsite / dispatch** does not need the lab marker. Read the
latest Trends stamp and live group members for the site they
named. If the person who could go is on an open ticket in a
`recommend: kb` cluster, say a KB would free them and offer
someone who is not on an open ticket.

**Lab cases** stay on `servicenow/metadata-lab.json`. Shared-
instance rows that are not lab and not this dispatch ask stay
out of scope.

Assign or draft a KB only when they ask this turn (draft only;
never publish; do not write a Trends stamp). After a tested
change they named, update that INC and read it back. One
mutation per invoke.
