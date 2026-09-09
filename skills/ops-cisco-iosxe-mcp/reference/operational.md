# Cisco IOS-XE Operational State (Troubleshooting)

Read-only operational data via RESTCONF `-oper` YANG models. Equivalent to `show` commands — use for troubleshooting, verification, and diagnostics.

**Rules:**
- Use `iosxe_restconf_get` only. Never PUT, PATCH, or DELETE on operational paths.
- Never use SSH for operational reads.
- Operational data is separate from configuration. To change config, use the appropriate config reference (e.g. [bgp.md](bgp.md), [interfaces.md](interfaces.md)).
- Use `params={"fields": "..."}` to limit large responses. Pass a native dict, not a JSON string.

## Field filter syntax

```
container(list-name(field1;field2;nested/leaf))
```

Semicolons separate siblings; slashes descend into nested containers.

---

## BGP

**Model:** `Cisco-IOS-XE-bgp-oper`  
**Config reference:** [bgp.md](bgp.md)

### Neighbor summary — start here

Equivalent to `show ip bgp summary`. Use for any BGP health check.

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-bgp-oper:bgp-state-data/address-families",
    params={
        "fields": "address-family(afi-safi;vrf-name;router-id;local-as;bgp-table-version;routing-table-version;bgp-neighbor-summaries/bgp-neighbor-summary(id;as;state;up-time;prefixes-received;input-queue;output-queue;messages-received;messages-sent))"
    }
)
```

| Field | Healthy | Problem |
|-------|---------|---------|
| `state` | `fsm-established` | `fsm-active`, `fsm-idle`, `fsm-connect`, etc. |
| `up-time` | Duration (e.g. `6d01h`) | `never` or empty |
| `prefixes-received` | Non-zero when routes expected | `0` on an established peer |
| `input-queue` / `output-queue` | `0` | Sustained non-zero |

Common FSM states: `fsm-established` (up), `fsm-active` (trying TCP — check reachability/ACL/179), `fsm-idle` (not connecting — check `shutdown` in config).

### Neighbor detail — when a peer looks unhealthy

Equivalent to `show ip bgp neighbors`. Use when summary shows non-Established state, zero prefixes, or queue buildup.

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors",
    params={
        "fields": "neighbor(neighbor-id;description;link;as;afi-safi;vrf-name;session-state;up-time;last-read;last-write;installed-prefixes;connection;transport;bgp-neighbor-counters;prefix-activity;negotiated-keepalive-timers)"
    }
)
```

Key detail fields:
- `connection.state` / `connection.reset-reason` — why session is down
- `transport.local-host` / `foreign-host` / ports — TCP endpoints; ports `0` means TCP never established
- `bgp-neighbor-counters` — `notifications > 0` indicates policy/capability rejection

Cross-check with running config when a peer is down:

```
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/bgp")
```

---

## IS-IS

**Model:** `Cisco-IOS-XE-isis-oper`

### IS-IS neighbors

Equivalent to `show isis neighbors`. Use to verify adjacency state, find neighbor system IDs, or troubleshoot IS-IS peering on a per-interface basis.

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-isis-oper:isis-oper-data"
)
```

Focused filter:

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-isis-oper:isis-oper-data",
    params={
        "fields": "isis-instance(tag;isis-neighbor(system-id;level;if-name;ipv4-address;ipv6-address;state;holdtime))"
    }
)
```

Specific IS-IS instance by tag:

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-isis-oper:isis-oper-data/isis-instance=<TAG>"
)
```

Replace `<TAG>` with the IS-IS router tag (e.g. `1`, `CORE`). Numeric tags are common.

Response is keyed under `Cisco-IOS-XE-isis-oper:isis-oper-data` with `isis-instance[]` (keyed by `tag`), each containing `isis-neighbor[]` (compound key: `system-id`, `level`, `if-name`).

| Field | Use |
|-------|-----|
| `tag` | IS-IS process/router tag |
| `system-id` | Neighbor system ID (6-byte ISO address) |
| `level` | Adjacency level: `isis-level-1` or `isis-level-2` |
| `if-name` | Local interface the adjacency is on |
| `ipv4-address` / `ipv6-address` | Neighbor IP addresses |
| `state` | Adjacency state (see table below) |
| `holdtime` | Remaining hold time in seconds |

### Adjacency states

| State | Meaning | Typical cause |
|-------|---------|---------------|
| `isis-adj-up` | Adjacency established | Normal |
| `isis-adj-down` | Adjacency down | Interface down, mismatched NET/area, authentication failure, or no IIH received |
| `isis-adj-init` | Initializing | Transient during bring-up; persistent init → check MTU, level mismatch, or circuit type |
| `isis-adj-standby` | Standby adjacency | Multi-topology or redundancy scenario |

**Troubleshooting uses:**
- "Are IS-IS neighbors up?" → look for `state: isis-adj-up` on expected interfaces
- "Neighbor missing on Gi1/0/1" → no `isis-neighbor` entry with matching `if-name`; check interface `ip router isis`, IS-IS enabled on process, and link state
- "L1 vs L2 issue" → check `level` matches design on both sides of the link
- "Adjacency flapping" → `holdtime` resetting or state toggling between `isis-adj-init` and `isis-adj-down`

Cross-check with running config when adjacencies are down:

```
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/router/isis")
```

---

## CDP

**Model:** `Cisco-IOS-XE-cdp-oper`

### CDP neighbors

Equivalent to `show cdp neighbors detail`. Use to discover directly connected devices, verify cabling, identify neighbor platforms, or find management IPs.

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-cdp-oper:cdp-neighbor-details"
)
```

Focused filter (smaller response):

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-cdp-oper:cdp-neighbor-details",
    params={
        "fields": "cdp-neighbor-detail(device-name;local-intf-name;port-id;capability;platform-name;ip-address;mgmt-address;version;duplex)"
    }
)
```

Response is a list under `cdp-neighbor-detail[]`, keyed by `device-id`.

| Field | Use |
|-------|-----|
| `device-name` | Remote hostname |
| `local-intf-name` | Local interface that received the CDP advertisement |
| `port-id` | Remote interface connected to this device |
| `platform-name` | Remote device model (e.g. `cisco C9300-24P`) |
| `capability` | Device role: `R` router, `S` switch, `H` host, etc. |
| `ip-address` / `mgmt-address` | Reachable IPs for the neighbor |
| `version` | Remote IOS/software version |

**Troubleshooting uses:**
- "What's connected to Gi1/0/1?" → filter results by `local-intf-name`
- "I don't see a neighbor" → empty list on that interface may mean CDP disabled, wrong cable, or link down
- Layer-2 topology mapping → correlate `local-intf-name` ↔ `device-name` / `port-id`

CDP is enabled in config under `Cisco-IOS-XE-native:native/cdp`. If neighbors are missing, read that container to check whether CDP is globally or per-interface disabled.

---

## ARP

**Model:** `Cisco-IOS-XE-arp-oper`

### ARP table

Equivalent to `show ip arp` / `show arp vrf <name>`. Use to verify L2/L3 resolution, find MAC addresses for IPs, or diagnose connectivity to next-hop addresses.

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-arp-oper:arp-data"
)
```

Response is keyed under `Cisco-IOS-XE-arp-oper:arp-data` with `arp-vrf[]` (keyed by `vrf`), each containing `arp-oper[]` entries (keyed by IP `address`).

| Field | Use |
|-------|-----|
| `vrf` | VRF name |
| `address` | IP address |
| `hardware` | MAC address |
| `interface` | Interface for this entry |
| `mode` | Entry mode (e.g. dynamic, static, incomplete) |
| `time` | Last update timestamp |

**Troubleshooting uses:**
- "Can this router reach 10.0.0.1?" → look up `address`; missing entry means no L2 resolution yet
- "Wrong MAC for an IP" → compare `hardware` to expected device
- "ARP incomplete" → look for `mode` indicating incomplete, or missing/stale entry
- VRF-scoped lookups → filter `arp-vrf` entries by `vrf` name

---

## ACL

**Model:** `Cisco-IOS-XE-acl-oper` (operational) / `Cisco-IOS-XE-native` (configuration)

ACL has two layers:
- **Operational** — hit counters and rule match statistics (`show access-lists`)
- **Configuration** — ACE definitions (`show run | section access-list`)

### ACL hit counters — operational

Equivalent to `show access-lists` / `show ip access-lists`. Use to verify which ACEs are matching traffic, debug permit/deny behavior, or confirm an ACL is actually being hit.

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-acl-oper:access-lists"
)
```

Focused filter (match counters per rule):

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-acl-oper:access-lists",
    params={
        "fields": "access-list(access-control-list-name;access-control-list-type;access-list-entries/access-list-entry(rule-name;access-list-entries-oper-data/match-counter))"
    }
)
```

Specific ACL by name:

```
iosxe_restconf_get(
    path="Cisco-IOS-XE-acl-oper:access-lists/access-list=<ACL_NAME>"
)
```

Replace `<ACL_NAME>` with the ACL name (e.g. `GUEST_IN`, `100`). URL-encode special characters if needed.

Response is a list under `access-list[]`, each containing `access-list-entries/access-list-entry[]`.

| Field | Use |
|-------|-----|
| `access-control-list-name` | ACL name |
| `access-control-list-type` | Standard, extended, etc. |
| `rule-name` | Sequence/rule number (e.g. `10`, `20`) |
| `match-counter` | Number of packets that matched this ACE — `0` means the rule is not being hit |

Operational entries may also include `access-list-entries-rule-data` with the parsed match criteria (source, destination, protocol, action). Use this to correlate counters with specific permit/deny rules.

**Troubleshooting uses:**
- "Is my ACL blocking traffic?" → find the ACL, check which `match-counter` values are incrementing
- "Rule never matches" → `match-counter: 0` on expected ACE; verify ACL is applied to the correct interface/line and config criteria are correct
- "Traffic allowed when it shouldn't be" → look for a permit rule above the deny with a high `match-counter`
- Cross-check config when counters look wrong:

```
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/ip/access-list")
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/ip/access-list/extended")
```

---

## Quick reference

| Goal | Path | CLI equivalent |
|------|------|----------------|
| BGP neighbor summary | `Cisco-IOS-XE-bgp-oper:bgp-state-data/address-families` + fields filter | `show ip bgp summary` |
| BGP neighbor detail | `Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors` + fields filter | `show ip bgp neighbors` |
| BGP running config | `Cisco-IOS-XE-native:native/router/bgp` | `show run \| section router bgp` |
| IS-IS neighbors | `Cisco-IOS-XE-isis-oper:isis-oper-data` | `show isis neighbors` |
| IS-IS running config | `Cisco-IOS-XE-native:native/router/isis` | `show run \| section router isis` |
| CDP neighbors | `Cisco-IOS-XE-cdp-oper:cdp-neighbor-details` | `show cdp neighbors detail` |
| ARP table | `Cisco-IOS-XE-arp-oper:arp-data` | `show ip arp` |
| ACL hit counters | `Cisco-IOS-XE-acl-oper:access-lists` | `show access-lists` |
| ACL configuration | `Cisco-IOS-XE-native:native/ip/access-list` | `show run \| section access-list` |
