# WAN hub peer recipe — add a branch spoke to an existing hub

Use when a new branch router exists and the hub side must be configured: bring up
the /30 link and add the eBGP neighbor. RESTCONF only.

This is the exact shape that works on CML-backed C8000V. Do not derive a new shape
from the YANG models — keyed write paths return `unknown-element` on this lab even
when the equivalent GET works.

## Before you write

1. Get the hub's PAT port. `cml_get_node_info` on the hub exposes `pat:<ext>:443`
   → use that as the MCP `port`, with the CML controller as `host`. Never omit
   `port`; never assume 443.
2. Identify which hub interface faces the new branch, from the CML link you just
   created. Do not copy an interface number from another branch.
3. Read the current BGP config first:

```text
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp")
```

Note the hub's local AS from that response rather than assuming it.

## 1 — Hub interface

PATCH the **parent** `interface` container. The interface number goes in the body
as `name`, not in the path. Omit CDP.

```text
iosxe_restconf_patch(
  path="Cisco-IOS-XE-native:native/interface",
  payload={
    "Cisco-IOS-XE-native:interface": {
      "GigabitEthernet": [{
        "name": "6",
        "description": "Link to AI-BRANCH-03",
        "ip": { "address": { "primary": {
          "address": "100.64.7.1", "mask": "255.255.255.252"
        }}}
      }]
    }
  }
)
```

Bring it up by deleting the `shutdown` leaf — there is no "no shutdown" write:

```text
iosxe_restconf_delete(
  path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=6/shutdown"
)
```

Convention: the branch holds `.2/30`, the hub holds `.1`.

## 2 — eBGP neighbor

PATCH `Cisco-IOS-XE-native:native` and wrap `router` → `Cisco-IOS-XE-bgp:bgp`.
**Never PUT on any BGP path** — PUT replaces the resource and drops every existing
neighbor.

```text
iosxe_restconf_patch(
  path="Cisco-IOS-XE-native:native",
  payload={
    "Cisco-IOS-XE-native:native": {
      "router": { "Cisco-IOS-XE-bgp:bgp": [{
        "id": 65000,
        "neighbor": [{ "id": "100.64.7.2", "remote-as": 65100 }]
      }]}
    }
  }
)
```

## 3 — Activate under the address family

The neighbor does not exchange routes until it is activated. This is a separate
PATCH, same parent path.

```text
iosxe_restconf_patch(
  path="Cisco-IOS-XE-native:native",
  payload={
    "Cisco-IOS-XE-native:native": {
      "router": { "Cisco-IOS-XE-bgp:bgp": [{
        "id": 65000,
        "address-family": { "no-vrf": { "ipv4": [{
          "af-name": "unicast",
          "ipv4-unicast": { "neighbor": [{
            "id": "100.64.7.2",
            "activate": [null],
            "next-hop-self": {},
            "as-override": {}
          }]}
        }]}}
      }]}
    }
  }
)
```

## 4 — Save and verify

```text
iosxe_save_config()
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface/GigabitEthernet=6")
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp")
```

Verify over RESTCONF, never SSH. The neighbor will not be Established until the
branch side is up — that is the live test's job to confirm, not a reason to
re-write the hub.

## Hard fails

Fix these before reporting anything:

- The CML link to the hub exists but the hub was never configured.
- Configured the wrong hub interface, or an interface number copied from another
  branch.
- `PUT` used on any BGP path.
- Keyed write paths in the PATCH path — `bgp=65000`, `GigabitEthernet=6` — instead
  of the parent container with the key in the body.
- Neighbor added but never activated under the address family.
- SSH used for configuration or verification.
- An `unknown-element` or `Internal error` response treated as success. Retry the
  parent-path recipe once; do not go browsing YANG models for a new shape.
