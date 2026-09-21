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
device `scope` `device:<name>`), `readings`, and `vs_prior`.
`readings` is every admin-up interface and every BGP neighbor:
`name` as `inventory/prod.json` writes it, `kind` `interface` or
`bgp`, `subject` the interface name or neighbor `id`, `keys` every
join key that payload contains (`device:<inventory name>` and
`interface:<name>` when the interface is in the payload), `note`
the nurse's opinion (oper state, errors, discards, flaps, or
prefixes, and what moved since the prior stamp), `state`
(`if-oper-state-ready` or `fsm-established` and the other oper
values the device returned), plus `in_errors` / `in_discards` /
`num_flaps` on interfaces and `prefixes_received` on neighbors.
Omit admin-down idle interfaces. Cap 64. The first visit writes
every admin-up interface and every BGP neighbor the GET returned.
`readings` is empty only when that GET returned none. Each `note`
says this is the first visit and the state, errors, discards,
flaps, or prefixes. A later visit diffs those rows. Add `concerns` only when
a metric on that device is non-zero. The stamp has no `devices[]`
tree.

There is no baseline until a prior stamp exists. First visit:
`delta` `first`, `changed` []. Store `readings` anyway. Later
visit: diff `readings` against that prior file by `name` + `kind`
+ `subject`. `changed` lists only what moved: the inventory name,
the interface or neighbor, and the old state to the new state.
`headline` is the opinion across those notes. A sentence that only
says unchanged is not a note: name the state, the errors, and the
prefixes. Do not copy a name from this skill. Keys on
each metric
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
degrade. This plane’s `status` is these readings only. Do not call
ThousandEyes or Splunk.

Some GETs fail, others succeed → `partial`. All fail or no PAT →
`unknown` / `unavailable`, null facts, never zeros.

Headline: device names, oper-not-ready count, BGP states, error/flap
counts — not “interfaces checked.”
