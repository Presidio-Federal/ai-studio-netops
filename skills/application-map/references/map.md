# Map — `inventory/applications.json`

You copy the CMDB's application model into one workspace file. The
CMDB already says which service depends on which application,
which application depends on which, and which server each runs
on; you copy those rows and look up spellings. You do not decide
what an application is or where it runs.

Schema: `schemas/applications.schema.json`. Example:
`examples/applications.example.json`. What the CMDB must contain:
`references/cmdb-seed.md`.

## 1. Read (four at most, this order)

| # | Path | Take |
|---|------|------|
| 1 | `inventory/applications.json` (prior) | `source_updated_at` |
| 2 | `inventory/prod.json` | `devices[].name` |
| 3 | `inventory/services.json` | `services[].name`, `services[].aliases[]` (missing is fine) |
| 4 | `servicenow/metadata-lab.json`, else `health/metadata-servicenow.json` | `servicenow.marker` |

No marker in either file → reply `Need: marker (servicenow/metadata-lab.json servicenow.marker)` and stop.
Do not read anything else. Do not list `inventory/`, `health/`, or
`servicenow/`.

## 2. Query (four `snow_query_table` calls, copied exactly)

`<marker>` is the string from step 1. The marker lives in each
CI's `comments` column; every query scopes on it so the payload is
this lab's. Do not widen a query. Do not query by class alone.

**A — applications**

```text
snow_query_table(table="cmdb_ci_appl", query="commentsLIKE<marker>",
  fields="sys_id,name,short_description,operational_status,sys_updated_on", limit=50)
```

**S — business services**

```text
snow_query_table(table="cmdb_ci_service", query="commentsLIKE<marker>",
  fields="sys_id,name,operational_status,sys_updated_on", limit=50)
```

**H — servers**

```text
snow_query_table(table="cmdb_ci_server", query="commentsLIKE<marker>",
  fields="sys_id,name,ip_address,sys_updated_on", limit=50)
```

**R — relationships**

```text
snow_query_table(table="cmdb_rel_ci", query="parent.commentsLIKE<marker>^ORchild.commentsLIKE<marker>",
  fields="sys_id,parent,child,type,sys_updated_on", limit=50)
```

Reference columns come back as `{sys_id, display}`: `parent` and
`child` carry the CI name in `display`; `type` carries the
relationship name in `display` (for example `Depends on::Used by`,
`Runs on::Runs`). Match rows by `sys_id`, never by name.

A failed call is retried once with the same arguments. A failing
twice → do not write; reply `unavailable`. R failing twice with A
good → write applications with empty `hosts[]`, `depends_on[]`,
`service` null and `status` `partial`. S or H failing → the
affected columns null / empty, `status` `partial`.

**No-op.** `source_updated_at` = the newest `sys_updated_on` across
A, S, H, R rows. Equal to the prior file's and the prior exists →
write nothing; reply the no-op line.

## 3. Build `applications[]` — one row per A row

| Column | From |
|--------|------|
| `name` | A `name` as written. This is the `application:` spelling; it must equal the Grafana `service` label, and you do not rename it. |
| `source_ref` | `servicenow:cmdb_ci_appl/<sys_id>` |
| `operational_status` | A `operational_status` display text |
| `service_ci` | the `display` of the `parent` on an R row whose `type.display` is `Depends on::Used by`, whose `child.sys_id` is this app, and whose `parent.sys_id` is an S row. Several → the alphabetically first; list the others in `notes`. None → null. |
| `service` | `service_ci` matched case-insensitively against `services[].name` or `aliases[]` → that row's `name`; no match or no registry → null |
| `hosts[]` | the `display` of the `child` on every R row whose `type.display` is `Runs on::Runs` and whose `parent.sys_id` is this app, **when** that name equals a `prod.json` `devices[].name` case-insensitively — write the `prod.json` spelling. Sorted. |
| `hosts_unmapped[]` | the same R children whose name is not in `prod.json` (text only; the compiler ignores them) |
| `depends_on[]` | the `display` of the `child` on every R row whose `type.display` is `Depends on::Used by`, whose `parent.sys_id` is this app, and whose `child.sys_id` is another A row. Sorted. |
| `notes` | one line or null: a second service, a relationship whose other end is in no A/S/H row, a host not in `prod.json` |

`services[]` — one row per S row: `name`, `sys_id`, `registered`
(true when it matched the registry). `servers[]` — one row per H
row: `name`, `sys_id`, `device` (the `prod.json` spelling, else
null).

An R row whose `type.display` is anything else (`Contains`,
`Hosted on`, `Uses`) is ignored and counted in `relations_ignored`.
Do not translate it into one of the three columns.

## 4. Envelope and write

- `schema` `applications/v1`; `source_agent` `application-map`;
  `updated_at` this invoke; `source_updated_at` from step 2;
  `marker_ref` the path the marker came from.
- `status`: `ok` when A, S, H, R all returned; `partial` when some
  failed; `unavailable` is never written (see step 2).
- `headline`: counts (applications, services, hosts mapped /
  unmapped, dependencies) and what is missing — a service CI not in
  the registry, a host not in `prod.json`, an application with no
  host. One line. Names, not sys_ids.
- `next_action`: `none`; or `Run the services registry: <service_ci>`
  when a `service_ci` has `registered` false; or `Add to prod.json:
  <host>` when `hosts_unmapped[]` is non-empty. One of them, most
  useful first.
- `keys` = `application:<name>` for every row, `service:<service>`
  for every non-null `service`, `device:<host>` for every mapped
  host. Deduplicated. Never a `service:` from `service_ci`.

`write_file` `inventory/applications.json`, replace in full, read
it back. One write.

## Budget

≤ 4 `read_file`, 4 `snow_query_table` (plus one retry each),
1 `write_file`, 1 read-back. No `snow_create_*`, `snow_update_*`,
`snow_find_*`, or `snow_get_*`. No `execute_command`.

## Reply

```text
Result: <ok | partial | unavailable | no-op>
Wrote: <inventory/applications.json | none — CMDB unchanged since <source_updated_at>>
Applications: <n> (<h> on a prod.json host, <u> unmapped hosts, <d> dependencies)
Services: <name> (registered) ; <name> (not in registry) ; none
Next: <next_action>
Gaps:
- <thing>: <why>
```

Omit `Gaps:` when none. A relationship type you ignored is a gap.
