# Cisco IOS-XE MCP Examples

All examples use RESTCONF. SSH is only shown for the two permitted operations: enabling RESTCONF and saving configuration.

## Device Discovery (first step with any device)

```
1. iosxe_get_platform_and_yang()
   → Returns hardware model, serial, software version, YANG GitHub folder URL

2. iosxe_get_platform_and_yang(list_modules=True)
   → Returns all supported YANG modules on the device (can be hundreds)

3. iosxe_get_platform_and_yang(yang_model="Cisco-IOS-XE-native")
   → Fetches the full Cisco-IOS-XE-native.yang model definition from GitHub
```

## Bootstrap: Enable RESTCONF via SSH

If `iosxe_get_platform_and_yang()` fails because the RESTCONF API is not enabled:

1. Ask the user: *"RESTCONF is not responding. Should I SSH in and enable it? What SSH port? (default: 22)"*
2. After user confirms:

```
iosxe_ssh_command(
    commands=["ip http server", "ip http secure-server", "restconf"],
    config_mode=True,
    port=22
)
```

3. Wait a few seconds for the RESTCONF process to start, then retry `iosxe_get_platform_and_yang()`.

## Read Interface Configuration

```
# All interfaces
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface")

# All GigabitEthernet interfaces
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/GigabitEthernet")

# Specific Loopback
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/Loopback=0")

# Specific GigE (URL-encode slashes)
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=1%2F0%2F1")

# IETF interfaces model (operational + config state)
iosxe_restconf_get(path="ietf-interfaces:interfaces")
```

## Create a Loopback Interface

```
iosxe_restconf_put(
    path="Cisco-IOS-XE-native:native/interface/Loopback=99",
    payload={
        "Cisco-IOS-XE-native:Loopback": {
            "name": 99,
            "description": "Management Loopback",
            "ip": {
                "address": {
                    "primary": {
                        "address": "10.255.255.1",
                        "mask": "255.255.255.255"
                    }
                }
            }
        }
    }
)
```

## Update Interface Description (PATCH — incremental)

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface/Loopback=99",
    payload={
        "Cisco-IOS-XE-native:Loopback": {
            "name": 99,
            "description": "Updated Management Loopback"
        }
    }
)
```

## Delete a Loopback Interface

```
iosxe_restconf_delete(path="Cisco-IOS-XE-native:native/interface/Loopback=99")
```

## Read Routing Configuration

```
# All routing config
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router")

# Static routes
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/ip/route")

# OSPF config
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/router-ospf")

# BGP config
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp")
```

## Add a Static Route

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/ip/route",
    payload={
        "Cisco-IOS-XE-native:route": {
            "ip-route-interface-forwarding-list": [
                {
                    "prefix": "192.168.100.0",
                    "mask": "255.255.255.0",
                    "fwd-list": [
                        {"fwd": "10.0.0.1"}
                    ]
                }
            ]
        }
    }
)
```

## Read and Change Hostname

```
# Read
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/hostname")

# Change hostname (PUT — replacing a single value is a replace operation)
iosxe_restconf_put(
    path="Cisco-IOS-XE-native:native/hostname",
    payload={
        "Cisco-IOS-XE-native:hostname": "ROUTER-NYC-01"
    }
)
```

## ACL Configuration

```
# Read ACLs
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/ip/access-list")

# Read extended ACLs
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/ip/access-list/extended")
```

## NTP Configuration

```
# Read NTP
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/ntp")

# Configure NTP server
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/ntp",
    payload={
        "Cisco-IOS-XE-native:ntp": {
            "server": {
                "server-list": [
                    {"ip-address": "10.0.0.10"}
                ]
            }
        }
    }
)
```

## Logging / Syslog Configuration

```
# Read logging config (always read first)
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/logging")

# ADD a syslog host (PATCH — merges, preserves existing hosts)
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/logging",
    payload={
        "Cisco-IOS-XE-native:logging": {
            "host": {
                "ipv4-host-list": [
                    {"ipv4-host": "10.0.0.50"}
                ]
            }
        }
    }
)

# CHANGE/REPLACE syslog host (PUT — overwrites, old host is removed)
iosxe_restconf_put(
    path="Cisco-IOS-XE-native:native/logging",
    payload={
        "Cisco-IOS-XE-native:logging": {
            "host": {
                "ipv4-host-list": [
                    {"ipv4-host": "10.0.0.51"}
                ]
            }
        }
    }
)
```

## SNMP Configuration

```
# Read SNMP config
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/snmp-server")
```

## Using Query Parameters (filtered GET)

**Prefer reading the full container and inspecting the response** instead of using `params`. The `params` argument requires a native dict (not a JSON string) and some models may serialize it incorrectly. Only use `params` when the response is very large and you need to reduce it server-side.

```
# Only return specific fields
iosxe_restconf_get(
    path="Cisco-IOS-XE-native:native/interface",
    params={"fields": "GigabitEthernet/name;GigabitEthernet/description"}
)

# Limit depth
iosxe_restconf_get(
    path="Cisco-IOS-XE-native:native",
    params={"depth": "2"}
)

# Config-only data (exclude operational state)
iosxe_restconf_get(
    path="ietf-interfaces:interfaces",
    params={"content": "config"}
)
```

## Save Configuration

After making RESTCONF changes, save the running config to NVRAM:

```
iosxe_save_config()
```

This calls `POST /restconf/operations/cisco-ia:save-config` — the RESTCONF equivalent of `write memory`. Do NOT use SSH for this.

## End-to-End: Audit and Update a Device

```
1. iosxe_get_platform_and_yang()
   → Discover device model, version, map to YANG folder

2. iosxe_restconf_get(path="Cisco-IOS-XE-native:native/hostname")
   → Get current hostname

3. iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface")
   → Inventory all interfaces

4. iosxe_restconf_get(path="Cisco-IOS-XE-native:native/ntp")
   → Check NTP config

5. iosxe_restconf_patch(path="Cisco-IOS-XE-native:native/ntp", payload={...})
   → Fix NTP if needed

6. iosxe_restconf_get(path="Cisco-IOS-XE-native:native/logging")
   → Check syslog config

7. iosxe_restconf_patch(path="Cisco-IOS-XE-native:native/logging", payload={...})
   → Add syslog host if missing

8. iosxe_save_config()
   → Save configuration to NVRAM
```

## Connecting to a Non-Default Device

All RESTCONF tools accept optional connection overrides:

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-native:native/hostname",
    host="192.0.2.2",
    port=443
)
```

Host, port, and credentials stay on the MCP server (or env). Do not
put passwords in this skill or in workspace files.

## YANG Model Lookup Before Configuration

When unsure of the exact payload structure, fetch the YANG model first:

```
1. iosxe_get_platform_and_yang(yang_model="Cisco-IOS-XE-mdt-cfg")
   → Returns the full .yang file content for model-driven telemetry config

2. Read the YANG model to understand the container/leaf structure

3. Build your RESTCONF payload matching the model
```
