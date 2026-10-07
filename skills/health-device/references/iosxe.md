# Health visit — IOS-XE GET recipes

The health visit runs `scripts/visit_iosxe.py`. These steps are what
that script implements, and the manual fallback when the command
reports `hai_mcp unavailable`. Topology map: `references/topology.md`.
Tool is `iosxe_restconf_get`. Host and credentials are already on the
MCP server. Pass **`port`** from `inventory/prod.json`
`devices[].access.restconf.port`. Omit `port` and the call hits the CML
UI. Never pass username, password, or a Splunk LAN IP. Never guess a
port.

GET only. Never PUT/PATCH/DELETE, `iosxe_save_config`,
`iosxe_ssh_command`, or `iosxe_get_platform_and_yang`. Do not browse
YANG. Do not call Splunk or ThousandEyes MCP.

Every call below carries a `params={"fields": ...}` filter (a native
dict, not a JSON string). The filter is what keeps the payload small
enough to copy from; **never drop it**. An unfiltered CPU call is 170
KB; filtered it is 5 lines.

## Inventory and scope

1. `read_file` `inventory/prod.json`. Missing file: write `unavailable`
   and stop. Use `access.restconf.host` and `port` as written. Do not
   stop because `expires_at` has passed. Do not guess a port.
2. Candidate set = devices whose `platform` is `iosxe` and that have
   both `access.restconf.host` and `access.restconf.port`. Match names
   case-insensitively; write the `prod.json` spelling everywhere. Do
   not hardcode hostnames or ports in this file.
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
   `devices[].neighbors[]` `local`/`far` (far-end context for notes).
   Missing file: resolve peers from this visit's own interface
   payloads only; notes name no far end. Do not GET CDP or LLDP on a
   health visit.

## Calls (copy these)

**One device at a time.** The five calls for one device share a port
and may be issued in one message. **Never put two ports in one
message** — a response is attributed to the port you passed, and that
is only certain when every call in flight has the same port. Finish
reducing device A's five payloads to rows before device B's first
call.

| # | Keep | Call |
|---|------|------|
| 1 | `boot-time`, `software-version` (the token after `Version ` up to the comma, e.g. `17.15.1a`), `last-reboot-reason`, `reason-severity`, `unsaved-config` | `iosxe_restconf_get(path="Cisco-IOS-XE-device-hardware-oper:device-hardware-data/device-hardware/device-system-data", port=<port>, params={"fields": "boot-time;software-version;last-reboot-reason;reason-severity;unsaved-config"})` |
| 2 | `five-minutes` → `cpu_5m` | `iosxe_restconf_get(path="Cisco-IOS-XE-process-cpu-oper:cpu-usage/cpu-utilization", port=<port>, params={"fields": "five-seconds;one-minute;five-minutes"})` |
| 3 | `used-memory`, `total-memory` → `mem_used_pct` = round(used / total × 100) | `iosxe_restconf_get(path="Cisco-IOS-XE-memory-oper:memory-statistics/memory-statistic=Processor", port=<port>)` |
| 4 | per interface: `name`, `admin-status`, `oper-status`, `last-change`, `ipv4`, `statistics.num-flaps`, `in-crc-errors`, `in-errors`, `in-discards`, `input-security-acl`, `output-security-acl` | `iosxe_restconf_get(path="Cisco-IOS-XE-interfaces-oper:interfaces", port=<port>, params={"fields": "interface(name;admin-status;oper-status;last-change;ipv4;input-security-acl;output-security-acl;statistics(num-flaps;in-crc-errors;in-errors;in-discards))"})` |
| 5 | per neighbor summary: `id`, `as`, `state`, `up-time`, `prefixes-received`. **204 / 404 → the device runs no BGP**: `bgp_not_established` 0, no bgp rows, not a failure | `iosxe_restconf_get(path="Cisco-IOS-XE-bgp-oper:bgp-state-data/address-families", port=<port>, params={"fields": "address-family(afi-safi;vrf-name;bgp-neighbor-summaries/bgp-neighbor-summary(id;as;state;up-time;prefixes-received))"})` |

Follow-up, only when a neighbor summary is not `fsm-established`,
keyed, never the unkeyed list. Cap 3 extra calls per device:
`Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors/neighbor={afi-safi},{vrf-name},{id}`
with `params={"fields": "connection;session-state"}`. Keep
`connection.reset-reason`. Empty `vrf-name` → `default`. A failed
follow-up leaves `reset_reason` null; it does not fail the device.

A call that fails (timeout, connection closed, 5xx) is retried
**once**. A second failure: that device's rows are kept as the board
had them, its metric row is null, coverage `partial`, and you move to
the next device. Do not GET `ietf-interfaces`, `native/interface`,
`acl-oper`, or any path not in this table.

## What to keep from each payload

Read the payload, keep these fields, discard the rest. Live counters
may be strings — coerce to integers. Empty string → null.

**Device row** (one per device, from calls 1–3): `subject` = the
device name, `state` `up`, `last_changed` = `boot-time`,
`software_version`, `last_reboot_reason`, `reason_severity`,
`cpu_5m`, `mem_used_pct`, `unsaved_config`. `keys`:
`[device:<name>]`.

**Interface rows** (call 4, `interface[]`). A board row for
physical, sub-, and Tunnel interfaces whose name is not
`Loopback*`, `Vlan*`, or `Null*` — **including admin-down**.
`name` → `subject`, `admin-status` → `admin_status`, `oper-status` →
`state`, `last-change` → `last_changed` (interface transition time,
not device boot), `num-flaps` → `num_flaps`,
`in-crc-errors` → `in_crc_errors`, `in-errors` → `in_errors`,
`in-discards` → `in_discards`, `input-security-acl` → `input_acl`,
`output-security-acl` → `output_acl`. `intent`: `ok` when admin-up
and oper ready; `failed` when admin-up and oper not ready
(non-idle); `admin_disabled` when admin-down and the subject was
already on the board; `provisioning` when admin-down and the row
is new; `unknown` otherwise. An intended cable is a `prod.json`
`links[]` end on this device. Keep every interface's `ipv4` for
peer resolution (`0.0.0.0` means none); do not write it.

**BGP rows** (call 5, `address-family[].bgp-neighbor-summaries.
bgp-neighbor-summary[]`): `id` → `subject`, `state`, `up-time` →
`up_time` (session uptime, not device uptime), `prefixes-received`
→ `prefixes_received`, `as` → `remote_as`, follow-up
`reset_reason` when collected. `peer`: `device:<name>` when `id`
equals an interface address of a device in `prod.json` — from this
visit's interface payloads or from `topology-observed.json`
`devices[].interfaces[].cidr` (ignore the `/len`); else null. Row
`keys`: this device and the peer device. Expected peers are the
prior board's bgp rows for this device. A missing expected peer is
a vanished row, not a reboot. Forwarding evidence on an
established session is `prefixes_received` plus the connected
interface `intent` `ok`; otherwise impact unknown.

## Diff against the board — what is material

The board is `health/metadata-iosxe.json` `iosxe.current[]`. Match a
collected row to a board row by `name` + `kind` + `subject`. Rows for
devices outside scope are untouched.

Material (one `vs_prior.changed[]` item per field):

| Kind | Field moved |
|------|-------------|
| device | `boot_time` when the boot instant moved **more than 5 seconds** (timestamp correction otherwise). A reboot (`delta` worse, plane degraded) only when that shift is corroborated by `last_reboot_reason` changing, `software_version` changing, an interface `last_changed` at or after the new boot, or a BGP `up_time` that got shorter. Uncorroborated shift: `boot_time` with `delta` `changed`, not a reboot. `software_version`; `cpu_5m` crossed **80** or `mem_used_pct` crossed **85** in either direction; `unsaved_config` boolean flipped (the running/startup text is not collected — no verified GET; `next` says difference unknown) |
| interface | `state`, `admin_status`, `input_acl`, `output_acl`; `num_flaps`, `in_errors`, `in_crc_errors` **increased** over the visit interval (`last_collected_at` → `checked_at`). A drop is a **counter reset** (`delta` `changed`, not better, not degraded). Zero in one snapshot is not historical health. No octet or traffic-rate leaves. |
| bgp | `state`, `peer`; `prefixes_received` changed; `up_time` shorter than the board's (**session re-establishment**, never a device reboot); `reset_reason` when the follow-up returned one |
| any | a row appeared or disappeared (`field` `row`, `prior` or `current` null) |

Not material (update the board, no `changed` item): `cpu_5m` or
`mem_used_pct` moving without crossing the threshold, `in_discards`
(recorded on the row and summed on the metric only), `up_time`
growing, `last_reboot_reason` alone, boot-time skew **within 5
seconds**, `last_changed` alone on an interface, a counter that
did not increase.

`at` on a `changed` item: the interface's `last-change` for `state`
on an interface row; the new `boot-time` for `boot_time`; otherwise
this visit's `checked_at`.

`delta`: `worse` when any item lowered health (a **corroborated**
reboot, left `if-oper-state-ready`/`fsm-established`, a counter
increased, a threshold crossed upward, an ACL unbound, an expected
peer disappeared, a session `up_time` shortened); `better` when
every item raised it; `changed` otherwise (`software_version`, new
row, ACL bound, uncorroborated boot-time shift, counter reset,
`unsaved_config`, admin-down that is not an intended `links[]`
cable); `unchanged` when `changed[]` is empty; `first` when there
was no board.

## Write the lab slip — not the RESTCONF body

Write a stamp only when: no board (first visit), `changed[]` is
non-empty, or `coverage.state` is not `complete`. Otherwise the visit
is quiet: update the board only (`references/watch.md`).

`metrics`: one row per collected device, `scope` `device:<name>`:
`oper_not_ready` (intent `failed`, plus intended `links[]` cables
that are admin-down),
`bgp_not_established` (summaries whose `state` ≠ `fsm-established`,
plus expected prior-board peers that vanished),
`num_flaps`, `in_errors` (in_errors + in_crc_errors), `in_discards`
(sums over that device's board interfaces), `cpu_5m_max`,
`mem_used_pct_max` (the device's own values). Null when not collected.

`readings`: **first visit** — every board row. **Later visits** — only
rows with a `changed` item this visit, plus rows abnormal now (device
over a threshold, oper not ready, BGP not established). Identical
field names and values to the board row.

`note` — only on a row that changed or is abnormal. It is the nurse's
opinion, not the columns again. Name the component, the evidence,
impact or impact unknown, and the next read-only GET from
`needs_note`. Far end comes from `topology-observed.json`
`devices[].neighbors[]` (this interface as `local`, its `far`) when
present. Typical reads: a shorter BGP `up_time` is session
re-establishment, not a router reboot; a flap timed with a
**corroborated** `boot_time` change is the reload, not the cable; a
flap with 0 CRC errors points at the far end; a peer that vanished
with the interface still up is a far-end session loss; errors with
no ACL bound are not policy; admin-down not in `links[]` is
provisioning or administratively disabled, not a failed required
component. Do not repeat addresses or counter values the row
already carries. A healthy unchanged row gets no note.

`unchanged`: board rows not in `readings`. `baseline_ref`:
`health/iosxe/<baseline_visit_id>.json`, null on the first visit.
`concerns`: one device entity-ref per device that rebooted with
corroboration, is over a threshold, has `unsaved_config` true, or
has a non-zero `oper_not_ready` / `bgp_not_established` /
increased errors or flaps.

`headline`: subject, field, prior → current, since when; then the
unchanged count — not "interfaces checked". Do not copy a name from
this skill.

## Plane status

**degraded** when any collected device: rebooted since the board
(`boot_time` moved more than 5 seconds **and** corroborated), **or**
`cpu_5m` ≥ 80 or `mem_used_pct` ≥ 85, **or** has intent `failed`
(or an intended `links[]` cable admin-down), **or** an expected BGP
neighbor is not `fsm-established` or vanished, **or** `num_flaps` /
`in_errors` / `in_crc_errors` **increased** since the board on a
board interface. `in_discards`, `unsaved_config`, a
`software_version` change, boot-time skew within 5 seconds, a
shorter BGP `up_time` while the session is again established, and
a counter reset never degrade on their own. This plane's `status`
is these readings only. GET only — never PUT/PATCH/DELETE,
`iosxe_save_config`, or SSH.

Some devices fail, others succeed → `partial` (board rows for the
failed device kept as they were, its metric row null). All fail or no
PAT → `unknown` / `unavailable`, null facts, never zeros.
