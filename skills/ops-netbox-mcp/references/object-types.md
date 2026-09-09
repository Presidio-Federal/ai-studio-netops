# NetBox find / manage / bulk fields

The MCP sends `data` to NetBox unchanged. Map vendor names in
[sot-from-iosxe.md](sot-from-iosxe.md).

## netbox_find filters

| Filter | Typical types |
|--------|----------------|
| `tenant` | device, site, prefix, vlan, vrf, ip_address, circuit, vm |
| `name` | site, device, interface, tenant (contains) |
| `site` | device, prefix, vlan, vm (slug, name, or id) |
| `role` | device |
| `device` / `device_id` | interface, cable |
| `device_type`, `manufacturer`, `serial`, `asset_tag` | device |
| `status`, `tag`, `search` | most types |
| `occupied`, `enabled` | interface |
| `address` | ip_address |
| `prefix` | prefix |
| `vid` | vlan |
| `region` | site |
| `limit` / `offset` | all (max 100) |

Interface find **requires** `device` or `device_id`. Do not list all
interfaces in the instance. Prefer ids in `inventory/infra-sot.json`.

`netbox_get`: prefer `object_id`. Interface also needs `name` + `device`.
IP: `address`.

## Create required fields (`data`)

| object_type | Required |
|-------------|----------|
| `site` | `name`, `slug` |
| `device` | `name`, `device_type`, `role`, `site` |
| `interface` | `device`, `name`, `type` (NetBox slug) |
| `cable` | `a_terminations`, `b_terminations` — arrays of `{object_type, object_id}` |
| `ip_address` | `address` |
| `prefix` | `prefix` |
| `vlan` | `vid` (send `name` when creating) |
| `vrf` | `name` |
| `circuit` | `cid`, `provider`, `type` |
| `virtual_machine` | `name`, `site` |
| `device_type` | `manufacturer`, `model` (also send `slug` = node_definition) |
| `device_role` / `manufacturer` / `tenant` / `tag` | `name`, `slug` |

Also send `tenant` on devices, IPs, and the site when this lab owns them.

Related fields: id, slug, or name. Tags: JSON array of `{ "slug": "…" }`.
String lists 400 on this NetBox 4.6 Cloud instance.

Cable — one: `netbox_manage`. Many: `netbox_bulk`. The MCP unwraps
`{ "item": … }` / JSON strings to NetBox arrays.

```
netbox_manage action=create object_type=cable
data={
  "status": "connected",
  "a_terminations": [{ "object_type": "dcim.interface", "object_id": 8334 }],
  "b_terminations": [{ "object_type": "dcim.interface", "object_id": 8345 }]
}
```

## Which write tool

| Case | Tool |
|------|------|
| One tenant / site / type / role / tag, or **one cable** | `netbox_manage` |
| Many devices, interfaces, IPs, or cables | `netbox_bulk` (`create` or `update`) |
| Delete | `netbox_delete` with `confirm=true` only after the user intends it |

Do not invent XML wrappers. Call once. `{ "item": … }` and JSON strings
are unwrapped by the MCP.

`netbox_bulk` `data` is a list of those bodies. Update rows must include
`id`. `object_id` is a number. If `missing: a_terminations` after a
restart of this skill, the running netbox-mcp is still pass-through —
stop and restart the server.
