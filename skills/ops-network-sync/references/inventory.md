# Canonical inventory (`inventory/prod.json` / `dev.json`)

These files are the **canonical accumulating inventories** and the
**published access snapshots**. Merge in place. Do not replace a
last-known-good file with a failed collect. Keep unknown and
user-authored keys on merge (`additionalProperties` is true).

Schema `network-access-inventory/v3`. Prior `v2` files are retired;
rewrite on the next successful collect (preserve extra keys).

`state/network-sync.json` is **not** this file. GitHub Actions runs and
logs are durable workflow evidence. Do not copy raw job logs or
configurations into the workspace.

Do not store passwords, tokens, usernames, or API keys. `credential_ref`
is a name only (`iosxe-lab`).

## Header

Required on every published write:

| Field | Meaning |
|-------|---------|
| `snapshot_id` | Stamp of this published snapshot (`YYYY-MM-DDTHH-MM-SSZ`). State `current_snapshot.snapshot_id` must match. |
| `environment` | `prod` or `dev` |
| `collected_at` | When source evidence was collected (UTC) |
| `published_at` | When this merged file was written (UTC) |
| `expires_at` | After this instant, PAT/access is **stale**. Default `collected_at` + 26h |
| `status` | `complete` or `partial` only. Failed collects are **not** published |
| `coverage` | Collection coverage (below) |
| `source` | `{ "type", "name" }` — collect from this |
| `infra_sot` | `git` or `netbox` |
| `lab_title` | CML / lab identity |
| `lab_id` | CML UUID or null |
| `netbox.tenant` / `netbox.site` | identifiers; never a customer-name default |
| `devices` / `device_count` | merge by `name` |
| `links` | known links; `[]` if none yet |

`source.type`: `document` | `api` | `cml` | `netbox` | `excel` | `other`.
`source.name` is the lab title (CML) or document name.

| `source.type` | Collect from |
|---------------|----------------|
| `document` | User list already in the json |
| `api` | Live RESTCONF / mgmt — merge `access` |
| `cml` | CML lab — merge tags + PAT into `access` |

## Freshness

| Condition | Reader |
|-----------|--------|
| `now < expires_at` | **Current.** PAT and access may be used as live access information. |
| `now >= expires_at` | **Stale.** Inspect identity and last-known structure. Do **not** treat PAT, SSH, or RESTCONF ports as current access. Collect again. |

`published_at` is write time. It is not the freshness clock.

## Coverage

| Field | Meaning |
|-------|---------|
| `state` | `complete` or `partial` on a published file. Never `unavailable` here |
| `devices_discovered` | Nodes found in source evidence |
| `devices_inspected` | Nodes you actually read (tags/info) |
| `accessible_devices` | `agent_access` true |
| `missing_device_info` | Names you could not inspect |
| `missing_restconf` / `missing_ssh` | Names with that endpoint null |

Do not publish a file whose coverage is `unavailable`. That belongs only on
`latest_attempt` in state after a failed collect. Do not write zeros for
“we could not talk to CML.”

## Create vs merge

| Workspace | Do |
|-----------|----|
| No `inventory/prod.json` | **Create.** Interview (only then). Write json, then state. |
| `prod.json` exists | **Merge.** No interview. Collect from `source`, update devices and known links in place. Successful collect **is** this file. |

Interview when empty (at most):

1. Existing SoT / list / “new network”?
2. `source.type`: document / api / cml
3. Infra in NetBox? (`infra_sot`)
4. **Tenant and site** — ask. No NetBox MCP; do not call `netbox_find`.
   No answer: slug of `lab_title`, else `lab-<utc-date>`. **Never** default
   a customer name.

## Device fields (merge, do not wipe)

Keep unknown keys. Always try to have:

- `name`, `platform`, `role`
- `tags` — intent tags only (`tag:simulate`, `tag:sync`, `site:*`, …). Drop `pat:*` and `synced:*` from this list.
- `operational_state`, `agent_access`
- `access.restconf` / `access.ssh` — `{ host, port }` or null. Never invent a port.
- `source_metadata`

`source.type` `cml`: PAT `pat:<port>:443` → `access.restconf` (`protocol`
`https`); `pat:<port>:22` → `access.ssh`. Host = CML controller from the lab
record.

## When to refresh

- Operator asks for inventory, device access, or PAT ports
- After a successful named `deploy-twin` / `reconcile-dev` (Twin's runner — Dev PAT ports are new)
- After a successful `sync-prod` / `sync-dev` if asked to refresh access, or
  when the existing file is missing or **stale**

## CML — read only

Allowed:

- `cml_list_labs`
- `cml_get_lab_details` (`include_configurations=false`)
- `cml_get_node_info` (`include_configuration=false`)
- `cml_find_nodes_by_tags` if lab details omit tags

Forbidden during inventory refresh: create/add/remove/connect, start/stop,
`cml_apply_configs`, `cml_manage_node_tags`, any topology or config write.

Keep Prod and Dev as separate files even when hostnames match. Never copy a
port from one environment to the other.

## Resolve lab titles

1. Prior inventory `lab_title` / `source.name`, or state
   `inventories.*.current_snapshot` plus the inventory file
2. Repository variables `PROD_NETWORK` / `DEV_NETWORK` if a job log already
   printed them
3. Exact titles on `cml_list_labs` that match those names

Never invent a lab title. If you cannot resolve one, record a **failed
attempt** in state and leave the last-known-good inventory file untouched.
Do not hardcode lab titles in this skill.

Controller host for `access.*.host` is the CML controller hostname from the
lab record or prior inventory. Never guess a new hostname. Never guess a port.

## PAT tags

Parse node tags only:

- `pat:<external-port>:443` → `access.restconf` (`protocol` `https`)
- `pat:<external-port>:22` → `access.ssh`

No matching tag → that endpoint is `null`. `agent_access` is true only when
at least one of restconf or ssh has host and port. Never invent a port.

`cml_get_lab_details` often returns empty `tags`. Confirm with
`cml_get_node_info` or `cml_find_nodes_by_tags` before concluding there are
no PAT tags.

## Normalize a node

Skip `external_connector` and `unmanaged_switch`.

| node_definition | platform |
|-----------------|----------|
| `cat8000v`, `iosv`, `csr1000v`, `iosvl2` | `iosxe` |
| `nxosv`, `nxosv9000` | `nxos` |
| `asav` | `asa` |
| `ubuntu`, `alpine`, `server` | `linux` |

Role: first of `wan`, `edge`, `branch`, `hq`, `cloud` found in tags, else
`unknown`. Do not invent a role from the hostname.

`source_metadata` for CML: `lab_id`, `lab_title`, `node_id`,
`node_definition`, `pat_tags` (the `pat:*` strings only).

`status` on the published file:

- `complete` — every included node inspected; ports present or explicitly null
- `partial` — some nodes missing tags/info, or some `agent_access` false

After a successful prod write, compare simulate seed to
`inventory/infra-sot.json` (`ops-network-sync` Seed gate) only to decide whether
to invoke Ops NetBox SoT. Do not put NetBox ids or interfaces into this inventory
file. Do not write `state/netbox.json`.

Ops NetBox SoT copies json `tags` onto the device. RESTCONF uses json `access`.

## Failed collect

If CML is unreachable or the lab is missing: do **not** write this inventory.
Update only `state/network-sync.json` `latest_attempt` (coverage `unavailable`,
counts **null**, not zero). Leave `current_snapshot` pointing at the prior
file. Readers distinguish a failed refresh from “no inventory.”

## Other sources

A future NetBox/Excel collector fills the same top-level and `access` fields
and puts native ids in `source_metadata`.
