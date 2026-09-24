# Health visit — IOS-XE GET recipes

Use on a **health visit** only. Topology map: `references/topology.md`.
Tool is `iosxe_restconf_get`. Host and credentials are already on the
MCP server. Pass **`port`** from `inventory/prod.json`
`devices[].access.restconf.port`. Omit `port` and the call hits the CML
UI. Never pass username, password, or a Splunk LAN IP. Never guess a
port.

GET only. Never PUT/PATCH/DELETE, `iosxe_save_config`,
`iosxe_ssh_command`, or `iosxe_get_platform_and_yang`. Do not browse
YANG. Do not call Splunk or ThousandEyes MCP.

Do **not** GET `ietf-interfaces:interfaces` or
`Cisco-IOS-XE-native:native/interface` — those are config (enabled, IP,
description). No oper-status, no counters.

## Inventory and scope

1. `read_file` `inventory/prod.json`. Missing or `now >= expires_at`:
   write `unavailable`, ask or stop. Do not guess PAT.
2. Candidate set = devices with both `access.restconf.host` and
   `access.restconf.port`. Match names case-insensitively; write the
   `prod.json` spelling everywhere. Do not hardcode hostnames or
   ports in this file.
3. **Scope.** If the task line has `Scope:` followed by `device:` keys,
   collect only those that are in the candidate set; ignore any other
   name and say so in the reply. No `Scope:` → every candidate, ranked:

| Rank | Evidence |
|------|----------|
| 1 | `role=wan` with `access.restconf.port` |
| 2 | `role=edge` (or HQ/CLOUD/DC in `name`) with RESTCONF |
| 3 | Remaining RESTCONF devices in `prod.json` |

4. `read_file` `inventory/topology-observed.json` if it exists. Keep
   `devices[].name` + `interfaces[].cidr` (peer resolution) and
   `links[]` (far-end context for notes). Missing file: resolve peers
   from this visit's own interface payloads only; notes name no far
   end. Do not GET CDP or LLDP on a health visit.

## Calls (copy these)

Every call: `iosxe_restconf_get(path="<path>", port=<access.restconf.port>)`.
No `fields` filter on address-families (payload is small). Parent 404:
retry the parent container once, then stop YANG-fishing.

Three GETs per device in scope, in this order:

| # | Purpose | Path |
|---|---------|------|
| 1 | Interfaces: oper, counters, ACL bindings, addresses | `Cisco-IOS-XE-interfaces-oper:interfaces` |
| 2 | BGP neighbors (204 or 404 → the device runs no BGP; `bgp_not_established` 0, no bgp rows) | `Cisco-IOS-XE-bgp-oper:bgp-state-data/address-families` |
| 3 | ACLs present and ACE counters | `Cisco-IOS-XE-acl-oper:access-lists` |

Follow-ups, only when needed:

| When | Path |
|------|------|
| One neighbor not `fsm-established` and you need its detail | `Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors/neighbor={afi-safi},{vrf-name},{id}` |
| GET 1 failed | `ietf-interfaces:interfaces-state` once |

Do **not** GET the unkeyed `.../neighbors` list (~37 KB).

**Capability probe.** GET 3 is a probe: HTTP **204**, `404`, or an
empty list means the device has no ACLs. Metric `acls` 0, no acl
rows. Do not degrade, do not retry, do not GET native ACL config, do
not ask.

## What to keep from each payload

Read the payload, keep these fields, discard the rest. Live counters
may be strings — coerce to integers.

**Interfaces** (`interface[]`). A board row only for interfaces with
`admin-status` up whose name is not `Loopback*`, `Vlan*`, or `Null*`.
Fields: `name` → `subject`, `oper-status` → `state`, `last-change` →
`last_changed`, `statistics.in-errors` → `in_errors`, `in-discards` →
`in_discards`, `in-crc-errors` → `in_crc_errors`, `num-flaps` →
`num_flaps`, `rx-kbps` → `rx_kbps`, `tx-kbps` → `tx_kbps`,
`input-security-acl` → `input_acl` (null when absent or empty),
`output-security-acl` → `output_acl`. Keep every interface's `ipv4`
address (including Loopback) in mind for peer resolution; do not write
it.

**BGP** (`address-families[].address-family[].bgp-neighbor-summaries.
bgp-neighbor-summary[]`): `id` → `subject`, `state`, `up-time` →
`up_time`, `prefixes-received` → `prefixes_received`, `as` →
`remote_as`. `peer`: `device:<name>` when `id` equals an interface
address (ignore the `/len`) of a device in `prod.json` — from this
visit's interface payloads or from `topology-observed.json`
`devices[].interfaces[].cidr`; else null. Row `keys`: this device and
the peer device.

**ACLs** (`access-list[]`): `access-list-name` → `subject`,
`ace_count` = length of `access-list-entries.access-list-entry[]`,
`matches_total` = sum of `access-list-entries-oper-data.match-counter`.
`bound_to` = every `interface:<device>/<name>` whose `input_acl` or
`output_acl` equals this name; `state` `bound` when non-empty, else
`unbound`. The oper model does not say permit or deny; do not guess it.
Do not write ACE lists onto any file.

**Mismatch.** An interface whose `input_acl`/`output_acl` names an ACL
the ACL GET did not return is a mismatch: the interface row gets a
`note`, and the device goes on `concerns`. Do not invent an acl row.

## Diff against the board — what is material

The board is `health/metadata-iosxe.json` `iosxe.current[]`. Match a
collected row to a board row by `name` + `kind` + `subject`. Rows for
devices outside scope are untouched.

Material (one `vs_prior.changed[]` item per field):

| Kind | Field moved |
|------|-------------|
| interface | `state`, `input_acl`, `output_acl`; `in_errors`, `in_discards`, `in_crc_errors`, `num_flaps` **increased** |
| bgp | `state`, `peer`; `prefixes_received` changed; `up_time` shorter than the board's (session reset) |
| acl | `bound_to`, `ace_count` changed; `matches_total` moved from 0 (or null) to > 0 — the first hits |
| any | a row appeared or disappeared (`field` `row`, `prior` or `current` null) |

Not material (update the board, no `changed` item): `rx_kbps`,
`tx_kbps`, `up_time` growing, `matches_total` growing after the first
hit, `last_changed` alone.

`at` on a `changed` item: the interface's `last-change` when the field
is `state` on an interface row; otherwise this visit's `checked_at`.

`delta`: `worse` when any item lowered health (left
`if-oper-state-ready`/`fsm-established`, a counter increased, an ACL
was unbound, a peer disappeared); `better` when every item raised it;
`changed` otherwise; `unchanged` when `changed` is empty; `first` when
there was no board.

## Write the lab slip — not the RESTCONF body

Write a stamp only when: no board (first visit), `changed[]` is
non-empty, or `coverage.state` is not `complete`. Otherwise the visit
is quiet: update the board only (`references/watch.md`).

`metrics`: one row per collected device, `scope` `device:<name>`:
`oper_not_ready` (admin-up, oper not ready, non-idle),
`bgp_not_established` (summaries whose `state` ≠ `fsm-established`),
`in_errors`, `in_discards`, `num_flaps` (sums over board rows),
`acls` (ACLs present; 0 on 204). Null when not collected.

`readings`: **first visit** — every board row. **Later visits** — only
rows with a `changed` item this visit, plus rows abnormal now (oper not
ready, BGP not established, a counter that increased, an ACL
mismatch). Identical field names and values to the board row.

`note` — only on a row that changed, is abnormal, or is mismatched.
It is the nurse's opinion, not the columns again: what moved, since
when (`last_changed`), and what the ACL, peer, and far-end columns say
about the cause. Far end comes from `topology-observed.json` `links[]`
when present (for example: drops with no ACL bound are not policy; a
flap with 0 CRC errors points at the far end; a peer that vanished
with the interface still up is a far-end shutdown). Do not repeat
addresses or counter values the row already carries. A healthy
unchanged row gets no note.

`unchanged`: board rows not in `readings`. `baseline_ref`:
`health/iosxe/<baseline_visit_id>.json`, null on the first visit.
`concerns`: one device entity-ref per device with a non-zero metric
(`acls` does not count) or a mismatch.

`headline`: subject, field, prior → current, since when; then the
unchanged count and the ACL probe result — not "interfaces checked".
Do not copy a name from this skill.

## Plane status

**degraded** when any collected device has: admin-up and oper not ready
on a non-idle interface, **or** BGP `state` ≠ `fsm-established`, **or**
`in_errors` / `in_discards` / `num_flaps` increased since the board on
a board interface. ACL 204, zero ACLs, or an ACL mismatch never
degrade (mismatch is a concern, not a fault). This plane's `status` is
these readings only.

Some GETs fail, others succeed → `partial` (board rows for the failed
device are kept as they were, its metric row null). All fail or no PAT
→ `unknown` / `unavailable`, null facts, never zeros.
