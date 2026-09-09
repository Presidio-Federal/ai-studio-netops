# Cisco IOS-XE Syslog Configuration

This document covers configuring IOS-XE devices to forward syslog messages to a collector via RESTCONF.

For model-driven telemetry (gRPC streams), see [mdt-telemetry.md](mdt-telemetry.md) instead.

All configuration MUST use RESTCONF tools. Do not use SSH for syslog configuration.

## Collector Discovery

Before configuring syslog on the device, attempt to discover the collector's IP/hostname from other available MCP tools. This avoids asking the user for information the platform already knows.

### Discovery Priority

1. **Check for a Splunk MCP connector** — if `splunk_get_server_info` is available, call it. The `server_name` or the host configured via `SPLUNK_HOST` / `X-SPLUNK-HOST` is the collector IP. The default syslog receive port in Splunk is **UDP 514** (configured as a `udp` input on the Splunk side).
2. **Check for other collector connectors** — as new connectors come online (e.g., Elastic, Graylog, SolarWinds), follow the same pattern: call the server info tool to resolve the collector address.
3. **Fall back to the user** — if no collector connector is available, ask the user for the collector IP and port.

### Splunk Discovery Example

```
# Step 1: Verify Splunk is reachable and get its address
splunk_get_server_info()
→ Response includes server_name / host info

# Step 2: Check if a syslog input already exists on the target port
splunk_get_inputs(kind="udp")
→ Look for an existing UDP 514 listener

# Step 3: If no syslog input exists, create one
# (This requires the Splunk MCP connector — see splunk-mcp skill)
```

The resolved Splunk host becomes the syslog destination IP on the IOS-XE device.

## Syslog Configuration

### Read Current Logging Config

Always read the **full logging container** first. Do NOT drill into sub-paths like `logging/facility`, `logging/host`, or `logging/trap` directly — these leaves may not exist on the device and will return 404. Read the parent container and inspect the response:

```
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/logging")
```

The response includes all configured logging sub-elements (host, trap, source-interface, facility, etc.) in a single object. Extract what you need from the response rather than making separate GET calls to individual sub-paths.

### Add a Syslog Destination (no existing syslog host)

Use PATCH to **add** a new syslog host. PATCH merges into existing config — existing entries are preserved.

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/logging",
    payload={
        "Cisco-IOS-XE-native:logging": {
            "host": {
                "ipv4-host-list": [
                    {"ipv4-host": "<COLLECTOR_IP>"}
                ]
            }
        }
    }
)
```

### Add a Syslog Destination with a Custom Port

When the collector listens on a non-default port (anything other than UDP 514), use `ipv4-host-transport-list` instead of `ipv4-host-list`. The `port` field is a leaf-list — pass it as a plain JSON array of integers.

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/logging",
    payload={
        "Cisco-IOS-XE-native:logging": {
            "host": {
                "ipv4-host-transport-list": [
                    {
                        "ipv4-host": "<COLLECTOR_IP>",
                        "transport": {
                            "udp": {
                                "port": [<PORT_NUMBER>]
                            }
                        }
                    }
                ]
            }
        }
    }
)
```

**Important:** `ipv4-host-list` and `ipv4-host-transport-list` are separate YANG lists. If an existing `ipv4-host-list` entry already exists for the same IP, the device will reject the transport-list entry because the host is already defined in the other list. In that case, delete the existing host entry first, then re-apply with the transport list:

```
# Step 1: Remove the existing default-port entry
iosxe_restconf_delete(path="Cisco-IOS-XE-native:native/logging/host")

# Step 2: Re-apply with custom port
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/logging",
    payload={
        "Cisco-IOS-XE-native:logging": {
            "host": {
                "ipv4-host-transport-list": [
                    {
                        "ipv4-host": "<COLLECTOR_IP>",
                        "transport": {
                            "udp": {
                                "port": [<PORT_NUMBER>]
                            }
                        }
                    }
                ]
            }
        }
    }
)
```

**Which list to use:**

| Collector port | YANG list | Notes |
|---------------|-----------|-------|
| UDP 514 (default) | `ipv4-host-list` | Simpler payload, no transport block needed |
| Any other port | `ipv4-host-transport-list` | Must include `transport.udp.port` array |

Always ask the user what port the collector is listening on. If they don't know, default to UDP 514 and use `ipv4-host-list`.

### Change/Replace a Syslog Destination (existing host → new host)

Use PUT to **replace** the logging host config. PUT overwrites the entire resource at that path — the old syslog host is removed and only the new one remains.

```
iosxe_restconf_put(
    path="Cisco-IOS-XE-native:native/logging",
    payload={
        "Cisco-IOS-XE-native:logging": {
            "host": {
                "ipv4-host-list": [
                    {"ipv4-host": "<NEW_COLLECTOR_IP>"}
                ]
            }
        }
    }
)
```

Replace `<COLLECTOR_IP>` / `<NEW_COLLECTOR_IP>` with the address discovered from the collector connector or provided by the user.

### Set Syslog Severity Level

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/logging",
    payload={
        "Cisco-IOS-XE-native:logging": {
            "trap": {
                "severity": "informational"
            }
        }
    }
)
```

Severity levels (most to least verbose): `debugging` (7), `informational` (6), `notifications` (5), `warnings` (4), `errors` (3), `critical` (2), `alerts` (1), `emergencies` (0).

### Set Logging Source Interface

Best practice: use a Loopback so syslog messages have a stable source IP regardless of which physical interface is used to reach the collector.

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/logging",
    payload={
        "Cisco-IOS-XE-native:logging": {
            "source-interface": {
                "interface-name": "Loopback0"
            }
        }
    }
)
```

### Enable Timestamps on Syslog Messages

```
iosxe_restconf_patch(
    path="Cisco-IOS-XE-native:native/service",
    payload={
        "Cisco-IOS-XE-native:service": {
            "timestamps": {
                "log": {
                    "datetime": {
                        "msec": [null],
                        "localtime": [null],
                        "show-timezone": [null]
                    }
                }
            }
        }
    }
)
```

### Verify Syslog is Working

```
# On the IOS-XE device — read logging config to confirm the host is set
iosxe_restconf_get(path="Cisco-IOS-XE-native:native/logging")

# On Splunk (if available) — search for events from this device
splunk_search(
    query="index=* host=<DEVICE_HOSTNAME_OR_IP> sourcetype=syslog | head 10",
    earliest_time="-15m"
)
```

## End-to-End: Syslog to Splunk Workflow

Complete workflow for wiring an IOS-XE device's syslog to a Splunk collector:

```
1. Discover the collector
   → splunk_get_server_info()
   → Extract the Splunk host IP (this is the syslog destination)

2. Verify Splunk has a syslog listener
   → splunk_get_inputs(kind="udp")
   → Confirm UDP 514 input exists, or note the correct port

3. Ensure a Splunk index exists for the data
   → splunk_get_indexes()
   → splunk_create_index(name="network_syslog") if needed

4. Discover the IOS-XE device
   → iosxe_get_platform_and_yang()

5. Read current logging config
   → iosxe_restconf_get(path="Cisco-IOS-XE-native:native/logging")
   → Check if a syslog host already exists

6. Configure syslog destination on the device
   Choose the right payload based on the collector port:

   DEFAULT PORT (UDP 514) — use ipv4-host-list:
   → iosxe_restconf_patch(path="Cisco-IOS-XE-native:native/logging", payload={
         "Cisco-IOS-XE-native:logging": {
             "host": {"ipv4-host-list": [{"ipv4-host": "<SPLUNK_IP>"}]},
             "trap": {"severity": "informational"},
             "source-interface": {"interface-name": "Loopback0"}
         }
     })

   CUSTOM PORT — use ipv4-host-transport-list:
   → iosxe_restconf_patch(path="Cisco-IOS-XE-native:native/logging", payload={
         "Cisco-IOS-XE-native:logging": {
             "host": {"ipv4-host-transport-list": [
                 {"ipv4-host": "<SPLUNK_IP>", "transport": {"udp": {"port": [<PORT>]}}}
             ]},
             "trap": {"severity": "informational"},
             "source-interface": {"interface-name": "Loopback0"}
         }
     })

   If REPLACING an existing syslog host → DELETE the host container first,
   then PATCH with the correct list (default or custom port):
   → iosxe_restconf_delete(path="Cisco-IOS-XE-native:native/logging/host")
   → iosxe_restconf_patch(...with the appropriate payload above...)

7. Save the device config
   → iosxe_save_config()

8. Verify end-to-end
   → iosxe_restconf_get(path="Cisco-IOS-XE-native:native/logging")
   → splunk_search(query="index=network_syslog | head 5", earliest_time="-5m")
```
