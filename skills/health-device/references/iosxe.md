# Named IOS-XE visit — GET recipes

Use on an **IOS-XE visit** only. Tool is `iosxe_restconf_get`. Host and
credentials are already on the MCP server. Pass **`port`** from
`inventory/prod.json` `devices[].access.restconf.port`. Omit `port` and
the call hits the CML UI. Never pass username, password, or a Splunk
LAN IP. Never guess a port.

GET only. Never PUT/PATCH/DELETE, `iosxe_save_config`,
`iosxe_ssh_command`, or `iosxe_get_platform_and_yang`. Do not browse
YANG. Do not call Splunk or ThousandEyes MCP.

Do **not** GET `ietf-interfaces:interfaces` or
`Cisco-IOS-XE-native:native/interface` — those are config (enabled, IP,
description). No oper-status, no counters.

## Inventory

1. `read_file` `inventory/prod.json`. Missing or `now >= expires_at`:
   write `unavailable`, ask or stop. Do not guess PAT.
2. Candidate set = devices with both `access.restconf.host` and
   `access.restconf.port` (wan + edge; more than two). Match names
   case-insensitively. Do not hardcode hostnames or ports in this file.
3. Rank wan/edge with RESTCONF, then fill remaining budget:

| Rank | Evidence |
|------|----------|
| 1 | `role=wan` with `access.restconf.port` |
| 2 | `role=edge` (or HQ/CLOUD/DC in `name`) with RESTCONF |
| 3 | Remaining RESTCONF devices in `prod.json` |

Do not open ThousandEyes or Splunk files. Missing `prod.json`: skip
all GETs.

## Calls (copy these)

Every call: `iosxe_restconf_get(path="<path>", port=<access.restconf.port>)`.
No `fields` filter on address-families (payload is small). Parent 404:
retry the parent container once, then stop YANG-fishing.

| Why ranked | Path |
|------------|------|
| Baseline + TE / LINK / path | `Cisco-IOS-XE-interfaces-oper:interfaces` |
| `role=wan` or BGP mnemonic | `Cisco-IOS-XE-bgp-oper:bgp-state-data/address-families` |
| One unhealthy or implicated peer | `Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors/neighbor={afi-safi},{vrf-name},{id}` |
| Drops on a ranked up interface | `Cisco-IOS-XE-acl-oper:access-lists` — **only then** |
| Oper GET failed | one fallback `ietf-interfaces:interfaces-state` |

Do **not** GET the unkeyed `.../neighbors` list (~37 KB).

**ACL is follow-up, not baseline.** Skip `access-lists` unless a ranked
**up** interface shows traffic being dropped (`in_discards`,
`in_errors`, or `out_errors` > 0 after the oper GET). No drops → do
not look for ACLs. HTTP **204** (empty) = no ACLs on that box; write
`acls.count` 0, do not GET native ACL config, do not degrade. Omit
`acls` entirely when you did not run the GET.

## Write the lab slip — not the RESTCONF body

Map oper enums to counts (`if-state-up` / `if-oper-state-ready`
→ ready). IETF fallback uses `admin-status` / `oper-status`
`up`/`down`.

Write `headline`, `coverage`, `metrics` (one row per collected
device `scope` `device:<name>`), `vs_prior`. Do **not** write
`devices[]` interface, BGP, or ACL trees. Keys on each metric
row: `oper_not_ready`, `bgp_not_established`, `in_errors`,
`in_discards`, `num_flaps`. Null when that device was not
collected.

Count **oper_not_ready** from admin-up / oper-not-ready (non-idle).
Count **bgp_not_established** from `bgp-neighbor-summary` whose
`state` is not `fsm-established`. Sum errors/flaps from ranked up
ports (skip idle shutdown). Live counters may be strings — coerce
to numbers for the metric row.

ACL GET is follow-up evidence for `headline` only (drops already
set `in_discards` / `in_errors`). Do not dump ACE lists onto the
stamp.

## Plane status

**degraded** when any collected device has: admin-up and oper not ready
on a non-idle interface, **or** BGP `state` ≠ `fsm-established`, **or**
`in_errors` / `out_errors` / `num_flaps` > 0 on a ranked up interface.
Idle shutdown ports do not count. Missing `acls` or count 0 does not
degrade.

TE loss with all ranked ports ready and errors/flaps 0: this **plane**
may be `ok` (no local L1/L2 fault). The **board** stays degraded if TE
is. Do not call ThousandEyes or Splunk.

Some GETs fail, others succeed → `partial`. All fail or no PAT →
`unknown` / `unavailable`, null facts, never zeros.

Headline: device names, oper-not-ready count, BGP states, error/flap
counts — not “interfaces checked.”
