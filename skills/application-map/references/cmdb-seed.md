# What the CMDB must contain

The Application Map reads; it never creates a CI. An operator (or
Cursor, over the Table API) seeds these records once. Spellings are
the contract between the CMDB, Grafana, and `inventory/prod.json`.

| Table | One row per | `name` must equal | Other columns |
|-------|-------------|-------------------|---------------|
| `cmdb_ci_service` | business service | the registry `services[].name` (or an alias) | `comments` carries the lab marker |
| `cmdb_ci_appl` | application tier | the Grafana `service` label on that tier's probe and container (`web`, not `dc-web` and `web`) | `comments` carries the lab marker; `short_description` free |
| `cmdb_ci_server` | host | the `inventory/prod.json` `devices[].name` (the Prometheus `host_name` label should match it too) | `comments` carries the lab marker; `ip_address` optional |

| `cmdb_rel_ci` | `parent` | `type` | `child` | Meaning |
|---------------|----------|--------|---------|---------|
| service → tier | `cmdb_ci_service` | `Depends on::Used by` | `cmdb_ci_appl` | service depends on this tier |
| tier → tier | `cmdb_ci_appl` | `Depends on::Used by` | `cmdb_ci_appl` | web depends on api, api on database |
| tier → host | `cmdb_ci_appl` | `Runs on::Runs` | `cmdb_ci_server` | tier runs on this host |

Rules:

- The marker is the same string the lab tickets use
  (`servicenow/metadata-lab.json` `servicenow.marker`). It goes in
  `comments` on every seeded CI so one `commentsLIKE` scopes each
  query. It is never written into a prompt or skill.
- Standard relationship types only. `Contains::Contained by`,
  `Hosted on::Hosts`, and `Uses::Used by` are ignored by the map.
- A tier the probes test but no container runs (or the reverse) is
  still one `cmdb_ci_appl` row; the Analyzer sees the gap through
  the compiled edges, not through two names.
- A host that is not in `prod.json` still gets a `cmdb_ci_server`
  row; the map lists it under `hosts_unmapped[]` until Ops Network
  Sync picks the node up.
- Renaming a tier means renaming it in Grafana relabel config and
  the CMDB in the same change; the compiler does not alias.
