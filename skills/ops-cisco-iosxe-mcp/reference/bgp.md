# Cisco IOS-XE BGP Configuration

Full BGP configuration management via RESTCONF. All operations use the existing `iosxe_restconf_get`, `iosxe_restconf_patch`, `iosxe_restconf_put`, and `iosxe_restconf_delete` tools.

## CML PAT / C8000V — WRITE RECIPE (use this first)

On CML-backed cat8000v (PAT), **keyed write paths often fail** with `unknown-element: bgp=65000` / `neighbor=x.x.x.x` even though **GET** on those paths works. Do **not** spiral into YANG discovery. Use the **native parent PATCH** below.

### Step A — GET (keyed path OK)

```
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp")
```

Confirm AS (e.g. `65000`) and that the new neighbor IP is not already present.

### Step B — Add neighbor (process level) — PATCH `native`

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native",
    payload={
        "Cisco-IOS-XE-native:native": {
            "router": {
                "Cisco-IOS-XE-bgp:bgp": [
                    {
                        "id": 65000,
                        "neighbor": [
                            {
                                "id": "100.64.7.2",
                                "remote-as": 65100
                            }
                        ]
                    }
                ]
            }
        }
    }
)
```

### Step C — Activate in AF (+ next-hop-self + as-override for WAN→branch)

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native",
    payload={
        "Cisco-IOS-XE-native:native": {
            "router": {
                "Cisco-IOS-XE-bgp:bgp": [
                    {
                        "id": 65000,
                        "address-family": {
                            "no-vrf": {
                                "ipv4": [
                                    {
                                        "af-name": "unicast",
                                        "ipv4-unicast": {
                                            "neighbor": [
                                                {
                                                    "id": "100.64.7.2",
                                                    "activate": [null],
                                                    "next-hop-self": {},
                                                    "as-override": {}
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
        }
    }
)
```

Then `iosxe_save_config()` and GET to verify.

### Forbidden / known failures on this lab

| Do not | Why |
|--------|-----|
| PATCH/PUT `.../router/bgp=65000` with body keyed at that path | `unknown-element: bgp=65000` on write |
| PUT `.../neighbor=100.64.7.2` | Same unknown-element; also PUT is forbidden for BGP |
| PATCH `.../router/bgp` with bare `"Cisco-IOS-XE-bgp:bgp": [ ... ]` without wrapping under `native` | Often `Internal error` / malformed |
| Call `iosxe_get_platform_and_yang` after a write failure | Does not fix path shape — use native parent PATCH |
| PUT any BGP resource | Wipes peers |

**GET** may still use `bgp=65000` / `neighbor=<ip>`. **WRITE** for this lab = PATCH `Cisco-IOS-XE-native:native` only.

## !!!!! SAFETY: NEVER OVERWRITE EXISTING BGP CONFIG !!!!!

**BGP configuration is additive-only.** Follow these rules without exception:

1. **ALWAYS read the full BGP config before making any change.** Every single time. No exceptions.
2. **ONLY use PATCH for adding neighbors, networks, and address-family entries.** PATCH merges into existing config — existing neighbors, networks, and routes are preserved.
3. **NEVER use PUT on any BGP path.** PUT replaces the entire resource at that path. If you PUT a BGP config with one neighbor, every other neighbor is deleted. This is catastrophic in production.
4. **NEVER use DELETE on the BGP process or address-family container.** Only DELETE specific, targeted leaf resources (a single neighbor, a single network statement) and only when the user explicitly asks to remove that specific item.
5. **When in doubt, read the config again.** If you are unsure whether a PATCH will do what you expect, do a GET first and show the user the current state before proceeding.
6. **On CML C8000V / PAT devices, prefer the native-parent WRITE RECIPE above** over keyed `bgp=<AS>` PATCH examples later in this file.

**Why this matters:** A BGP misconfiguration can tear down every peering session on a router and cause a network-wide outage. There is no "undo" — the old config is gone the moment a PUT overwrites it or a DELETE removes it.

## YANG Structure

BGP configuration lives at:

```
Cisco-IOS-XE-native:native/router/bgp
```

The response data is keyed under `Cisco-IOS-XE-bgp:bgp`. Each BGP instance is a list entry keyed by AS number (`id`). A device typically has one BGP instance.

### Hierarchy

```
router/bgp (list, keyed by "id" = AS number)
  ├── id                          ← AS number (integer)
  ├── bgp                         ← BGP process-level settings
  │   ├── router-id               ← Router ID
  │   ├── log-neighbor-changes    ← Log neighbor state changes
  │   └── ...
  ├── neighbor (list, keyed by "id" = neighbor IP)
  │   ├── id                      ← Neighbor IP address
  │   ├── remote-as               ← Neighbor AS number
  │   ├── description             ← Neighbor description
  │   ├── update-source           ← Update source interface
  │   ├── ebgp-multihop           ← eBGP multihop settings
  │   ├── password                ← MD5 authentication
  │   └── shutdown                ← Admin shutdown of neighbor
  └── address-family
      ├── no-vrf
      │   └── ipv4 (list, keyed by "af-name")
      │       ├── af-name          ← "unicast", "multicast"
      │       ├── ipv4-unicast
      │       │   └── neighbor (list)
      │       │       ├── id
      │       │       ├── activate
      │       │       ├── route-map
      │       │       ├── prefix-list
      │       │       └── soft-reconfiguration
      │       └── network
      │           └── with-mask (list)
      │               ├── number   ← Network prefix
      │               └── mask     ← Network mask
      └── with-vrf
          └── ipv4 (list)
              ├── af-name
              ├── vrf (list, keyed by "name")
              └── ...
```

## Read BGP Configuration

**Always start here.** Read the full BGP config to understand what exists before any change.

```
# Full BGP config (all instances, all neighbors, all address-families)
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp")

# A specific BGP instance by AS number
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp=65000")

# Just the neighbors of AS 65000
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp=65000/neighbor")

# A specific neighbor
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp=65000/neighbor=10.0.0.2")

# Address-family config
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family")
```

## Add a BGP Neighbor

Use PATCH on the BGP instance. PATCH merges — the new neighbor is added alongside all existing neighbors. Nothing is removed or overwritten.

### Basic eBGP neighbor

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000",
    payload={
        "Cisco-IOS-XE-bgp:bgp": {
            "id": 65000,
            "neighbor": [
                {
                    "id": "10.0.0.2",
                    "remote-as": 65001
                }
            ]
        }
    }
)
```

### eBGP neighbor with description and update-source

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000",
    payload={
        "Cisco-IOS-XE-bgp:bgp": {
            "id": 65000,
            "neighbor": [
                {
                    "id": "10.0.0.2",
                    "remote-as": 65001,
                    "description": "Peer to ISP-A",
                    "update-source": {
                        "Loopback": "0"
                    },
                    "ebgp-multihop": {
                        "max-hop": 2
                    }
                }
            ]
        }
    }
)
```

### iBGP neighbor (same AS)

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000",
    payload={
        "Cisco-IOS-XE-bgp:bgp": {
            "id": 65000,
            "neighbor": [
                {
                    "id": "10.255.255.2",
                    "remote-as": 65000,
                    "description": "iBGP to Core-Router-2",
                    "update-source": {
                        "Loopback": "0"
                    }
                }
            ]
        }
    }
)
```

### Add multiple neighbors at once

Include multiple entries in the `neighbor` array. PATCH merges all of them — existing neighbors are untouched.

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000",
    payload={
        "Cisco-IOS-XE-bgp:bgp": {
            "id": 65000,
            "neighbor": [
                {
                    "id": "10.0.0.2",
                    "remote-as": 65001,
                    "description": "Peer to ISP-A"
                },
                {
                    "id": "10.0.0.6",
                    "remote-as": 65002,
                    "description": "Peer to ISP-B"
                },
                {
                    "id": "10.255.255.2",
                    "remote-as": 65000,
                    "description": "iBGP to Core-2"
                }
            ]
        }
    }
)
```

## Activate a Neighbor in an Address-Family

Adding a neighbor at the process level does NOT activate it. You must also activate the neighbor inside the appropriate address-family.

### Activate in IPv4 unicast (no VRF)

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast",
    payload={
        "Cisco-IOS-XE-bgp:ipv4": {
            "af-name": "unicast",
            "ipv4-unicast": {
                "neighbor": [
                    {
                        "id": "10.0.0.2",
                        "activate": [null]
                    }
                ]
            }
        }
    }
)
```

### Activate multiple neighbors at once

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast",
    payload={
        "Cisco-IOS-XE-bgp:ipv4": {
            "af-name": "unicast",
            "ipv4-unicast": {
                "neighbor": [
                    {
                        "id": "10.0.0.2",
                        "activate": [null]
                    },
                    {
                        "id": "10.0.0.6",
                        "activate": [null]
                    },
                    {
                        "id": "10.255.255.2",
                        "activate": [null]
                    }
                ]
            }
        }
    }
)
```

### Activate with route-map and soft-reconfiguration

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast",
    payload={
        "Cisco-IOS-XE-bgp:ipv4": {
            "af-name": "unicast",
            "ipv4-unicast": {
                "neighbor": [
                    {
                        "id": "10.0.0.2",
                        "activate": [null],
                        "route-map": [
                            {
                                "inout": "in",
                                "route-map-name": "ISP-A-IN"
                            },
                            {
                                "inout": "out",
                                "route-map-name": "ISP-A-OUT"
                            }
                        ],
                        "soft-reconfiguration": "inbound"
                    }
                ]
            }
        }
    }
)
```

## Add Network Statements

Network statements advertise prefixes into BGP. Use PATCH — it merges new networks alongside existing ones.

### Add a network to IPv4 unicast

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast",
    payload={
        "Cisco-IOS-XE-bgp:ipv4": {
            "af-name": "unicast",
            "ipv4-unicast": {
                "network": {
                    "with-mask": [
                        {
                            "number": "192.168.1.0",
                            "mask": "255.255.255.0"
                        }
                    ]
                }
            }
        }
    }
)
```

### Add multiple networks at once

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast",
    payload={
        "Cisco-IOS-XE-bgp:ipv4": {
            "af-name": "unicast",
            "ipv4-unicast": {
                "network": {
                    "with-mask": [
                        {
                            "number": "192.168.1.0",
                            "mask": "255.255.255.0"
                        },
                        {
                            "number": "192.168.2.0",
                            "mask": "255.255.255.0"
                        },
                        {
                            "number": "10.0.0.0",
                            "mask": "255.255.0.0"
                        }
                    ]
                }
            }
        }
    }
)
```

### Add networks AND activate neighbors in a single PATCH

You can combine network statements and neighbor activation in one PATCH call since they are both under the same address-family:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast",
    payload={
        "Cisco-IOS-XE-bgp:ipv4": {
            "af-name": "unicast",
            "ipv4-unicast": {
                "neighbor": [
                    {
                        "id": "10.0.0.2",
                        "activate": [null]
                    }
                ],
                "network": {
                    "with-mask": [
                        {
                            "number": "192.168.1.0",
                            "mask": "255.255.255.0"
                        }
                    ]
                }
            }
        }
    }
)
```

## Remove a Specific Neighbor

Only do this when the user explicitly asks to remove a specific neighbor. This removes ONLY the targeted neighbor — nothing else.

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/neighbor=10.0.0.2"
)
```

**Also deactivate from address-families if the neighbor was activated:**

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast/ipv4-unicast/neighbor=10.0.0.2"
)
```

## Remove a Specific Network Statement

Only when the user explicitly asks to stop advertising a specific prefix:

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast/ipv4-unicast/network/with-mask=192.168.1.0,255.255.255.0"
)
```

## Shut Down / Bring Up a BGP Neighbor

### Admin-shutdown a neighbor (stop peering without removing config)

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000",
    payload={
        "Cisco-IOS-XE-bgp:bgp": {
            "id": 65000,
            "neighbor": [
                {
                    "id": "10.0.0.2",
                    "shutdown": [null]
                }
            ]
        }
    }
)
```

### Remove shutdown from a neighbor (re-enable peering)

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/neighbor=10.0.0.2/shutdown"
)
```

## Update Neighbor Description

PATCH merges — only the description changes, everything else on the neighbor is untouched:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000",
    payload={
        "Cisco-IOS-XE-bgp:bgp": {
            "id": 65000,
            "neighbor": [
                {
                    "id": "10.0.0.2",
                    "description": "Updated: Primary ISP-A peer"
                }
            ]
        }
    }
)
```

## BGP Process-Level Settings

### Set router-id

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000",
    payload={
        "Cisco-IOS-XE-bgp:bgp": {
            "id": 65000,
            "bgp": {
                "router-id": {
                    "ip-addr": "10.255.255.1"
                }
            }
        }
    }
)
```

### Enable log-neighbor-changes

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000",
    payload={
        "Cisco-IOS-XE-bgp:bgp": {
            "id": 65000,
            "bgp": {
                "log-neighbor-changes": [null]
            }
        }
    }
)
```

## Redistribution into BGP

### Redistribute connected routes into IPv4 unicast

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast",
    payload={
        "Cisco-IOS-XE-bgp:ipv4": {
            "af-name": "unicast",
            "ipv4-unicast": {
                "redistribute": {
                    "connected": {}
                }
            }
        }
    }
)
```

### Redistribute static routes with a route-map

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family/no-vrf/ipv4=unicast",
    payload={
        "Cisco-IOS-XE-bgp:ipv4": {
            "af-name": "unicast",
            "ipv4-unicast": {
                "redistribute": {
                    "static": {
                        "route-map": "STATIC-TO-BGP"
                    }
                }
            }
        }
    }
)
```

## Verify BGP Configuration

After every change:

```
# Read the full BGP config to confirm the change
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp=65000")

# Check specific neighbor
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp=65000/neighbor=10.0.0.2")

# Check address-family
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp=65000/address-family")

# Operational state — see reference/operational.md
iosxe_restconf_get(path="Cisco-IOS-XE-bgp-oper:bgp-state-data/address-families", params={...})
```

## Always Save After Changes

```
iosxe_save_config()
```

## End-to-End: Add a New BGP Peer

**For CML PAT / C8000V (this lab): use the WRITE RECIPE at the top of this file** — PATCH `Cisco-IOS-XE-native:native` twice (neighbor, then AF). Do not use keyed `bgp=65000` write paths.

Generic keyed-path examples earlier in this file may work on some platforms; if you see `unknown-element: bgp=<AS>`, switch immediately to the native-parent recipe. Never call `iosxe_get_platform_and_yang` to debug that error.

```
1. READ  → GET Cisco-IOS-XE-native:native/router/bgp
2. ADD neighbor  → PATCH path=Cisco-IOS-XE-native:native  (Step B recipe)
3. ACTIVATE AF   → PATCH path=Cisco-IOS-XE-native:native  (Step C recipe; include next-hop-self + as-override for WAN→branch)
4. VERIFY → GET router/bgp (confirm new neighbor alongside existing)
5. SAVE → iosxe_save_config()
```

## Prohibited Operations

| Operation | Why it is forbidden |
|-----------|-------------------|
| `iosxe_restconf_put` on `router/bgp` | Replaces the entire BGP process — all neighbors, all address-families, everything is wiped |
| `iosxe_restconf_put` on `router/bgp=65000` | Replaces the entire BGP instance — same destruction |
| `iosxe_restconf_put` on `address-family/no-vrf/ipv4=unicast` | Replaces the entire address-family — all activated neighbors and all network statements are wiped |
| `iosxe_restconf_delete` on `router/bgp` | Removes the entire BGP process from the device |
| `iosxe_restconf_delete` on `router/bgp=65000` | Removes the entire BGP instance |
| `iosxe_restconf_delete` on `address-family` | Removes all address-families |
| Any PUT or DELETE on a broad BGP path without the user explicitly requesting removal of that specific resource | Potentially destructive — always ask the user first |

The only safe DELETE targets are:
- A specific neighbor: `router/bgp=65000/neighbor=<IP>`
- A specific network: `router/bgp=65000/address-family/no-vrf/ipv4=unicast/ipv4-unicast/network/with-mask=<prefix>,<mask>`
- A specific leaf on a neighbor (e.g., `/shutdown`, `/description`)

## Decision Guide

| User says | Action | Method | Safe? |
|-----------|--------|--------|-------|
| "add a BGP neighbor" | Add neighbor + activate in AF | PATCH (two calls) | Yes |
| "add multiple neighbors" | Add all in one PATCH + activate all in one PATCH | PATCH (two calls) | Yes |
| "advertise a network" / "add a network statement" | Add network in AF | PATCH | Yes |
| "shut down neighbor X" | Add shutdown leaf to neighbor | PATCH | Yes |
| "bring up neighbor X" / "no shut" | Remove shutdown leaf | DELETE on specific leaf | Yes |
| "update neighbor description" | Merge new description | PATCH | Yes |
| "remove neighbor X" | Delete specific neighbor + deactivate in AF | DELETE (two calls) | Yes — confirm with user |
| "stop advertising 192.168.1.0/24" | Delete specific network statement | DELETE on specific entry | Yes — confirm with user |
| "replace the BGP config" / "reconfigure BGP" | **REFUSE.** Explain that this is destructive and ask the user to specify exactly what to add or remove instead. | N/A | **NEVER** |
| "delete BGP" / "remove the BGP process" | **REFUSE unless the user explicitly confirms.** Explain the consequences. | N/A | **NEVER without explicit confirmation** |
