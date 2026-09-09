# Inventory for populate

This agent reads **`inventory/prod.json` only** for seed
(`network-access-inventory/v1`). Do not open yaml.

Writes:

| File | Role |
|------|------|
| `inventory/infra-sot.json` | Details — id map (`infra-sot/v1`) |
| `state/netbox.json` | Summary — in sync or not (`netbox-state/v1`) |

Never write `state/network-sync.json`.

Missing json → stop (Network Sync). Do not onboard. Do not invent PAT.

## Json fields

| Need | Field |
|------|--------|
| source | `source.type` (`cml` / `api` / `document`) |
| tenant / site / lab slug | `source.name` |
| node name | `devices[].name` |
| platform / role | `devices[].platform` / `role` |
| type slug | `devices[].source_metadata.node_definition` |
| tags | `devices[].tags` (seed filter `tag:simulate`; drop `pat:*` / `synced:*`) |
| RESTCONF | `devices[].access.restconf.host` + `port` (object or `null`) |
| SSH | `devices[].access.ssh.host` + `port` (not used for SoT) |

Treat as NetBox unless `state/netbox.json` says `kind: git`. Do not read
`state/network-sync.json` for that flag.

## Seed

| `source.type` | Seed |
|---------------|------|
| `cml` | Only devices with exact tag **`tag:simulate`** |
| `api` | Entries with RESTCONF access |
| `document` | As given; RESTCONF only if filled |
| `state/netbox.json` `kind: git` | Do **not** populate NetBox |

RESTCONF GET when `access.restconf` is an object with host+port **and**
modes.md says GET is required. `refresh` is audit (GET + compare, no
NetBox write).
iosvl2 / ASA / FTD / stopped NX with `restconf: null`: create the **device**
in `bootstrap` / `reconcile` only.
Do not invent interfaces. CDP may add a far-end interface later.

## Tenant

List tenants. Use `source.name` if that tenant exists or we create it.
Never a customer default. Same-name device in another tenant → skip.

## Tags on NetBox devices

`[{ "slug": "{source.name}-simulate" }, …]` — see populate.md.

After bootstrap, audit, or reconcile, write the snap then the summary.
Board fields: `references/state.md`.
