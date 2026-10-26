---
name: ops-cmdb-sync
version: "1.2.2"
description: "v1.2.2 — Sync one lab device to live IOS-XE, reusing a NetBox address that already exists and updating the ServiceNow hardware asset."
---

# Ops CMDB Sync

One device per invoke. The webhook names the device. `signal netbox` or `signal servicenow` is a label on `state/cmdb-sync.json`. It does not choose a winner and it does not change the procedure.

The box is the authority for hostname and primary IPv4. Both CMDB records are targets. A field the box does not own is reported and not copied. Copying it from whichever system fired is what loops.

Write **`state/cmdb-sync.json` only**, then `read_file` it back. Paths: **`workspace-handoff`**. Schema and example are in this skill.

## Hard no

Do not write the box. Do not call `iosxe_restconf_put`, `iosxe_restconf_patch`, `iosxe_restconf_delete`, `iosxe_save_config`, or `iosxe_ssh_command`.

Do not create cables, device types, or tags beyond `{tenant}-simulate` on the one device this invoke is creating. Do not call `netbox_bulk` or `netbox_delete`. Do not change `device_type` on a device that already exists.

Do not write ServiceNow except `snow_get_asset` and `snow_upsert_asset` for this one lab device. The asset serial and asset tag are the device name. `comments` is `<lab tenant> <address>`. Do not call `snow_find_assets` without that serial. Do not call `snow_query_table`, `snow_find_cis`, or `snow_get_ci`.

Do not write `inventory/prod.json`, `inventory/infra-sot.json`, or `state/netbox.json`. Do not bootstrap NetBox. Do not rename either record. The task-line name is the join key.

Scope is the lab on `inventory/prod.json`: `netbox.tenant`, otherwise `source.name`. The device must be a `devices[]` row in that file. NetBox calls send that tenant. A missing NetBox device is created from that inventory row and the live address. ServiceNow is one hardware asset, serial and asset tag equal to the device name, company Cisco AI Lab. Do not list assets. A name that is not in the lab inventory is not looked up.

Call `execute_command` only to run `scripts/sync_cmdb.py`. Do not write scripts. Do not call MCP yourself unless stderr says `hai_mcp unavailable`. Do not `get_folder_structure`. Do not list `automations/schedules`.

## Tools

| Tool | Use |
|------|-----|
| `iosxe_restconf_get` | Hostname, then interfaces. Host and port from `inventory/prod.json`. |
| `iosxe_get_platform_and_yang` | Only after the interface path 404s, `list_modules=true`, then one retry. No `yang_model`. |
| `netbox_get` | Device by id from `inventory/infra-sot.json` when that name is there. |
| `netbox_find` | Device by name + tenant only when the snap has no id. |
| `netbox_manage` | `action=update` on the existing IP object, or on the device `primary_ip4` pointer. One or two calls. Only when the address host differs. |
| `snow_get_asset` | One asset by `serial_number` = the device name. |
| `snow_upsert_asset` | Create or update that asset. Serial, asset tag, and display name are the device name. `comments` is the lab tenant and the address. `install_status` is `in_use`. `company` is `Cisco AI Lab`. |

Details: [references/tools.md](references/tools.md).

## Procedure

The script owns the compare and the NetBox write. [references/watch.md](references/watch.md) is the command. [references/fields.md](references/fields.md) is the contract the script implements. [references/signal.md](references/signal.md) is the task line.

**First tool:** `read_file` `inventory/prod.json`, only to confirm the workspace is there. Then one `execute_command`, `execution_type: "mcp_orchestration"`. Use the path Studio shows for `ops-cmdb-sync/scripts/sync_cmdb.py`. Copy it. Pass `--device` as the one token in `Sync <device-name>.` and `--signal` from the label, or `unknown`.

The last stdout line is the result. Do not open `state/cmdb-sync.json` to fill the reply. The script writes that file.

If stderr says `hai_mcp unavailable`, follow the manual order in `references/watch.md`. Any other failure: one line from stderr, then stop. Do not collect by hand.

## Files

| Path | Kind |
|------|------|
| `state/cmdb-sync.json` | state — this invoke only. Replace in full. |

Schema: `schemas/cmdb-sync-state.schema.json`. Example: `examples/cmdb-sync-state.example.json`.
