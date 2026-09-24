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
   `access.restconf.port`. Match names case-insensitively; write the
   `prod.json` spelling everywhere. Do not hardcode hostnames or
   ports in this file.
3. Rank, then fill remaining budget:

| Rank | Evidence |
|------|----------|
| 1 | `role=wan` with `access.restconf.port` |
| 2 | `role=edge` (or HQ/CLOUD/DC in `name`) with RESTCONF |
| 3 | Remaining RESTCONF devices in `prod.json` |

4. `read_file` `inventory/infra-sot.json` if it exists. Keep only
   `devices[].name` and `devices[].interfaces[].{name,cidr}` in mind;
   they resolve a BGP neighbor address to a device. Missing file: every
   `peer` is null. Do not open ThousandEyes or Splunk files.

## Calls (copy these)

Every call: `iosxe_restconf_get(path="<path>", port=<access.restconf.port>)`.
No `fields` filter on address-families (payload is small). Parent 404:
retry the parent container once, then stop YANG-fishing.

Four GETs per ranked device, in this order:

| # | Purpose | Path |
|---|---------|------|
| 1 | Interfaces: oper, counters, ACL bindings | `Cisco-IOS-XE-interfaces-oper:interfaces` |
| 2 | BGP neighbors (204 or 404 → the device runs no BGP; `bgp_not_established` 0, no bgp rows) | `Cisco-IOS-XE-bgp-oper:bgp-state-data/address-families` |
| 3 | ACLs present and ACE counters | `Cisco-IOS-XE-acl-oper:access-lists` |
| 4 | Physical neighbors | `Cisco-IOS-XE-cdp-oper:cdp-neighbor-details` |

Follow-ups, only when needed:

| When | Path |
|------|------|
| One neighbor not `fsm-established` and you need its detail | `Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors/neighbor={afi-safi},{vrf-name},{id}` |
| GET 4 returned 204 or 404 | `Cisco-IOS-XE-lldp-oper:lldp-entries` once |
| GET 1 failed | `ietf-interfaces:interfaces-state` once |

Do **not** GET the unkeyed `.../neighbors` list (~37 KB).

**Capability probes.** GET 3 and GET 4 are probes: HTTP **204**,
`404`, or an empty list means the platform has none. ACL 204 → one
`acl` board row for that device with `subject` `none`, `present`
`false`, metric `acls` 0. CDP 204 → try LLDP once; both empty →
every `neighbor` on that device stays null. Neither degrades the
plane. Do not retry. Do not GET native ACL config. Do not ask.

## What to keep from each payload

Read the payload, keep these fields, discard the rest. Live counters
may be strings — coerce to integers.

**Interfaces** (`interface[]`, skip `admin-status` down and
`Loopback*`/`Null*`): `name`, `admin-status` → `admin`,
`oper-status` → `oper`, `last-change` → `last_changed`,
`statistics.in-errors` → `in_errors`, `in-discards` → `in_discards`,
`in-crc-errors` → `in_crc_errors`, `num-flaps` → `num_flaps`,
`rx-kbps` → `rx_kbps`, `tx-kbps` → `tx_kbps`,
`input-security-acl` → `input_acl` (null when absent or empty),
`output-security-acl` → `output_acl`.

**BGP** (`address-families[].address-family[].bgp-neighbor-summaries.
bgp-neighbor-summary[]`): `id` → `subject`, `state`, `up-time` →
`up_time`, `prefixes-received` → `prefixes_received`, `as` →
`remote_as`. `peer`: if `id` equals the address part of any
`infra-sot` `interfaces[].cidr` (ignore the `/len`), `device:<that
device's name>`; else null.

**ACLs** (`access-list[]`): `access-list-name` → `subject`,
`ace_count` = length of `access-list-entries.access-list-entry[]`,
`matches_total` = sum of `access-list-entries-oper-data.match-counter`.
`bound_to` = every `interface:<device>/<name>` whose `input_acl` or
`output_acl` equals this name. The oper model does not say permit or
deny; do not guess it. Do not write ACE lists onto any file.

**CDP** (`cdp-neighbor-detail[]`): `local-intf-name` is the local
interface; `device-name` minus any domain suffix, matched
case-insensitively to a `prod.json` name, is the neighbor device;
`port-id` its port. When it matches: interface row `neighbor` =
`interface:<neighbor prod.json name>/<port-id>` and a board relation
`{from: interface:<this device>/<local-intf-name>, to: that neighbor,
rel: connected_to, basis: observed, evidence_ref:
"Cisco-IOS-XE-cdp-oper:cdp-neighbor-details on device:<this device>"}`.
No match (a host, an agent VM, an unknown name): `neighbor` null, no
relation. LLDP fallback: `device-id` / `local-interface` / `port-id`
the same way. A resolved `peer` adds `{from: device:<this device>, to:
<peer>, rel: peers_with, basis: observed, evidence_ref:
"Cisco-IOS-XE-bgp-oper:bgp-state-data on device:<this device>"}`.

Write each edge once per direction it was seen; the compiler merges.

## Diff against the board — what is material

The board is `health/metadata-iosxe.json` `iosxe.current[]`. Match a
collected row to a board row by `device` + `kind` + `subject`.

Material (one `vs_prior.changed[]` item per field):

| Kind | Field moved |
|------|-------------|
| interface | `oper`, `admin`, `input_acl`, `output_acl`, `neighbor`; `in_errors`, `in_discards`, `in_crc_errors`, `num_flaps` **increased** |
| bgp | `state`, `peer`; `prefixes_received` changed; `up_time` shorter than the board's (session reset) |
| acl | row appeared or disappeared (`field` `row`); `present`, `bound_to`, `ace_count` changed; `matches_total` moved from 0 (or null) to > 0 — the first hits |
| any | a row appeared or disappeared (`field` `row`, `prior` or `current` null) |

Not material (update the board, no `changed` item): `rx_kbps`,
`tx_kbps`, `up_time` growing, `matches_total` growing after the
first hit, `last_changed` alone.

`at` on a `changed` item: the interface's `last-change` when the field
is `oper` or `admin`; otherwise this visit's `checked_at`.

`delta`: `worse` when any item lowered health (left
`if-oper-state-ready`/`fsm-established`, a counter increased, an ACL
was unbound, a neighbor or peer disappeared); `better` when every item
raised it; `changed` otherwise; `unchanged` when `changed` is empty;
`first` when there was no board.

## Write the lab slip — not the RESTCONF body

Write a stamp only when: no board (first visit), `changed[]` is
non-empty, or `coverage.state` is not `complete`. Otherwise the visit
is quiet: update the board only (`references/watch.md`).

`metrics`: one row per collected device, `scope` `device:<name>`:
`oper_not_ready` (admin-up, oper not ready, non-idle),
`bgp_not_established` (summaries whose `state` ≠ `fsm-established`),
`in_errors`, `in_discards`, `num_flaps` (sums over admin-up ports),
`acls` (ACLs present; 0 on 204). Null when not collected.

`readings`: **first visit** — every admin-up interface, every BGP
neighbor, every ACL (and the `present: false` row per 204 device).
**Later visits** — only rows with a `changed` item this visit, plus
rows abnormal now (oper not ready, BGP not established, a counter that
increased). Same `keys` as the board row. `note` is the nurse's
opinion: what the row shows, what moved, since when (`last_changed`),
and what the neighbor/peer/ACL columns say about the cause (for
example: drops with no ACL bound are not policy; a flap with 0 CRC
errors points at the far end; a neighbor that vanished with the
interface still up is a far-end shutdown). A note that only says
unchanged is not a note.

`unchanged`: board rows not in `readings`. `baseline_ref`:
`health/iosxe/<baseline_visit_id>.json`, null on the first visit.
`relations`: edges not present on the prior board. `concerns`: one
device entity-ref per device with a non-zero metric.

`headline`: subject, field, prior → current, since when; then the
unchanged count and the ACL/CDP probe result — not "interfaces
checked". Do not copy a name from this skill.

## Plane status

**degraded** when any collected device has: admin-up and oper not ready
on a non-idle interface, **or** BGP `state` ≠ `fsm-established`, **or**
`in_errors` / `in_discards` / `num_flaps` increased since the board on
a ranked up interface. Idle shutdown ports do not count. ACL 204, zero
ACLs, or no CDP neighbors never degrade. This plane's `status` is these
readings only.

Some GETs fail, others succeed → `partial` (board rows for the failed
device are kept as they were, its metric row null). All fail or no PAT
→ `unknown` / `unavailable`, null facts, never zeros.
