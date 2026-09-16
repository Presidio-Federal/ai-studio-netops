# Populate — proven lockstep (NetBox 4.6.4)

This was verified against the live NetBox Cloud API and live IOS-XE RESTCONF
(CML PAT). Map vendor fields **here**. Send NetBox REST bodies. A 400 is a
bad field. Fix that field.

**Mode first:** [modes.md](modes.md). `bootstrap` uses this file to **create
missing** objects. `reconcile` uses it to apply **approved** creates/updates.
`audit` does not write NetBox. `refresh` is audit.

## What the SoT must contain

Enough for a digital twin:

- One **tenant** for this lab (`source.name` from inventory — e.g. `example-lab-prod`)
- One **site** on that tenant (same slug)
- **Devices** for every inventory row with `tag:simulate`
- **Interfaces + IPv4** from IOS-XE RESTCONF (not invented)
- **Cables** from IOS-XE CDP (not invented)
- Namespaced **tags** so CML can select `{tenant}-simulate`

Git stays the config SoT. NetBox is infrastructure only.

## Inventory — `inventory/prod.json` only

Read `inventory/prod.json` (`network-access-inventory/v1`).
**Do not read `prod.yaml`.** It is not in the Studio workspace.

Missing json → stop. Network Sync owns collect.

Seed = devices whose `tags` contain exact `tag:simulate`.

| Need | Field |
|------|--------|
| Lab / tenant / site slug | `source.name` |
| Device name | `devices[].name` |
| Role slug | `devices[].role` (`wan`, `edge`, …). If `unknown`, use role slug `unknown` |
| Type slug | `devices[].source_metadata.node_definition` (`cat8000v`, `iosvl2`, …) |
| RESTCONF | `devices[].access.restconf.host` + `.port` (null = no GET) |
| Intent tags | `tag:simulate` `tag:sync` `site:wan` — drop `pat:*` / `synced:*` |

`agent_access` true only means a PAT exists. RESTCONF GET still requires
`access.restconf` not null **and** GET is required (modes.md). Never
guess a port. Never use 443 unless that is the json port.

## Tools

| Step | Tool |
|------|------|
| Inventory | workspace `read_file` on `inventory/prod.json` |
| Id map | workspace `read_file` / `write_file` on `inventory/infra-sot.json` |
| Summary | workspace `write_file` on `state/netbox.json` |
| Live box | **`iosxe_get_platform_and_yang`** (version) then **`iosxe_restconf_get`** — when restconf host+port exist **and** GET is required (below) |
| One parent (tenant, site, type, role, tag) | snap id, else `netbox_find` then `netbox_manage` |
| Many devices / interfaces / IPs / cables | snap ids, else `netbox_find` then **`netbox_bulk`** |

If a box has RESTCONF in json and GET is required and you have not called
`iosxe_restconf_get` for that host+port, you may **not** write or audit its
interfaces yet. Same visit: `iosxe_get_platform_and_yang` for
`software_version` (null on fail).

No PUT/PATCH/DELETE/save/SSH on IOS-XE. Do not loop `netbox_manage` per
interface. There is no `netbox_sync_device`.

`netbox_bulk` is `create` or `update` only (not upsert). `update` requires
`id` on every row. Prefer snap ids. Find only when the snap has no id for
that name, or a write returns 404.

## `inventory/infra-sot.json` (id map)

Schema: `schemas/infra-sot.schema.json`. Example:
`examples/infra-sot.example.json`. Envelope + `seed` + parent/device/interface
/cable **ids** + `devices[].software_version`. Names stay next to ids. Do not put this in prod.json.

**Seed** (this agent compares it): simulate devices from prod.json, each
`name`, `host` (`access.restconf.host` or null), `port` (`access.restconf.port`
or null), `node_definition`. Sort by `name`. Store that list as `seed`.
Compare lists. Do not hash.

### When you start

1. Read `inventory/prod.json`, `state/netbox.json` (missing is ok), and
   `inventory/infra-sot.json` (missing is ok).
   `state/netbox.json` `kind: git` → stop (do not populate).
2. Recompute seed from prod.json.
3. Resolve **mode** ([modes.md](modes.md)). Do not infer `reconcile` from
   `refresh`. Onboard / `populate` / `bootstrap` → `bootstrap` even if the
   snap is `ok`.
4. `audit` → compare only (modes.md). No NetBox writes. Rewrite snap envelope
   + `state/netbox.json` with `mode: audit`. Stop.
5. `bootstrap` or `reconcile` → continue this file. GET when modes.md says so.

### First populate (no snap) — `bootstrap`

Current sequence below. After each create/bulk, copy returned `id`s into the
snap (parents, devices, interfaces, `ip_id`, cables). Then write the full
`inventory/infra-sot.json`. Then write `state/netbox.json` (summary; ids stay
in the snap). `mode` = `bootstrap`.

### Later `bootstrap` (snap present)

Create **missing** names only. Do **not** `netbox_bulk` `update` an existing
snap id (that overwrites curated NetBox).

- Do **not** `netbox_find` interfaces per device when the snap has them.
- New names (new box, new interface) → `create`, append ids to the snap.
- Known device/interface names → skip the row.
- IPs: missing → create and store `ip_id`. Existing `ip_id` → skip.
- Cables: existing cable `id` or unordered pair → skip. New pair → create.
- `primary_ip4` already set → skip. Null + static IPv4 → set once.
- HTTP 404 on an id → one `netbox_find` for that object (or tenant devices if
  many 404s). Rewrite those ids. Do not find everything “to be sure.”

### Later `reconcile` (approved set only)

Approved rows may `update` with snap `id`. Unapproved existing objects stay.
Otherwise same id-map rules as bootstrap for **new** names.

- Known approved names → `netbox_bulk` `update` with `id` from the snap.
- New names in the approved set → `create`, append ids to the snap.
- IPs: approved change with existing `ip_id` → update that IP; missing →
  create and store `ip_id`.
- Cables: approved new pair → create. Approved delete → `netbox_delete`
  `confirm=true` only when the operator named the delete.
- HTTP 404 on an id → one `netbox_find` for that object. Rewrite those ids.

After a successful **bootstrap** or **reconcile** push, set `netbox_pushed_at`,
rewrite the snap (`mode` set), then rewrite `state/netbox.json`. Audit does
not set `netbox_pushed_at`.

## Proven 400s (do not repeat)

| You sent | API |
|----------|-----|
| `device_type`: `"Cisco Catalyst 8000v"` | `Related object not found … {'slug': 'Cisco Catalyst 8000v'}` |
| `tags`: `["example-lab-prod-simulate"]` | `Related objects must be referenced by numeric ID or by dictionary of attributes` |

## Related objects — slugs, not display names

NetBox 4.6 Cloud accepts related objects as **id** or **`{"slug": "…"}`**.
Bare display names are not slugs.

`device_type` = CML `node_definition` slug. Find it first.

| node_definition | Find slug (in order) | RESTCONF? |
|-----------------|----------------------|-----------|
| `cat8000v` | `cat8000v` | yes if `access.restconf` |
| `iosvl2` | `iosvl2` | no PAT in this lab |
| `nxosv9000` | `nxosv9000`, else existing `nxos` | skip GET unless restconf and BOOTED |
| `asav` | `asav` | no |
| `ftdv` | `ftdv` | no |
| linux / Splunk | skip (not `tag:simulate` here) | no |

Create a missing type with **the same string** for `model` and `slug`:

```
netbox_manage action=create object_type=device_type
data={ "model": "cat8000v", "slug": "cat8000v", "manufacturer": { "slug": "cisco" }, "u_height": 1 }
```

Manufacturer: `{ "name": "cisco", "slug": "cisco" }`.
Role: `{ "name": "wan", "slug": "wan" }` (use inventory `role`).

### Tags (this instance)

Create `{ "name": "<slug>", "slug": "<slug>" }` with `netbox_manage`.
On the **device**, always a JSON array of dicts:

```
"tags": [
  { "slug": "example-lab-prod-simulate" },
  { "slug": "example-lab-prod-sync" },
  { "slug": "example-lab-prod-site-wan" }
]
```

Map inventory → NetBox: `tag:X` → `{tenant}-X`; `site:X` → `{tenant}-site-X`.
Do not copy bare `wan` / `edge` as NetBox tags.

## Sequence

### 1. Tenant

Snap `parents.tenant.id` → use it. Else
`netbox_find(object_type="tenant", name=<source.name>)`.
Exists → use it. Missing → `netbox_manage` create `name` + `slug` =
`source.name`. Never a customer default. Never another tenant. Store `id`.

### 2. Site on that tenant

Snap `parents.site.id` → use it. Else find `slug=source.name`. Missing →
`netbox_manage` create `name`, `slug`, `status=active`,
`tenant={"slug": "<source.name>"}`. Store `id`.

### 3–6. Manufacturer, device types, roles, tags

Snap `parents.*` ids → use them. Else find each. `netbox_manage` create only
if missing. Types from unique simulate `node_definition` values (with the
nxos alias above). Store each `id` on the snap.

### 7. Device shells

Snap `devices[].id` for known names. No snap → find devices with
`tenant=source.name`. Split missing vs existing.

Missing → **`netbox_bulk` create** `object_type=device` (one array, not a
loop). Existing that need a field fix → **`netbox_bulk` update** with `id`
on every row (from snap, or from find on first populate).

```
netbox_bulk action=create object_type=device
data=[
  {
    "name": "WAN-04",
    "status": "active",
    "site": { "slug": "example-lab-prod" },
    "role": { "slug": "wan" },
    "device_type": { "slug": "cat8000v" },
    "tenant": { "slug": "example-lab-prod" },
    "tags": [
      { "slug": "example-lab-prod-simulate" },
      { "slug": "example-lab-prod-sync" },
      { "slug": "example-lab-prod-site-wan" }
    ]
  }
]
```

No interfaces on this call. Record each device `id` on the snap.

### 8. Interfaces and IPs (IOS-XE)

If GET is required (modes.md) and you have not already this run:
`iosxe_restconf_get` path `Cisco-IOS-XE-native:native/interface`.

Map **in this skill** (MCP will not):

| GET | NetBox |
|-----|--------|
| GigabitEthernet + `name` `"1"` | `name`: `GigabitEthernet1`, `type`: `1000base-t` |
| Loopback + `name` `0` | `name`: `Loopback0`, `type`: `virtual` |
| `255.255.255.252` | `/30` |
| `255.255.255.255` | `/32` |

`shutdown` present → `enabled: false`. No primary address → interface only.

Snap has this `device`+`name` → that interface `id`. Do **not**
`netbox_find` interfaces per device when the snap has them. Split new vs
existing from the snap. Then **one bulk per action**, not one manage per row:

```
netbox_bulk action=create object_type=interface
data=[
  { "device": "WAN-01", "name": "GigabitEthernet1", "type": "1000base-t", "enabled": true, "description": "Link to WAN-02 (Gig1)" },
  { "device": "WAN-01", "name": "Loopback0", "type": "virtual", "enabled": true }
]
```

You may put every simulate device's new interfaces in that same array.

`bootstrap`: existing names → skip (no update). `reconcile` approved rows →
`netbox_bulk` `action=update` with `id` on each row (from the snap). Record
new ids after create.

Then IPs. `assigned_object_id` is the interface id from the snap or create.
`bootstrap`: new → bulk create; existing `ip_id` → skip. `reconcile`:
approved new → create; approved existing → bulk update with `ip_id`.

```
netbox_bulk action=create object_type=ip_address
data=[
  {
    "address": "10.1.1.1/30",
    "status": "active",
    "assigned_object_type": "dcim.interface",
    "assigned_object_id": <id>,
    "tenant": { "slug": "example-lab-prod" }
  }
]
```

GET failed → device only. No restconf in json → device only.

Then set device `primary_ip4` for **every** seed device that has at least
one static IPv4. Pick in this order (stop at the first hit):

1. `Loopback0` with a static IPv4 (WAN-01…04).
2. Else the first static IPv4 in native GET order (AI-CLOUD-EDGE →
   GigabitEthernet1 `10.10.10.1/24`; HQ/DC/BRANCH → GigabitEthernet1 WAN).

`ip address dhcp`, empty Loopback (`no ip address`), and shutdown-only
interfaces are not candidates. Do not invent DHCP leases. Do not skip a
device because it has no Loopback.

`bootstrap`: one `netbox_manage` update per device whose `primary_ip4` is
null: `primary_ip4` = that IP **id**. Already set → skip. `reconcile`:
change `primary_ip4` only if that device is in the approved set.
Seed device has a static IPv4 and `primary_ip4` is still null after
bootstrap/reconcile should have set it → gap.

### 9. CDP cables

If GET is required (modes.md) and you have not already this run:
`iosxe_restconf_get` path `Cisco-IOS-XE-cdp-oper:cdp-neighbor-details`.

Walk **every seed box in inventory order**, then **every neighbor row in
GET order**. One pass. No scoring.

Each row:

| CDP | Meaning |
|-----|---------|
| this box | local device |
| `local-intf-name` | local interface (expand `Gi` → `GigabitEthernet`, strip spaces) |
| `device-name` | far device = text before first `.`, match seed name case-insensitive |
| `port-id` | far interface (same expand) |

Skip the row if:

- far name is not a seed device (`cloud-switch` → gap, do not create it)
- local or far name is Loopback / Vlan / mgmt
- you cannot resolve both interface ids (snap or create)
- either interface id is already on a cable you accepted
- the unordered pair of ids was already accepted (other end of the same link)

Keep the row otherwise. Do not prefer "both sides see each other". Do not
drop a row because CDP is asymmetric. Do not invent a far device.

Then write cables only in `bootstrap` / `reconcile`. Prefer snap `a_id` /
`b_id`. One cable → `netbox_manage`. Many → one `netbox_bulk`. XML `<item>`
is fine; the MCP unwraps to NetBox arrays. Do not invent `type="array"` or
retry six times. `object_id` is a number. Record each cable `id` on the snap.
`bootstrap`: skip pairs that already have a cable id. `audit`: do not write.

```
netbox_manage action=create object_type=cable
data={
  "status": "connected",
  "a_terminations": [{ "object_type": "dcim.interface", "object_id": 8334 }],
  "b_terminations": [{ "object_type": "dcim.interface", "object_id": 8345 }]
}
```

If `missing: a_terminations` or `data must be a list of objects`, stop.
Restart netbox-mcp (old pass-through), then retry once.

### 10. Snap + state

Write **details** then **summary**. Never write `state/network-sync.json`.

1. `inventory/infra-sot.json` (`infra-sot/v1`) — `mode`, seed, parent/device/interface/cable
   ids, counts, gaps, `netbox_pushed_at`.
2. `state/netbox.json` (`netbox-state/v1`) — `mode`, headline, status, counts, **`links[]`**
   (names from snap cables), `kind`, tenant/site, `seed_match`,
   `details: inventory/infra-sot.json`. Field list: `references/state.md`.
   Empty `links` after CDP on restconf seed is a gap.

`audit` (including unnamed seed-match): rewrite both files from the existing
snap (`updated_at`, `mode`, `gaps`, headline). Keep ids. Do not set
`netbox_pushed_at`.

## Isolation

Find-by-name + other tenant → skip. No delete on `bootstrap`. Delete only
on `reconcile` when the operator named it (`netbox_delete` `confirm=true`).
Untenanted same name: attach **our** tenant (`netbox_manage` update) during
bootstrap/reconcile, do not duplicate. Audit does not attach.
