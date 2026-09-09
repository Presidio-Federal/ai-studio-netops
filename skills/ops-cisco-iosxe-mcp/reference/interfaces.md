# Cisco IOS-XE Interface Management

Full CRUD operations for IOS-XE interfaces via RESTCONF. All operations use the existing `iosxe_restconf_get`, `iosxe_restconf_patch`, `iosxe_restconf_put`, and `iosxe_restconf_delete` tools.

## CML PAT / C8000V — WRITE RECIPE (use this first)

On CML-backed cat8000v (PAT to controller), **interface writes must use the parent path**. Do not invent alternate shapes or fetch YANG models when a write fails — use this recipe.

### Configure IP + description on GigabitEthernet N (canonical)

```
# 1) PATCH parent interface container — NEVER path GigabitEthernet=<N> for PATCH body
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "6",
                    "description": "Link to AI-BRANCH-03",
                    "ip": {
                        "address": {
                            "primary": {
                                "address": "100.64.7.1",
                                "mask": "255.255.255.252"
                            }
                        }
                    }
                }
            ]
        }
    }
)

# 2) no shutdown = DELETE the shutdown leaf (do not PATCH "no shutdown")
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=6/shutdown"
)
```

### Forbidden / known failures on this lab

| Do not | Why |
|--------|-----|
| PATCH `.../interface/GigabitEthernet=6` with payload key `Cisco-IOS-XE-native:GigabitEthernet` | Device returns `unknown-element: GigabitEthernet=6` |
| Include `cdp` / `Cisco-IOS-XE-cdp:cdp` / `enable: [null]` in the interface PATCH | Device returns malformed-message on `cdp/enable` — omit CDP; global `cdp run` is enough |
| Include `negotiation` / ethernet namespace extras unless you already know they work | Unnecessary; keep payload to `name` + `description` + `ip` |
| Call `iosxe_get_platform_and_yang` to "figure out" interface writes | Wasteful — use the parent-path recipe above |
| PUT the whole interface list | Risk of wiping other interfaces |

### GET vs WRITE paths

| Op | Path |
|----|------|
| GET one iface | `Cisco-IOS-XE-native:native/interface/GigabitEthernet=6` — OK |
| PATCH iface config | **Always** `Cisco-IOS-XE-native:native/interface` with `GigabitEthernet: [ { "name": "6", ... } ]` |
| DELETE shutdown | `.../GigabitEthernet=6/shutdown` — OK |

## Interface Types and Path Naming

Interfaces are accessed under `Cisco-IOS-XE-native:native/interface`. Each interface type is a separate YANG list keyed by its number.

| Interface type | YANG list name | Path example | `name` value |
|----------------|---------------|--------------|--------------|
| GigabitEthernet | `GigabitEthernet` | `interface/GigabitEthernet=5` | `"5"` |
| GigabitEthernet (slotted) | `GigabitEthernet` | `interface/GigabitEthernet=1%2F0%2F1` | `"1/0/1"` |
| Loopback | `Loopback` | `interface/Loopback=0` | `0` (integer) |
| Vlan | `Vlan` | `interface/Vlan=100` | `100` (integer) |
| Port-channel | `Port-channel` | `interface/Port-channel=1` | `1` (integer) |
| TenGigabitEthernet | `TenGigabitEthernet` | `interface/TenGigabitEthernet=1%2F0%2F1` | `"1/0/1"` |
| TwentyFiveGigE | `TwentyFiveGigE` | `interface/TwentyFiveGigE=1%2F0%2F1` | `"1/0/1"` |
| FortyGigabitEthernet | `FortyGigabitEthernet` | `interface/FortyGigabitEthernet=1%2F0%2F1` | `"1/0/1"` |
| HundredGigE | `HundredGigE` | `interface/HundredGigE=1%2F0%2F1` | `"1/0/1"` |

**URL-encode slashes:** Any `/` in the interface number must be encoded as `%2F` in the RESTCONF path. In payloads, use the raw number (e.g., `"1/0/1"`).

**Name type matters:** GigabitEthernet and other physical interfaces use a **string** name (`"5"`, `"1/0/1"`). Loopback and Vlan use an **integer** name (`0`, `100`).

## Read Interfaces

```
# All interfaces on the device
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface")

# All GigabitEthernet interfaces
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/GigabitEthernet")

# A specific GigabitEthernet
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=5")

# A slotted interface (encode the slashes)
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=1%2F0%2F1")

# A specific Loopback
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/Loopback=0")

# A specific Vlan interface
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/Vlan=100")

# IETF interfaces model (config + operational state — includes admin-status, oper-status, counters)
iosxe_restconf_get(path="ietf-interfaces:interfaces")
```

## Shutdown / No Shutdown

The `shutdown` leaf controls the administrative state of an interface.

- **Shutdown** = `"shutdown": [null]` — the interface is admin-down.
- **No shutdown** = the `shutdown` leaf is absent — the interface is admin-up.

### Shut down an interface

Use PATCH on the parent interface container. The `shutdown` key with a `[null]` value sets the interface to admin-down.

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "shutdown": [null]
                }
            ]
        }
    }
)
```

For a slotted interface:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "1/0/1",
                    "shutdown": [null]
                }
            ]
        }
    }
)
```

For a Loopback:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "Loopback": [
                {
                    "name": 0,
                    "shutdown": [null]
                }
            ]
        }
    }
)
```

### Bring up an interface (no shutdown)

To remove the shutdown state, DELETE the `shutdown` leaf from the specific interface. This is the equivalent of `no shutdown`.

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=5/shutdown"
)
```

For a slotted interface:

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=1%2F0%2F1/shutdown"
)
```

For a Loopback:

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/interface/Loopback=0/shutdown"
)
```

### Shut down multiple interfaces at once

PATCH the parent container with multiple entries in the list:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "3",
                    "shutdown": [null]
                },
                {
                    "name": "4",
                    "shutdown": [null]
                },
                {
                    "name": "5",
                    "shutdown": [null]
                }
            ]
        }
    }
)
```

### Bounce an interface (shut then no-shut)

When the user asks to "bounce" or "reset" an interface, perform two operations in sequence:

```
# Step 1: Shut it down
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "shutdown": [null]
                }
            ]
        }
    }
)

# Step 2: Bring it back up
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=5/shutdown"
)
```

## IP Address Configuration

### Set a primary IP address on a physical interface

Use PATCH to add/update the IP address without disturbing other interface settings:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "ip": {
                        "address": {
                            "primary": {
                                "address": "10.0.0.1",
                                "mask": "255.255.255.252"
                            }
                        }
                    }
                }
            ]
        }
    }
)
```

### Set a secondary IP address

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "ip": {
                        "address": {
                            "secondary": [
                                {
                                    "address": "10.0.1.1",
                                    "mask": "255.255.255.0",
                                    "secondary": [null]
                                }
                            ]
                        }
                    }
                }
            ]
        }
    }
)
```

### Remove an IP address

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=5/ip/address"
)
```

## Interface Description

### Set or update a description

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "description": "Uplink to Core Switch"
                }
            ]
        }
    }
)
```

### Remove a description

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=5/description"
)
```

## VRF Assignment

### Assign an interface to a VRF

**Important:** Assigning a VRF to an interface removes any existing IP address configuration on that interface (this is standard IOS-XE behavior). Always re-apply the IP address after setting the VRF.

```
# Step 1: Assign the VRF
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "vrf": {
                        "forwarding": "MGMT"
                    }
                }
            ]
        }
    }
)

# Step 2: Re-apply the IP address
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "ip": {
                        "address": {
                            "primary": {
                                "address": "10.0.0.1",
                                "mask": "255.255.255.252"
                            }
                        }
                    }
                }
            ]
        }
    }
)
```

### Remove VRF from an interface

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=5/vrf"
)
```

## Create a Loopback Interface

Use PUT to create or fully replace a Loopback. PUT is correct here because you are defining the entire interface from scratch.

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

## Create a Vlan Interface (SVI)

```
iosxe_restconf_put(
    path="Cisco-IOS-XE-native:native/interface/Vlan=100",
    payload={
        "Cisco-IOS-XE-native:Vlan": {
            "name": 100,
            "description": "User VLAN 100",
            "ip": {
                "address": {
                    "primary": {
                        "address": "192.168.100.1",
                        "mask": "255.255.255.0"
                    }
                }
            }
        }
    }
)
```

## Delete a Loopback or Vlan Interface

```
iosxe_restconf_delete(path="Cisco-IOS-XE-native:native/interface/Loopback=99")

iosxe_restconf_delete(path="Cisco-IOS-XE-native:native/interface/Vlan=100")
```

**Do NOT delete physical interfaces** (GigabitEthernet, TenGigabitEthernet, etc.) — they cannot be removed. You can only modify their configuration or shut them down.

## Combined Operations

When the user asks to configure multiple things on an interface at once (IP + description + no shutdown), combine what you can into a single PATCH and follow with a DELETE for shutdown removal:

```
# Step 1: Set IP, description, and ensure interface is configured
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "description": "WAN Uplink to ISP-A",
                    "ip": {
                        "address": {
                            "primary": {
                                "address": "203.0.113.2",
                                "mask": "255.255.255.252"
                            }
                        }
                    }
                }
            ]
        }
    }
)

# Step 2: Ensure interface is admin-up (remove shutdown if present)
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=5/shutdown"
)
```

## MTU Configuration

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "mtu": 9000
                }
            ]
        }
    }
)
```

## Speed and Duplex (physical interfaces only)

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/interface",
    payload={
        "Cisco-IOS-XE-native:interface": {
            "GigabitEthernet": [
                {
                    "name": "5",
                    "speed": {
                        "value-1000": [null]
                    },
                    "Cisco-IOS-XE-ethernet:duplex": "full"
                }
            ]
        }
    }
)
```

## Verify Interface State

After any change, always verify using a GET:

```
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=5")
```

For operational state (admin-status, oper-status, counters):

```
iosxe_restconf_get(path="ietf-interfaces:interfaces/interface=GigabitEthernet5")
```

## Always Save After Changes

```
iosxe_save_config()
```

## Decision Guide

| User says | Action | Method |
|-----------|--------|--------|
| "shut down GigE5" / "disable the interface" | Add `shutdown` leaf | PATCH |
| "no shut" / "bring up" / "enable the interface" | Remove `shutdown` leaf | DELETE on `/shutdown` |
| "bounce the interface" / "reset it" | Shutdown then no-shutdown | PATCH then DELETE |
| "set IP to 10.0.0.1/30" | Set primary IP address | PATCH |
| "change the IP" / "replace the IP" | Set new primary IP address | PATCH (overwrites primary) |
| "remove the IP" | Delete IP address config | DELETE on `/ip/address` |
| "add a description" / "update description" | Set description | PATCH |
| "remove the description" | Delete description | DELETE on `/description` |
| "put it in VRF MGMT" | Assign VRF, then re-apply IP | PATCH (two steps) |
| "create Loopback99" | Create new loopback | PUT |
| "create Vlan100 SVI" | Create new SVI | PUT |
| "delete Loopback99" | Remove loopback entirely | DELETE |
| "configure GigE5 with IP and description" | Combined config | PATCH (single payload) |
