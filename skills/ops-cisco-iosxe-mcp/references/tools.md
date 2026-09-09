# Cisco IOS-XE tools

Slice of `mcp-tool-capability-lookup.yaml` (2026-08-23). Studio uses live MCP for schemas.
Prefix: `iosxe_`. Lookup id: `cisco-iosxe`.

Use when:
- Read or change live Cisco IOS-XE configuration / operational state
- Discover platform + YANG models before building RESTCONF payloads
- Enable RESTCONF or run show/config CLI when RESTCONF is unavailable
- Persist running-config to NVRAM after changes

Do not use for:
- Inventory source of truth (netbox-mcp)
- Path performance from the internet (thousandeyes)

Typical flows:
- Discover: iosxe_get_platform_and_yang(list_modules=True or yang_model='Cisco-IOS-XE-native')
- Read: iosxe_restconf_get(path='Cisco-IOS-XE-native:native/interface')
- Change: iosxe_restconf_patch (preferred) or put/delete → iosxe_save_config
- CLI: iosxe_ssh_command(commands=[...], config_mode=True|False)

| Tool | Access | Required | Purpose |
|------|--------|----------|---------|
| `iosxe_restconf_get` | read | path | Read any RESTCONF resource from a Cisco IOS-XE device by YANG path. |
| `iosxe_restconf_put` | write | path, payload | Replace a RESTCONF resource on a Cisco IOS-XE device by YANG path. |
| `iosxe_restconf_patch` | write | path, payload | Merge/update a RESTCONF resource on a Cisco IOS-XE device by YANG path. |
| `iosxe_restconf_delete` | write | path | Delete a RESTCONF resource on a Cisco IOS-XE device by YANG path. |
| `iosxe_get_platform_and_yang` | read | — | Discover IOS-XE device platform information and fetch YANG model definitions. |
| `iosxe_ssh_command` | mixed | commands | Execute CLI commands on a Cisco IOS-XE device via SSH. |
| `iosxe_save_config` | write | — | Save the running configuration to NVRAM on a Cisco IOS-XE device. |

