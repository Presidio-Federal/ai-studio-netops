# Cisco IOS-XE Model-Driven Telemetry (MDT)

Model-driven telemetry pushes structured operational data from IOS-XE devices to a receiver using gRPC dial-out. Unlike syslog (unstructured log messages), MDT streams real-time metrics — interface counters, CPU utilization, memory, routing table changes — encoded as key-value Google Protocol Buffers (kvGPB).

For syslog configuration, see [syslog.md](syslog.md) instead.

All configuration MUST use RESTCONF tools. Do not use SSH for telemetry configuration.

## Prerequisites — Receiver Required

MDT streams use gRPC. Before configuring subscriptions on the device, the user **must** have a running receiver that can decode gRPC telemetry. Ask the user:

> "Model-driven telemetry streams use gRPC. You need a receiver that can decode gRPC telemetry — for example **Telegraf** (with the `cisco_telemetry_mdt` input plugin), **Cribl**, **Pipeline**, or any gRPC-capable collector. Do you have one of these? If so, what is its **IP address** and **port**?"

If the user does not have a receiver, telemetry cannot be configured — inform them and stop.

Typical receiver defaults:

| Receiver | Default Port | Notes |
|----------|-------------|-------|
| Telegraf (`cisco_telemetry_mdt`) | 57000 | Most common for IOS-XE MDT |
| Cribl | Varies | User must confirm the gRPC input port |
| Pipeline (Cisco) | 57500 | Cisco's own collector |

## YANG Model

MDT subscriptions use the `Cisco-IOS-XE-mdt-cfg` YANG model. The RESTCONF base path is:

```
Cisco-IOS-XE-mdt-cfg:mdt-config-data
```

To fetch the full YANG model definition for reference:

```
iosxe_get_platform_and_yang(yang_model="Cisco-IOS-XE-mdt-cfg")
```

## Subscription Structure

Each subscription has a numeric ID and contains:

- **base** — what to stream:
  - `stream`: always `"yang-push"` for periodic subscriptions
  - `encoding`: always `"encode-kvgpb"` (key-value GPB)
  - `xpath`: the YANG operational data path to stream
  - `period`: push interval in centiseconds (3000 = 30 seconds, 6000 = 60 seconds)
- **mdt-receivers** — where to send:
  - `address`: receiver IP
  - `port`: receiver port
  - `protocol`: `"grpc-tcp"` for unencrypted gRPC

## CRUD Operations

All operations use the existing RESTCONF tools. The YANG path `Cisco-IOS-XE-mdt-cfg:mdt-config-data` is the parent container. Individual subscriptions are keyed by `mdt-subscription=<id>`.

### READ — Check for existing subscriptions

Always read first before creating or modifying subscriptions.

```
iosxe_restconf_get(path="Cisco-IOS-XE-mdt-cfg:mdt-config-data")
```

If no subscriptions exist, this returns an empty container or a 404. Both mean zero subscriptions are configured.

### READ — Get a specific subscription

```
iosxe_restconf_get(path="Cisco-IOS-XE-mdt-cfg:mdt-config-data/mdt-subscription=101")
```

### CREATE — New subscription

Use PATCH on the parent container. PATCH merges — it will not touch existing subscriptions.

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-config-data": {
            "mdt-subscription": [
                {
                    "subscription-id": 101,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/interfaces-ios-xe-oper:interfaces/interface/statistics",
                        "period": 3000
                    },
                    "mdt-receivers": [
                        {
                            "address": "<RECEIVER_IP>",
                            "port": 57000,
                            "protocol": "grpc-tcp"
                        }
                    ]
                }
            ]
        }
    }
)
```

### CREATE — Multiple subscriptions at once

Add more entries to the `mdt-subscription` array in the same PATCH:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-config-data": {
            "mdt-subscription": [
                {
                    "subscription-id": 101,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/interfaces-ios-xe-oper:interfaces/interface/statistics",
                        "period": 3000
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 102,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/process-cpu-ios-xe-oper:cpu-usage/cpu-utilization/five-seconds",
                        "period": 6000
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                }
            ]
        }
    }
)
```

### UPDATE — Replace an entire subscription

Use PUT on the specific subscription. This replaces only that subscription entry — nothing else is affected.

**WARNING:** PUT replaces the entire subscription. You MUST include all fields (`stream`, `encoding`, `xpath`, `period`, `mdt-receivers`) even if you only want to change one. Any field you omit gets wiped.

```
iosxe_restconf_put(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data/mdt-subscription=101",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-subscription": {
            "subscription-id": 101,
            "base": {
                "stream": "yang-push",
                "encoding": "encode-kvgpb",
                "xpath": "/interfaces-ios-xe-oper:interfaces/interface/statistics",
                "period": 6000
            },
            "mdt-receivers": [
                {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
            ]
        }
    }
)
```

### UPDATE — Partial update (change one field, keep everything else)

Use PATCH on the specific subscription. Only the fields you include get changed:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data/mdt-subscription=101",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-subscription": {
            "subscription-id": 101,
            "base": {
                "period": 10000
            }
        }
    }
)
```

### UPDATE — Add a receiver to an existing subscription

PATCH merges, so existing receivers stay:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data/mdt-subscription=101",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-subscription": {
            "subscription-id": 101,
            "mdt-receivers": [
                {"address": "<ADDITIONAL_RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
            ]
        }
    }
)
```

### DELETE — Remove a specific subscription

```
iosxe_restconf_delete(path="Cisco-IOS-XE-mdt-cfg:mdt-config-data/mdt-subscription=101")
```

### DELETE — Remove a specific receiver from a subscription

Receivers are keyed by address and port (comma-separated in the path):

```
iosxe_restconf_delete(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data/mdt-subscription=101/mdt-receivers=10.0.0.200,57000"
)
```

### DELETE — Remove all subscriptions

**Destructive** — this wipes every subscription on the device:

```
iosxe_restconf_delete(path="Cisco-IOS-XE-mdt-cfg:mdt-config-data")
```

Only do this if the user explicitly asks to remove all telemetry. Confirm with the user first.

## Quick Reference

| Operation | Method | Path | Safe? |
|-----------|--------|------|-------|
| List all subscriptions | GET | `mdt-config-data` | Yes |
| Get one subscription | GET | `mdt-config-data/mdt-subscription=<id>` | Yes |
| Create subscription(s) | PATCH | `mdt-config-data` | Yes — merges |
| Replace one subscription | PUT | `mdt-config-data/mdt-subscription=<id>` | Yes — scoped to one entry |
| Partial update | PATCH | `mdt-config-data/mdt-subscription=<id>` | Yes — only changes what you send |
| Add receiver | PATCH | `mdt-config-data/mdt-subscription=<id>` | Yes — merges |
| Delete one subscription | DELETE | `mdt-config-data/mdt-subscription=<id>` | Yes |
| Delete one receiver | DELETE | `.../mdt-subscription=<id>/mdt-receivers=<addr>,<port>` | Yes |
| Delete everything | DELETE | `mdt-config-data` | **Destructive** — confirm with user |

**The golden rule:** PATCH to create or add, PUT only on a specific list entry when replacing it entirely, never PUT on the parent container.

## Common XPath Sensors

These are the most useful operational data paths for telemetry subscriptions. Use the full xpath value in the `base.xpath` field.

| What it streams | xpath | Suggested period |
|----------------|-------|-----------------|
| All interface statistics (counters, bytes, packets) | `/interfaces-ios-xe-oper:interfaces/interface/statistics` | 3000 (30s) |
| Single interface statistics | `/interfaces-ios-xe-oper:interfaces/interface[name='GigabitEthernet1']/statistics` | 3000 (30s) |
| CPU utilization (5-second average) | `/process-cpu-ios-xe-oper:cpu-usage/cpu-utilization/five-seconds` | 6000 (60s) |
| Memory statistics | `/memory-ios-xe-oper:memory-statistics/memory-statistic` | 6000 (60s) |
| OSPF neighbor state | `/ospf-ios-xe-oper:ospf-oper-data/ospf-state/ospf-instance/ospf-area/ospf-interface/ospf-neighbor` | 6000 (60s) |
| BGP neighbor connection state | `/bgp-state-data/neighbors/neighbor/connection` | 1500 (15s) |
| BGP neighbor counters | `/bgp-state-data/neighbors/neighbor/bgp-neighbor-counters` | 1500 (15s) |
| BGP prefix activity (advertised/received/withdrawn) | `/bgp-state-data/neighbors/neighbor/prefix-activity` | 1500 (15s) |
| BGP transport (TCP session details) | `/bgp-state-data/neighbors/neighbor/transport` | 1500 (15s) |
| BGP neighbor uptime | `/bgp-state-data/neighbors/neighbor/up-time` | 1500 (15s) |
| BGP neighbor summary (per address family) | `/bgp-state-data/address-families/address-family/bgp-neighbor-summaries/bgp-neighbor-summary` | 1500 (15s) |
| BGP peer state change (event-driven) | `/ios-events-ios-xe-oper:bgp-peer-state-change` | on-change |
| BGP all neighbor data (broad) | `/bgp-ios-xe-oper:bgp-state-data/neighbors/neighbor` | 6000 (60s) |
| IP SLA total statistics (RTT, jitter, packet loss) | `/ip-sla-stats/sla-oper-total-statistics` | 1500 (15s) |
| IP SLA RTT info (per-operation round-trip time) | `/ip-sla-stats/sla-oper-entry/rtt-info` | 1500 (15s) |
| IP SLA latest return code and status | `/ip-sla-stats/sla-oper-entry/latest-return-code` | 1500 (15s) |
| IP SLA specific operation (filter by oper-id) | `/ip-sla-stats/sla-oper-entry[oper-id='<ID>']/stats` | 1500 (15s) |
| Environment sensors (temperature, fans, power) | `/environment-ios-xe-oper:environment-sensors/environment-sensor` | 30000 (5m) |
| IP route table | `/ip-route-ios-xe-oper:ip-route-data/ip-route` | 12000 (2m) |

Period is in centiseconds: 100 = 1 second, 3000 = 30 seconds, 6000 = 60 seconds.

## XPath Filtering — Targeting Specific Interfaces

By default, the interface statistics xpath streams data for **every** interface on the device. To stream only a specific interface, add a YANG list key filter using `[name='<interface-name>']` in the xpath.

### Filter syntax

```
/interfaces-ios-xe-oper:interfaces/interface[name='<INTERFACE_NAME>']/statistics
```

Replace `<INTERFACE_NAME>` with the exact interface name as it appears on the device (case-sensitive).

### Examples

| Interface | Filtered xpath |
|-----------|---------------|
| GigabitEthernet1 | `/interfaces-ios-xe-oper:interfaces/interface[name='GigabitEthernet1']/statistics` |
| GigabitEthernet1/0/1 | `/interfaces-ios-xe-oper:interfaces/interface[name='GigabitEthernet1/0/1']/statistics` |
| Loopback0 | `/interfaces-ios-xe-oper:interfaces/interface[name='Loopback0']/statistics` |
| Vlan100 | `/interfaces-ios-xe-oper:interfaces/interface[name='Vlan100']/statistics` |

### When to use filtered vs unfiltered

- **User asks to monitor a specific interface** (e.g., "monitor GigabitEthernet1", "stream stats for my uplink") → use the filtered xpath with `[name='...']`
- **User asks to monitor all interfaces** or says "all interface stats" → use the unfiltered xpath without the filter
- **User asks to monitor several specific interfaces** → create a separate subscription for each interface, each with its own filtered xpath and a unique subscription ID

### Example — Subscribe to a single interface

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-config-data": {
            "mdt-subscription": [
                {
                    "subscription-id": 103,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/interfaces-ios-xe-oper:interfaces/interface[name='GigabitEthernet1']/statistics",
                        "period": 3000
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                }
            ]
        }
    }
)
```

### Example — Subscribe to multiple specific interfaces

One subscription per interface, all in a single PATCH:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-config-data": {
            "mdt-subscription": [
                {
                    "subscription-id": 103,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/interfaces-ios-xe-oper:interfaces/interface[name='GigabitEthernet1']/statistics",
                        "period": 3000
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 104,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/interfaces-ios-xe-oper:interfaces/interface[name='GigabitEthernet2']/statistics",
                        "period": 3000
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                }
            ]
        }
    }
)
```

### Discovering interface names on the device

If you do not know the exact interface names, read them first:

```
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface")
```

Use the interface names from the response exactly as returned (e.g., `GigabitEthernet1`, not `Gi1` or `gig1`).

## BGP Telemetry

BGP monitoring benefits from multiple focused subscriptions rather than a single broad one. Each xpath targets a specific aspect of BGP state, keeping the data granular and easier to process at the receiver.

### Available BGP xpaths

| What it captures | xpath | Stream type | Update policy |
|-----------------|-------|-------------|---------------|
| Connection state (established, idle, connect, active, open-sent, open-confirm) | `/bgp-state-data/neighbors/neighbor/connection` | `yang-push` | periodic |
| Neighbor counters (messages sent/received, notifications, updates) | `/bgp-state-data/neighbors/neighbor/bgp-neighbor-counters` | `yang-push` | periodic |
| Prefix activity (prefixes advertised, received, withdrawn, bestpaths) | `/bgp-state-data/neighbors/neighbor/prefix-activity` | `yang-push` | periodic |
| Transport (TCP session info — local/remote address, port, MSS, path MTU) | `/bgp-state-data/neighbors/neighbor/transport` | `yang-push` | periodic |
| Uptime (how long the neighbor session has been established) | `/bgp-state-data/neighbors/neighbor/up-time` | `yang-push` | periodic |
| Neighbor summary per address family (state, prefixes, up/down time) | `/bgp-state-data/address-families/address-family/bgp-neighbor-summaries/bgp-neighbor-summary` | `yang-push` | periodic |
| Peer state change event (fires when a peer transitions state) | `/ios-events-ios-xe-oper:bgp-peer-state-change` | `yang-notif-native` | on-change |

### Periodic vs on-change subscriptions

Most BGP xpaths use `yang-push` with a periodic update policy — they push data at a fixed interval regardless of whether anything changed. This is the standard approach for counters and gauges.

The **peer state change** xpath is different: it uses `yang-notif-native` with an **on-change** update policy. It fires only when a BGP peer transitions state (e.g., Established → Idle). This is critical for alerting — it tells you the instant a peer goes down or comes back up without polling.

When building the subscription payload for an on-change subscription, omit the `period` field and set `stream` to `"yang-notif-native"`:

```
{
    "subscription-id": 210,
    "base": {
        "stream": "yang-notif-native",
        "encoding": "encode-kvgpb",
        "xpath": "/ios-events-ios-xe-oper:bgp-peer-state-change"
    },
    "mdt-receivers": [
        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
    ]
}
```

Note: there is no `period` field for on-change subscriptions. The device pushes data only when the event occurs.

### Example — Full BGP monitoring suite

This creates all the BGP subscriptions in a single PATCH. Each xpath gets its own subscription ID so they can be managed independently.

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-config-data": {
            "mdt-subscription": [
                {
                    "subscription-id": 201,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/bgp-state-data/neighbors/neighbor/connection",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 202,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/bgp-state-data/neighbors/neighbor/bgp-neighbor-counters",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 203,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/bgp-state-data/neighbors/neighbor/prefix-activity",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 204,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/bgp-state-data/neighbors/neighbor/transport",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 205,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/bgp-state-data/neighbors/neighbor/up-time",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 206,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/bgp-state-data/address-families/address-family/bgp-neighbor-summaries/bgp-neighbor-summary",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 210,
                    "base": {
                        "stream": "yang-notif-native",
                        "encoding": "encode-kvgpb",
                        "xpath": "/ios-events-ios-xe-oper:bgp-peer-state-change"
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                }
            ]
        }
    }
)
```

After creating the subscriptions, always verify and save:

```
iosxe_restconf_get(path="Cisco-IOS-XE-mdt-cfg:mdt-config-data")
iosxe_save_config()
```

### Choosing which BGP subscriptions to deploy

Not every environment needs all seven. Ask the user what they care about:

- **Basic BGP health** — deploy connection state (201) + peer state change event (210). This covers "are my peers up?" and "alert me when one goes down."
- **Performance monitoring** — add neighbor counters (202) + prefix activity (203). This shows update rates and prefix churn.
- **Full BGP observability** — deploy all seven. This gives complete visibility into every aspect of BGP neighbor state.

## WAN Connectivity / IP SLA Telemetry

IP SLA (Service Level Agreement) probes are the primary way IOS-XE measures WAN path performance — round-trip time, jitter, packet loss, and reachability. When the user asks about monitoring WAN links, circuit health, latency, jitter, or path availability, IP SLA telemetry is the answer.

### How IP SLA works

IP SLA operations are configured on the device (outside the scope of this skill — they are typically pre-configured or set up by a network engineer). Each operation has a numeric ID and runs a probe type (ICMP echo, UDP jitter, HTTP, etc.) against a target. The telemetry subscriptions stream the results of those operations.

Before configuring telemetry subscriptions for IP SLA, check whether any SLA operations exist on the device:

```
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/ip/sla")
```

If no operations exist, tell the user: *"There are no IP SLA operations configured on this device. IP SLA telemetry streams the results of existing probes — you or your network engineer need to configure the SLA operations first (e.g., ICMP echo to a remote site, UDP jitter to a WAN peer). Once operations are running, I can set up telemetry to stream their results."*

### Available IP SLA xpaths

| What it captures | xpath | Notes |
|-----------------|-------|-------|
| Total statistics (RTT, jitter, packet loss — aggregated) | `/ip-sla-stats/sla-oper-total-statistics` | Streams results for **all** SLA operations. Best general-purpose path. |
| Per-operation RTT details | `/ip-sla-stats/sla-oper-entry/rtt-info` | Round-trip time breakdowns per operation |
| Latest return code and status | `/ip-sla-stats/sla-oper-entry/latest-return-code` | Success/failure/timeout status per operation |
| Specific operation by ID | `/ip-sla-stats/sla-oper-entry[oper-id='<ID>']/stats` | Filter to a single SLA operation — replace `<ID>` with the operation number |

### Filtering by SLA operation ID

Like interfaces, SLA entries can be filtered by their key. To stream results for only a specific SLA operation:

```
/ip-sla-stats/sla-oper-entry[oper-id='100']/stats
```

Replace `100` with the operation ID. Use this when the device has many SLA operations but the user only cares about specific WAN circuits.

### Example — Stream all IP SLA results

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-config-data": {
            "mdt-subscription": [
                {
                    "subscription-id": 420,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/ip-sla-stats/sla-oper-total-statistics",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                }
            ]
        }
    }
)
```

### Example — Comprehensive WAN monitoring suite

Deploy multiple subscriptions to get full visibility into WAN path performance:

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-mdt-cfg:mdt-config-data",
    payload={
        "Cisco-IOS-XE-mdt-cfg:mdt-config-data": {
            "mdt-subscription": [
                {
                    "subscription-id": 420,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/ip-sla-stats/sla-oper-total-statistics",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 421,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/ip-sla-stats/sla-oper-entry/rtt-info",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                },
                {
                    "subscription-id": 422,
                    "base": {
                        "stream": "yang-push",
                        "encoding": "encode-kvgpb",
                        "xpath": "/ip-sla-stats/sla-oper-entry/latest-return-code",
                        "period": 1500
                    },
                    "mdt-receivers": [
                        {"address": "<RECEIVER_IP>", "port": 57000, "protocol": "grpc-tcp"}
                    ]
                }
            ]
        }
    }
)
```

After creating, verify and save:

```
iosxe_restconf_get(path="Cisco-IOS-XE-mdt-cfg:mdt-config-data")
iosxe_save_config()
```

### Choosing which WAN/SLA subscriptions to deploy

Ask the user what level of WAN visibility they need:

- **Basic WAN health** — deploy total statistics (420) only. This gives RTT, jitter, and packet loss for all SLA operations in a single stream. Sufficient for most dashboards and alerting.
- **Detailed WAN diagnostics** — add RTT info (421) + return codes (422). This adds per-operation RTT breakdowns and success/failure status for troubleshooting specific circuits.
- **Targeted monitoring** — if the user only cares about specific WAN circuits, use the `[oper-id='<ID>']` filter to stream only those operations instead of all of them.

### Combining WAN monitoring with BGP

For full WAN observability, combine IP SLA subscriptions with BGP telemetry. IP SLA tells you about path performance (latency, loss), while BGP tells you about routing state (peer up/down, prefix changes). Together they answer both "is the WAN link healthy?" and "is routing stable?"

## End-to-End Workflow

```
1. Ask the user what they want to monitor
   → Interface stats? CPU? Memory? BGP/OSPF neighbors?
     WAN connectivity / IP SLA? All of the above?

2. Confirm the receiver
   → "Do you have a gRPC telemetry receiver (Telegraf, Cribl, Pipeline)?
      What is its IP and port?"
   → If no receiver exists, stop — MDT requires one.

3. Discover the device
   → iosxe_get_platform_and_yang()

4. Read existing subscriptions
   → iosxe_restconf_get(path="Cisco-IOS-XE-mdt-cfg:mdt-config-data")
   → If subscriptions already exist, show them to the user.
      Ask whether to add new ones alongside or replace existing ones.

5. Build subscription payloads
   → Use the Common XPath Sensors table above to select paths.
   → Assign unique subscription IDs (start at 101 if no existing ones,
      or increment from the highest existing ID).
   → Set the receiver address and port from step 2.

6. Create subscriptions
   → iosxe_restconf_patch(path="Cisco-IOS-XE-mdt-cfg:mdt-config-data",
       payload={...})
   → Use a single PATCH with all subscriptions in one array for efficiency.

7. Verify
   → iosxe_restconf_get(path="Cisco-IOS-XE-mdt-cfg:mdt-config-data")
   → Confirm all subscriptions are present with correct xpaths and receivers.

8. Save config
   → iosxe_save_config()
```
