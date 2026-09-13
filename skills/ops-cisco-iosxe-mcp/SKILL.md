---
name: cisco-iosxe-mcp
version: "1.2"
description: "v1.2 — Manage Cisco IOS-XE devices via RESTCONF MCP tools — read and modify configuration using YANG paths, save configuration, troubleshoot operational state (BGP, IS-IS, CDP, ARP, ACL). SoT/NetBox twin: GET only, then ops-netbox-mcp. Includes CML PAT/C8000V write recipes. Use when the user asks about IOS-XE configuration, RESTCONF, YANG, interfaces, routing, BGP/IS-IS, ACLs, hostname, telemetry, syslog, or live reads for a NetBox source of truth."
---

# Cisco IOS-XE MCP Server (v1.2)

An MCP tool server for managing Cisco IOS-XE devices exclusively via the RESTCONF API.

## !!!!! SSH PROHIBITION !!!!!

**NEVER use `iosxe_ssh_command` unless the RESTCONF API is not running on the device.**

- **DO NOT** use SSH for show commands (`show logging`, `show running-config`, `show ip interface brief`, etc.)
- **DO NOT** use SSH for configuration changes
- **DO NOT** use SSH for verification or troubleshooting
- **DO NOT** use SSH to save configuration — use `iosxe_save_config` instead
- **DO NOT** use SSH as a fallback when a RESTCONF call returns unexpected data — try a different YANG path or ask the user instead

`iosxe_ssh_command` is permitted for **ONE operation only**: enabling the RESTCONF API when it is confirmed to not be running (connection refused). Before using SSH, ask the user: *"The RESTCONF API is not responding. Should I SSH in to enable it? What SSH port should I use? (default: 22)"*

Any other use of `iosxe_ssh_command` is FORBIDDEN.

Registered names and required args: [references/tools.md](references/tools.md).

## Available Tools

| Tool | Purpose | When to use |
|------|---------|-------------|
| `iosxe_restconf_get` | Read configuration or operational state by YANG path | ALL reads, ALL verification, ALL troubleshooting |
| `iosxe_restconf_put` | Replace an entire configuration resource by YANG path | **Change/replace** existing config (overwrites) |
| `iosxe_restconf_patch` | Merge additional fields into a configuration resource | **Add** new entries to existing config (merges) |
| `iosxe_restconf_delete` | Remove a configuration resource entirely | Resource removal |
| `iosxe_get_platform_and_yang` | Discover device platform info, version, fetch YANG models | Device discovery |
| `iosxe_save_config` | Save running config to NVRAM (write memory) | After ANY config change |
| `iosxe_ssh_command` | SSH CLI (RESTRICTED) | ONLY to enable the RESTCONF API — nothing else |

## GitOps (estate running-config)

Day-two device config is **Network Ops** via git (`github_put_file`
`ref=dev`), not RESTCONF write. `iosxe_restconf_put` / `patch` /
`delete` and `iosxe_save_config` are not the change path for this
fleet. Health Device and NetBox SoT stay GET-only as below.



When the user wants to **build / populate / refresh the NetBox SoT or digital twin** from live boxes:

1. Host/port from `inventory/prod.json` `access.restconf` — never guess.
2. Follow **ops-netbox-mcp** [populate.md](../ops-netbox-mcp/references/populate.md)
   for whether GET is required (matching `infra-sot.json` seed and no
   `refresh` → skip GET).
3. When GET is required, **call `iosxe_restconf_get`** for every simulate
   IOS-XE node with restconf:
   - interfaces: `Cisco-IOS-XE-native:native/interface`
   - cables (second pass): `Cisco-IOS-XE-cdp-oper:cdp-neighbor-details`
4. Map GET rows to NetBox bodies. Use snap ids on update. One cable →
   `netbox_manage`. Many interfaces/IPs/cables → **`netbox_bulk`**.
5. **Do not** `iosxe_restconf_put` / `patch` / `delete`, `iosxe_save_config`, or `iosxe_ssh_command`. SoT writes go to NetBox, not the device.

Interface/BGP write recipes in this skill do **not** apply to SoT builds.

## Standard Workflow

1. **Discover the device** — `iosxe_get_platform_and_yang`
2. If discovery fails (RESTCONF not running) — ask the user to confirm SSH bootstrap (see prohibition above)
3. **Look up the YANG model** — `iosxe_get_platform_and_yang(yang_model="Cisco-IOS-XE-native")`
4. **Read current config** — `iosxe_restconf_get` with the appropriate YANG path
5. **Make changes** — choose the right method:
   - **Adding** new entries (e.g. add a syslog host, add an NTP server) → `iosxe_restconf_patch` (merges into existing config)
   - **Changing/replacing** existing entries (e.g. change syslog host from X to Y, replace an interface config) → `iosxe_restconf_put` (overwrites the resource entirely)
   - **Removing** entries → `iosxe_restconf_delete`
6. **Verify** — `iosxe_restconf_get` to confirm the change (NEVER use SSH for verification)
7. **Save config** — `iosxe_save_config()` (NEVER use SSH for this)

## RESTCONF Path Convention

All RESTCONF data tool paths are appended to `/restconf/data/` automatically. Only provide the YANG-qualified resource path.

### Common YANG Paths

| Path | What it returns |
|------|-----------------|
| `Cisco-IOS-XE-native:native/hostname` | Device hostname |
| `Cisco-IOS-XE-native:native/interface` | All interfaces |
| `Cisco-IOS-XE-native:native/interface/Loopback=0` | Loopback0 specifically |
| `Cisco-IOS-XE-native:native/router` | All routing configuration |
| `Cisco-IOS-XE-native:native/ip/access-list` | ACLs |
| `Cisco-IOS-XE-native:native/ip/route` | Static routes |
| `Cisco-IOS-XE-native:native/logging` | Logging/syslog configuration |
| `Cisco-IOS-XE-native:native/ntp` | NTP configuration |
| `Cisco-IOS-XE-native:native/snmp-server` | SNMP configuration |
| `Cisco-IOS-XE-mdt-cfg:mdt-config-data` | Model-driven telemetry subscriptions |
| `ietf-interfaces:interfaces` | IETF interfaces model |

Use `=<key>` for specific list entries. URL-encode slashes as `%2F` (e.g. `GigabitEthernet=1%2F0%2F1`).

**Avoid drilling into leaf sub-paths for GET requests.** Many individual leaves (e.g., `logging/facility`, `logging/trap`, `ntp/server`) may not exist on the device if they haven't been configured, and will return a 404. Instead, read the **parent container** (e.g., `logging`, `ntp`) and inspect the response to find the data you need.

## CRITICAL: PUT vs PATCH

| User intent | Method | Behavior |
|-------------|--------|----------|
| "**Add** a syslog server" | `PATCH` | Merges — existing entries are preserved, new entry is added |
| "**Change** syslog server from X to Y" | `PUT` | Replaces — the entire resource is overwritten with the new value |
| "**Replace** the NTP config" | `PUT` | Replaces — old config is gone, only new payload remains |
| "**Add** an NTP server" | `PATCH` | Merges — existing NTP servers stay, new one is added |
| "**Update** the interface description" | `PATCH` | Merges — only the description field changes, everything else untouched |

**Key rule:** If the user says "change", "replace", "switch", or "set ... to", use `PUT`. If the user says "add", "also", "additionally", or "include", use `PATCH`. When in doubt, read the current config with `GET` first to understand what exists, then choose accordingly.

## Get the PAT port before connecting — never guess it

Devices sit behind PAT ports on the CML controller, not port 443. Ports are
reassigned whenever a lab is rebuilt, so a port from earlier in the conversation,
from the other lab, or from a previous session is wrong. Use `api_port` for
RESTCONF and `ssh_port` only for the one permitted SSH case.

Three ways to get it, in order of preference:

1. **Workspace inventory** — `inventory/prod.yaml` or `inventory/dev.yaml`
   (`access.host`, `access.restconf_port`) or the derived json. Paths in
   `workspace-handoff`. Do not use `lab-access.json`.
2. **CML MCP** — lab nodes and PAT ports when inventory is missing or stale.
   Confirm which lab: Prod and Dev have different ports for the same hostname.
3. **GitHub MCP** — `get_file_contents` on a committed inventory file.

Note that `inventory/runtime/` is **not** in git. Do not try to fetch a seed file
from there; it only exists on the CI runner.

If none of the three gives you a port for the host, say so and stop. Do not
substitute a nearby port — a wrong port either fails to connect or configures the
wrong device.

## CML PAT / C8000V — do this, not YANG fishing

When configuring interfaces or BGP on CML-backed devices (PAT port on the controller):

1. **Read the WRITE RECIPE first** in [reference/interfaces.md](reference/interfaces.md) and [reference/bgp.md](reference/bgp.md).
2. **Interface writes:** PATCH `Cisco-IOS-XE-native:native/interface` with `GigabitEthernet: [{ "name": "N", ... }]`. Never PATCH keyed `GigabitEthernet=N` with a repeating list key in the body. Omit CDP from the payload. `no shutdown` = DELETE `.../GigabitEthernet=N/shutdown`.
3. **BGP writes:** PATCH `Cisco-IOS-XE-native:native` wrapping `router` / `Cisco-IOS-XE-bgp:bgp`. Keyed write paths (`bgp=65000`, `neighbor=x`) often return `unknown-element` on this lab even when GET works.
4. On `unknown-element` / `Internal error` for writes: **retry the native-parent recipe once**. Do **not** call `iosxe_get_platform_and_yang` or browse YANG models to invent a new shape.

## Interface Management Decision Tree

When the user asks about interfaces — shutdown, no shutdown, bouncing, IP addressing, VRF, descriptions, creating loopbacks/SVIs, or any interface configuration — read [reference/interfaces.md](reference/interfaces.md) and follow the workflows there (WRITE RECIPE first on CML).

Key points:
- **Shutdown** = PATCH with `"shutdown": [null]` on parent `.../interface`
- **No shutdown** = DELETE the `/shutdown` leaf from the interface path
- **Bounce** = shutdown then no-shutdown (two operations in sequence)
- **IP address / description / VRF / MTU** = PATCH on the parent interface container (not keyed Gi=N for the PATCH path)
- **Create loopback or Vlan SVI** = PUT on the specific interface path
- **Delete loopback or Vlan SVI** = DELETE on the specific interface path
- **Physical interfaces cannot be deleted** — only modified or shut down
- **Omit CDP** from interface PATCH payloads on CML C8000V

Always verify with a GET after changes and save with `iosxe_save_config()`.

## Operational Troubleshooting

When the user asks to **troubleshoot**, **verify**, or **inspect live state** (BGP peers, CDP neighbors, ARP table, "show" equivalents) — read [reference/operational.md](reference/operational.md). Operational reads use GET only on `-oper` YANG models. Do not use SSH.

For BGP **configuration** changes, read [reference/bgp.md](reference/bgp.md) instead (WRITE RECIPE first on CML).

**Critical safety rules (BGP configuration only):**
- **ONLY use PATCH** for adding BGP neighbors, networks, and address-family entries. PATCH merges — existing config is preserved.
- **NEVER use PUT** on any BGP path. PUT replaces the entire resource — this will wipe out all existing neighbors, networks, and address-family entries.
- **NEVER use DELETE** on broad BGP paths (`router/bgp`, `router/bgp=<AS>`, `address-family`). Only DELETE specific, targeted resources (a single neighbor, a single network statement) when the user explicitly asks.
- **ALWAYS read the current BGP config** with a GET before making any change.
- **ALWAYS verify** with a GET after the change and save with `iosxe_save_config()`.
- **CML C8000V:** write via PATCH `Cisco-IOS-XE-native:native` (see bgp.md recipe). Do not PUT keyed neighbor paths.

## Visibility / Telemetry Decision Tree

When the user asks about visibility, monitoring, observability, or telemetry on an IOS-XE device, determine which method they need before proceeding.

**Step 1 — Ask the user:**
> "Do you want **syslog** (log messages forwarded to a collector) or **model-driven telemetry** (structured gRPC streams of operational data like interface stats, CPU, memory)?"

**Step 2 — Branch on the answer:**

- **Syslog** → Read [reference/syslog.md](reference/syslog.md). Ask the user for the syslog collector IP (or discover it from a Splunk MCP connector if available). Follow the syslog workflow in that reference.

- **Model-driven telemetry (MDT)** → Read [reference/mdt-telemetry.md](reference/mdt-telemetry.md). Tell the user: *"Model-driven telemetry streams use gRPC. You need a receiver that can decode gRPC telemetry — for example Telegraf (with the cisco_telemetry_mdt input plugin), Cribl, Pipeline, or any gRPC-capable collector. Do you have one of these? If so, what is its IP address and port?"* Then follow the MDT workflow in that reference.

Do NOT read both references — only load the one the user needs, to keep the context window small.

## Credential Resolution

Priority: **tool arguments > HTTP headers > environment variables**.

| Source | Host | Port | Username | Password |
|--------|------|------|----------|----------|
| Tool argument | `host` | `port` | `username` | `password` |
| HTTP header | `X-IOSXE-HOST` | `X-IOSXE-PORT` | `X-IOSXE-USERNAME` | `X-IOSXE-PASSWORD` |
| Environment var | `IOSXE_HOST` | `IOSXE_PORT` | `IOSXE_USERNAME` | `IOSXE_PASSWORD` |

Host accepts bare IPs, `host:port`, or full URLs. The library default is 443, but
on this lab every device is behind a CML PAT port — always pass the `api_port`
from `resolve_port.py`. HTTPS-first with HTTP fallback.

## Response Format

All tools return `{"ok": True/False, ...}`. On failure, `"error"` contains the message. RESTCONF responses include `status_code`, `method`, `path`, and `data`.

## Reference

Detailed documentation is in the `reference/` directory. Read these when you need specifics:

- [reference/tool-parameters.md](reference/tool-parameters.md) — Full parameter tables for every tool
- [reference/examples.md](reference/examples.md) — Practical usage examples (all RESTCONF-based)
- [reference/interfaces.md](reference/interfaces.md) — Interface management: shutdown/no-shutdown, IP addressing, VRF, descriptions, loopback/SVI creation, MTU, speed/duplex
- [reference/bgp.md](reference/bgp.md) — BGP configuration: neighbors, address-families, network statements, redistribution (PATCH-only, never PUT)
- [reference/wan-peer-recipe.md](reference/wan-peer-recipe.md) — end-to-end sequence for adding a branch spoke to an existing WAN hub: /30 interface, eBGP neighbor, activation, verify
- [reference/operational.md](reference/operational.md) — Operational troubleshooting: BGP, IS-IS, CDP, ARP, ACL hit counters (GET-only)
- [reference/syslog.md](reference/syslog.md) — Syslog configuration, collector discovery (Splunk integration), end-to-end syslog workflows
- [reference/mdt-telemetry.md](reference/mdt-telemetry.md) — Model-driven telemetry (gRPC dial-out subscriptions via Cisco-IOS-XE-mdt-cfg)
