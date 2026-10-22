# Fields

The script in `scripts/sync_cmdb.py` implements this contract. On the manual fallback, follow it yourself. Do not widen it.

## Scope

Lab tenant is `inventory/prod.json` `netbox.tenant`, otherwise `source.name`. The task-line name must be a `devices[]` name in that file. Anything else → `result` `failed`, gap `outside lab inventory`, no MCP.

NetBox `netbox_find` always sends `tenant` and `limit` 5. Accept the row only when `tenant.slug` or `tenant.name` equals that tenant and the tags include `{tenant}-simulate`. A device with no tenant, or with only `origin` `prod-twin`, is the other inventory. Do not update it. Do not list devices.

ServiceNow is the one query below. `limit` 5. Drop rows whose `name` is not the task line. Do not query `alm_hardware`, do not search serials, and do not filter by company. The lab network devices are not a ServiceNow company. Another inventory's company is not this lab.

RESTCONF host and port are that same `devices[]` row, `access.restconf.host` and `access.restconf.port`. The value must be an object with both. Null or missing → `result` `failed`, gap `no restconf`. Do not guess a port. Do not call MCP.

## Hostname

```text
iosxe_restconf_get
  path: Cisco-IOS-XE-native:native/hostname
  host / port: from that device
```

The hostname string in the body must equal the task-line name. No string, or a different string → `result` `failed`, gap `hostname mismatch`, `device.name` stays the task-line name, `device_values.hostname` is what you found or `null`. `keys` `[]`. Do not read NetBox or ServiceNow. Do not rename.

## Primary IPv4

```text
iosxe_restconf_get
  path: Cisco-IOS-XE-native:native/interface
  host / port: from that device
```

If that path 404s, one `iosxe_get_platform_and_yang` with `list_modules=true` and the same host and port. Pick the interface oper module that path names, GET it once, then stop. Do not SSH. A second failure → `device_values.primary_ipv4` `null`, gap `no address on device`, and do not write an address.

Pick one address. Stop at the first hit:

1. `Loopback0` with a static IPv4 (`ip.address.primary` address).
2. Else the first static IPv4 in native GET order.

`ip address dhcp`, an empty Loopback, and a shutdown-only interface are not candidates. Do not invent a lease. Record `device_values.interface` as the NetBox-style name (`Loopback0`, `GigabitEthernet1`). Record `device_values.primary_ipv4` as the host only, no prefix.

No candidate → gap `no address on device`. Leave both CMDB addresses alone.

## NetBox

Id: `inventory/infra-sot.json` `devices[].id` for this name, then `netbox_get` `object_type=device` `object_id` that id.

No id: one `netbox_find` `object_type=device` `name=<task line>` `tenant=<lab tenant>` `limit=5`. Keep a row only when the tenant matches and the tags include `{tenant}-simulate`. Zero such rows → `result` `failed`, gap `no netbox device`, stop. Do not create one. More than one → `result` `failed`, gap `netbox name not unique`, stop. More than five rows back → `failed`, gap `unscoped netbox result`, stop. Do not page.

Compare address hosts. Strip anything after `/` on NetBox `primary_ip4.address`. ServiceNow `ip_address` is already a host.

| Device host | NetBox primary | Action |
|-------------|----------------|--------|
| null | anything | gap `no address on device`. No address write. |
| equals NetBox host | set | `compared` verdict `match`. No `netbox_manage`. |
| differs | `primary_ip4.id` present | One `netbox_manage` `action=update` `object_type=ip_address`. `data.id` is that id. `data.address` is `<device host>/<prefix length already on that object>`. Keep the existing prefix length. Do not create an interface or a new IP. Then `netbox_get` that IP. Verdict `updated`. `wrote` `netbox`. |
| differs | no `primary_ip4.id` | `netbox_find` the interface by device id and name. It already exists → use that id. Missing → one `netbox_manage` create. Then create the IP on that interface and set `primary_ip4`. A 400 "already exists" means the find was skipped. Do not create the interface again. |

When the IP object you just confirmed is not the device `primary_ip4`, one more `netbox_manage` `action=update` `object_type=device` with `data.id` the device id and `data.primary_ip4` that IP id. Then `netbox_get` the device. If it was already the pointer, do not call it.

## ServiceNow

One call. `<name>` is the task-line name. Do not drop the class filter.

```text
snow_query_table(
  table="cmdb_ci",
  query="name=<name>^comments=<lab tenant>^sys_class_nameINcmdb_ci_netgear,cmdb_ci_ip_router,cmdb_ci_ip_switch,cmdb_ci_ip_firewall",
  fields="name,sys_id,sys_class_name,serial_number,asset_tag,ip_address,install_status,operational_status",
  limit=5)
```

Accept class `cmdb_ci_netgear`, `cmdb_ci_ip_router`, `cmdb_ci_ip_switch`, `cmdb_ci_ip_firewall`, or the display labels Network Gear, IP Router, IP Switch, IP Firewall. Any other class is not a row. The lab comment is also on application CIs; the class list leaves those out. Company `Cisco AI Lab` is the network set. Do not query that company without the name.

| Rows | Action |
|------|--------|
| 0 | gap `no servicenow ci`. Still apply the NetBox address rule. |
| 1 | Compare `ip_address` host to the device host. Equal → verdict `match`. Differ, including a device address against an empty CI address → verdict `gap`. Do not write ServiceNow. Do not copy the CI address onto NetBox. |
| more than 1 | `result` `failed`, gap `servicenow name not unique`, `wrote` `none`. No `netbox_manage`. |

## Reported, never written

One `compared` row each, verdict `reported`, when the NetBox read and the ServiceNow read both happened. `device` is `null`. Copy the strings you were given. Empty is `""`.

- `serial` — NetBox `serial`, ServiceNow `serial_number`
- `asset_tag` — both `asset_tag`
- `status` — NetBox `status`, ServiceNow `install_status` and `operational_status` joined as `<install>/<operational>`
- `model` — NetBox `device_type` slug. ServiceNow `""`. Do not read `model_id`.
- `site` — NetBox site name. ServiceNow `""`. Do not read `location`.

Do not map status words. Do not copy model or site.

## Result word

Set `result`, then envelope `status`:

| `result` | `status` | When |
|----------|----------|------|
| `in_sync` | `ok` | Hostname confirmed, address hosts match, no gaps |
| `updated` | `ok` | NetBox address was updated and there is no gap |
| `gaps` | `gaps` | Any gap, including a ServiceNow miss after a NetBox update |
| `failed` | `failed` | Stopped before an address write |

`wrote` is `netbox` only when `netbox_manage` ran. Otherwise `none`.

`keys`: `device:<task-line name>` when the hostname matched, plus `interface:<task-line name>/<interface>` when `device_values.interface` is set. Otherwise `[]`. No other prefixes. `relations` is `[]`. This visit does not observe a cable, a peer, or a ticket.

`next_action` is `null` when `result` is `in_sync` or `updated`. On `gaps` or `failed`, one sentence naming the gap. Never the string `none`.

`headline` is one line: result word, device name, and the address verdict.
