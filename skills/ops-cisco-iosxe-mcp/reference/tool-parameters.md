# Cisco IOS-XE MCP — Tool Parameters

## iosxe_restconf_get

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `path` | str | **required** | YANG-qualified RESTCONF path |
| `host` | str | None | Override connection host |
| `port` | int | None | Override connection port |
| `username` | str | None | Override username |
| `password` | str | None | Override password |
| `params` | dict | None | Query parameters: `fields`, `depth`, `content`. **Avoid using this parameter** — most use cases are better served by reading the full container path and inspecting the response. If you must use it, pass a native dict object (e.g. `{"depth": "2"}`), NOT a JSON string. All values must be strings. |

## iosxe_restconf_put

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `path` | str | **required** | YANG-qualified RESTCONF path |
| `payload` | dict | **required** | Full replacement JSON matching YANG model structure |
| `host` | str | None | Override connection host |
| `port` | int | None | Override connection port |
| `username` | str | None | Override username |
| `password` | str | None | Override password |

Payloads are automatically wrapped with the module-qualified root key derived from the path if not already wrapped.

**Use PUT when the user wants to change, replace, or switch an existing value.** PUT overwrites the entire target resource — the old config at that path is gone and only the new payload remains.

## iosxe_restconf_patch

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `path` | str | **required** | YANG-qualified RESTCONF path |
| `payload` | dict | **required** | Partial JSON — fields you provide are merged into existing config |
| `host` | str | None | Override connection host |
| `port` | int | None | Override connection port |
| `username` | str | None | Override username |
| `password` | str | None | Override password |

**Use PATCH when the user wants to add to or augment existing config.** PATCH merges — existing entries at the path are preserved and the new fields/entries are added alongside them. Do NOT use PATCH when the intent is to change or replace an existing value, because the old value will remain.

## iosxe_restconf_delete

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `path` | str | **required** | YANG-qualified RESTCONF path to the resource to remove |
| `host` | str | None | Override connection host |
| `port` | int | None | Override connection port |
| `username` | str | None | Override username |
| `password` | str | None | Override password |

Use with caution — permanently removes the resource from the device config.

## iosxe_get_platform_and_yang

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `host` | str | None | Override connection host |
| `port` | int | None | Override connection port |
| `username` | str | None | Override username |
| `password` | str | None | Override password |
| `yang_model` | str | None | Fetch a specific YANG model file (e.g. `Cisco-IOS-XE-native`, `Cisco-IOS-XE-mdt-cfg`) |
| `list_modules` | bool | False | List all supported YANG modules on the device |

Returns: `platform_info`, `version`, `yang_version_folder`, `yang_github_url`, and optionally `yang_model_content` or `modules`.

## iosxe_ssh_command

> **Restricted use.** This tool has ONE permitted use: enabling the RESTCONF API when it is not running on the device. NEVER use it for show commands, config reads, verification, troubleshooting, saving configuration, or any other purpose.

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `commands` | list[str] | **required** | One or more CLI commands |
| `host` | str | None | Override connection host |
| `port` | int | None | **Ask the user.** Default 22. Do not assume — confirm with the user first. |
| `username` | str | None | Override username |
| `password` | str | None | Override password |
| `enable_password` | str | None | Separate enable secret if required |
| `config_mode` | bool | False | `True` = configure terminal mode; `False` = privileged exec mode |

### The ONLY permitted SSH operation

**Enable RESTCONF** (config mode) — only after asking the user to confirm and for the SSH port:
```
iosxe_ssh_command(
    commands=["ip http server", "ip http secure-server", "restconf"],
    config_mode=True,
    port=<user-specified or 22>
)
```

## iosxe_save_config

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `host` | str | None | Override connection host |
| `port` | int | None | Override connection port |
| `username` | str | None | Override username |
| `password` | str | None | Override password |

Saves the running configuration to NVRAM. Equivalent to `write memory` / `copy running-config startup-config`. POSTs to `/restconf/operations/cisco-ia:save-config`. No payload required.

Call this after every configuration change:
```
iosxe_save_config()
```
