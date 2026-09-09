# SoT from IOS-XE RESTCONF

Parents and slugs: [populate.md](populate.md) **first**. This file is GET
paths and the vendor → NetBox map. The MCP will not map names or masks.

Orchestrate **`iosxe_restconf_get`** when modes.md says GET is required.
Then `netbox_bulk` / `netbox_manage` only in **`bootstrap`** (create missing)
or **`reconcile`** (approved rows). **`audit`** compares; it does not write
NetBox. Do not write config on the box. Do not dump GET JSON into NetBox
`data`. `refresh` is audit.

Read [environment.md](environment.md). RESTCONF GET using
`inventory/prod.json` `access.restconf`. `device_type` =
`source_metadata.node_definition` slug (`cat8000v`), never a display name.

Always pass **our** `tenant` + `site`. Device `id` from
`inventory/infra-sot.json` when present. Else find the device first. Other
tenant → do not write. Never a customer-name default.

## Seed

If `source.type` is `cml`, the seed is **only** devices whose `tags` contain
`tag:simulate` (exact). Zero simulate nodes → stop and say so.

`api` / `document`: every entry with RESTCONF access.

| Need | `prod.json` |
|------|-------------|
| name | `devices[].name` |
| host + port | `access.restconf.host` / `port` |
| tenant / site | `source.name` |
| role / type | `role` + `source_metadata.node_definition` **slug** |
| tags | `tags` minus `pat:*` / `synced:*` |

## CML tags → NetBox (namespaced)

Inventory keeps `tag:simulate` as the CML selector. **NetBox tags are global**
— do not create bare `simulate` / `sync` / `site-hq` that collide with the
rest of the instance.

Map each intent tag to `{tenant-slug}-` + the part after `tag:` or `site:`:

| Inventory | NetBox tag name / slug |
|-----------|------------------------|
| `tag:simulate` | `{tenant}-simulate` |
| `tag:sync` | `{tenant}-sync` |
| `site:hq` | `{tenant}-site-hq` |

Find the tag; `netbox_manage` create only if missing. On the device pass
`[{ "slug": "{tenant}-simulate" }, …]`.
Drop `pat:*` / `synced:*`. Do not invent tags.

## Default live read

Same host + port as inventory (never 443 unless that is the real PAT).

```
iosxe_get_platform_and_yang
  host / port: from inventory
```

Do **not** pass `yang_model` or `list_modules`. Record `version` on the
snap as `devices[].software_version`. Do **not** use `platform_info` to
change `device_type` — type stays `source_metadata.node_definition`.
Fail or no RESTCONF → `software_version` null; still create the device
shell; Gaps.

```
iosxe_restconf_get
  path: Cisco-IOS-XE-native:native/interface
  host / port: from inventory
```

Map each GET row to a NetBox interface body. `bootstrap` / `reconcile`:
`netbox_bulk` as in populate.md. `audit`: compare only.

## Extra paths

| Path / tool | Why |
|-------------|-----|
| `iosxe_get_platform_and_yang` (no YANG args) | Live `version` → snap `software_version` |
| `Cisco-IOS-XE-native:native/hostname` | Confirm NetBox device `name` |
| `Cisco-IOS-XE-native:native/interface` | Interfaces + IPv4 primaries/secondaries |
| `Cisco-IOS-XE-cdp-oper:cdp-neighbor-details` | Cables. Fields: `device-name`, `local-intf-name`, `port-id` |
| `Cisco-IOS-XE-lldp-oper:lldp-entries` | Only if CDP 404s. This lab had LLDP disabled. |

If an **interface or CDP** path 404s, `iosxe_get_platform_and_yang(list_modules=true)` and pick the oper module for that version. Then GET again — do not SSH. That is not a substitute for the version call above.

## Interface name / type (you map this)

YANG key + instance name. Set NetBox `type` yourself. The MCP will not.

| YANG | `name` field | NetBox `name` | NetBox `type` |
|------|--------------|---------------|---------------|
| GigabitEthernet | `1/0/1` | `GigabitEthernet1/0/1` | `1000base-t` |
| TenGigabitEthernet | `0/0/0/0` | `TenGigabitEthernet0/0/0/0` | `10gbase-x-sfpp` |
| Loopback | `0` | `Loopback0` | `virtual` |
| Port-channel | `1` | `Port-channel1` | `lag` |
| Vlan | `100` | `Vlan100` | `virtual` |

If `name` already includes the type prefix, it is not doubled.
IOS `shutdown` present (`true`, `[null]`, `{}`) → `enabled=false`.
`ip.address.primary` / `secondary` address + dotted mask → `10.1.1.1/24`.

Do not map IPv6. After IPs exist, set device `primary_ip4` (`netbox_manage`)
in `bootstrap` (only when null) or `reconcile` (if approved): Loopback0 if
that interface has an address, else the first static IPv4 in native GET
order. DHCP and empty Loopback are not IPs. Do not leave HQ/DC/BRANCH with
interface IPs and a null primary because they have no Loopback. Audit does
not set `primary_ip4`.

## Device fields

| Seed / RESTCONF | NetBox |
|-----------------|--------|
| hostname | `device.name` |
| site | `site` (name or slug) |
| role | `role` |
| node_definition / platform slug | `device_type` (`cat8000v`, not a product title) |
| `iosxe_get_platform_and_yang` `version` | snap `devices[].software_version` (not NetBox type) |
| vendor | `manufacturer` |
| serial | `serial` |

After GET, `bootstrap` / `reconcile` `netbox_bulk` create (and approved
update) interfaces, then IPs. `audit` does not bulk.

## Expand short interface names (cables)

CDP/LLDP often returns `Gi1/0/1`, `Gig 1/0/1`, `Te0/0/0`. NetBox names are long (`GigabitEthernet1/0/1`). Expand before lookup:

| Short | Long |
|-------|------|
| `Gi` / `Gig` | `GigabitEthernet` |
| `Te` / `TenGig` | `TenGigabitEthernet` |
| `Fo` | `FortyGigabitEthernet` |
| `Hu` | `HundredGigE` |
| `Po` | `Port-channel` |
| `Lo` | `Loopback` |
| `Vl` | `Vlan` |

Strip spaces (`Gig 1/0/1` → `GigabitEthernet1/0/1`). If NetBox find by expanded name misses, try the raw CDP string once.

## Cables (second pass)

After devices have interfaces in NetBox, GET CDP on each restconf seed
box (when GET is required). Walk inventory order, then neighbor order.
One pass. Resolve interface ids from `inventory/infra-sot.json` first.

| CDP field | Use |
|-----------|-----|
| this box | local device |
| `local-intf-name` (expand) | local interface id |
| `device-name` (before first `.`, match seed) | far device |
| `port-id` (expand) | far interface id |

Skip: not in seed, Loopback/Vlan/mgmt, missing ids, interface id already
used, same unordered id pair already used. Keep the rest. Asymmetric CDP
is still a cable. Do not score bidirectional. Do not invent devices.

Then write only in `bootstrap` / `reconcile`. One cable → `netbox_manage`.
Many → one `netbox_bulk`. The MCP unwraps `{ "item": … }` / JSON strings.
Do not invent XML wrappers. `audit` does not write cables.

```
netbox_manage action=create object_type=cable
data={
  "a_terminations": [{"object_type": "dcim.interface", "object_id": 37}],
  "b_terminations": [{"object_type": "dcim.interface", "object_id": 201}],
  "status": "connected"
}
```

## Failure handling

- RESTCONF fail on one box: still create the device from inventory; no invented
  interfaces; report host + error at the end.
- GET ok but you did not bulk the mapped interfaces: you skipped the mapping.
  Do not retry YANG formats. Do not dump GET JSON into NetBox.
- Cable resolve fail: leave the link off; do not invent the far-end device.
- HTTP 400: NetBox's error is the field-shape truth. Fix that field.
