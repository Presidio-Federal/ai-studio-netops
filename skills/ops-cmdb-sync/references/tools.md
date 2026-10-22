# Tools

`scripts/sync_cmdb.py` calls these under `mcp_orchestration`. Do not call them yourself unless stderr says `hai_mcp unavailable`. Names from `docs/mcp-index.md`. Do not invent tools. Do not pass usernames or passwords. Host and port come from `inventory/prod.json`.

Every NetBox call is for one device in the lab tenant. Every ServiceNow call is one exact name, `limit` 5. Neither call lists another inventory.

## IOS-XE

| Tool | Arguments | Use |
|------|-----------|-----|
| `iosxe_restconf_get` | `path`, `host`, `port` | `Cisco-IOS-XE-native:native/hostname`, then `Cisco-IOS-XE-native:native/interface` |
| `iosxe_get_platform_and_yang` | `host`, `port`, `list_modules=true` | Only after the interface path 404s |

Forbidden: `iosxe_restconf_put`, `iosxe_restconf_patch`, `iosxe_restconf_delete`, `iosxe_save_config`, `iosxe_ssh_command`.

## NetBox

| Tool | Arguments | Use |
|------|-----------|-----|
| `netbox_get` | `object_type=device`, `object_id` | Snap id, or the id you just updated |
| `netbox_get` | `object_type=ip_address`, `object_id` | Read-back after an address update |
| `netbox_find` | `object_type=device`, `name`, `tenant` | Only when the snap has no id for this name |
| `netbox_manage` | `action=update`, `object_type=ip_address`, `data` | `data` is `{ "id", "address" }` for the existing primary |
| `netbox_manage` | `action=update`, `object_type=device`, `data` | `data` is `{ "id", "primary_ip4" }` only when the pointer is a different IP id |

Forbidden: `netbox_bulk`, `netbox_delete`, `netbox_test_connection`. There is no `netbox_sync_device`.

## ServiceNow

| Tool | Arguments | Use |
|------|-----------|-----|
| `snow_get_asset` | `serial_number` = the device name | One lab asset |
| `snow_upsert_asset` | `serial_number`, `asset_tag`, `display_name`, `install_status=in_use`, `company=Cisco AI Lab`, `comments` | Create or update that asset. `comments` is `<tenant> <address>` |

Do not call `snow_find_assets` with an empty serial. Do not call `snow_query_table`.
