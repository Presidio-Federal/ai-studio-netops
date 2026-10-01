# Services registry — `inventory/services.json`

The registry is the only source of `service:` key spellings in
the workspace. Health ServiceNow matches ticket wording against
`services[].aliases`; the Application Map writes `service` on an
application row only when the CMDB service name matches a
registry row; the Analyzer and the Relationship agent join on
`service:<name>`. Nobody else writes it. Nobody derives a service
name from prose.

You discover candidates, you **ask**, you write what they
confirmed. Schema `schemas/services.schema.json`; example
`examples/services.example.json`. Discovery is read-only; the
registry visit mutates no ServiceNow record.

Trigger: `Set up the services registry.` or `Update the services
registry.` (also "add a service", "what services do we have").

## Read (in this order)

1. `read_file` `inventory/services.json` if it exists — current
   `services[]` and `candidates_rejected[]`. Existing rows and
   rejected strings are not asked about again.
2. `read_file` `inventory/prod.json` — `devices[].name`. A device
   name is never a service candidate.
3. `read_file` `inventory/applications.json` if it exists —
   `services[]` (`name`, `sys_id`, `registered`). Read only; you do
   not write it.
4. `read_file` `servicenow/metadata-lab.json` — `servicenow.marker`
   and `match_terms[]` for the ServiceNow query. Missing marker:
   `references/metadata.md`; a registry visit may still proceed
   with the Application Map candidates alone.

## Discover — two sources, nothing else

**S — ServiceNow service CIs.** One call:

```text
snow_query_table(
  table="cmdb_ci_service",
  query="<SCOPE>",
  fields="sys_id,name,operational_status,owned_by,support_group,short_description",
  limit=50)
```

`<SCOPE>` = `commentsLIKE<marker>^ORnameLIKE<marker>` joined with
`^OR` to one `nameLIKE<t>` per `match_terms[]` item. Lab CIs carry
the marker in `comments` (see `application-map`
`references/cmdb-seed.md`); the `name` clause keeps older seeds.
Zero rows is a normal answer: a shared instance usually has no
service CI for this lab. Do not widen the query to the whole
table. Do not read `cmdb_ci_service` rows that matched nothing of
yours.

**M — Application Map services.** From `inventory/applications.json`
`services[]`, every row with `registered` false. These are service
CIs the map already saw; S normally returns the same rows, and a
row in both is one candidate (match on `sys_id`).

Candidate list = S rows (name, owner from `owned_by` or
`support_group` display value) + M rows not already in S, minus
existing `services[].name` / `aliases[]`, minus
`candidates_rejected[]`.

## Ask — always, before the write

Show every candidate with a proposed canonical name and its
aliases. Propose the name by stripping direction words; keep the
source spelling in aliases. Never write before they answer.

```text
Services registry — <n> candidates (<s> from ServiceNow, <m> from the Application Map)
1. Order Management  ← cmdb_ci_service, owner none; 3 application tiers in the map
2. Cloud Management  ← cmdb_ci_service, owner Cloud Ops
Reply with: the numbers to keep (rename with "2 = Log platform"),
"reject <n>" for non-services, and an owner with "owner 1 = NetOps".
```

Zero candidates: say so in one line and stop. Do not write an
empty registry over an existing one.

## Write — only what they confirmed

Rows they kept → `services[]`:

- `name` — their spelling if they renamed, else your proposal.
  Exactly this string follows `service:`.
- `aliases[]` — every source string for that candidate, plus any
  they added. Do not add the canonical name to its own aliases.
- `owner` — `owned_by` / `support_group` from S, or what they
  typed, else null.
- `source_ref` — `servicenow:cmdb_ci_service/<sys_id>` for S and
  M (both carry the sys_id), `user` for a row they typed that no
  source named.
- `confirmed_by` `user`, `confirmed_at` this invoke.

Rows they rejected → append each source string to
`candidates_rejected[]`. Keep prior `services[]` rows unchanged
unless they renamed or removed one this turn; a removed row's
name goes to `candidates_rejected[]`.

`keys` = one `service:<name>` per row, same order. `updated_at`
this invoke. `source_agent` `ops-snow-mcp`. Write
`inventory/services.json`. Read it back. This is the one path
under `inventory/` you write.

Do not write `inventory/applications.json`. When a kept row came
from M, say so: the next `Run the application map only.` flips
that service to `registered` and writes `service` on its
application rows.

## Reply

```text
Status: succeeded | needs_approval | failed
Action: registry
Record: inventory/services.json — <k> services, <r> rejected
Services: <name> (<alias count> aliases); ...
Ask: none | <the candidate block above when nothing is confirmed yet>
```

`needs_approval` is the state while you wait for their answer:
nothing has been written.
