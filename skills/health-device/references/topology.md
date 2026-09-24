# Topology map — observed physical topology

Use only when the task line names the **network topology map**
(`Run the network topology map only.`). It is not a health visit: no
counters, no BGP, no ACL, no stamp, no board write. One file:
`inventory/topology-observed.json` (schema
`schemas/topology-iosxe.schema.json`, example
`examples/topology-observed.example.json`).

You are a recorder, not an analyst. Each device tells you three things
— its version, its interfaces, its neighbors — and you write down what
it said. You never compare two devices' reports, never decide which
one is right, never read a description, never look at an address to
work out who is cabled to whom. A reader does the pairing later.

## Rules that make this work on the first try

1. **One device at a time.** Finish device A completely — three
   calls, reduce, write the file — before the first call to device B.
2. **Never two ports in one message.** The three calls for one
   device share a port and may go in one message; a call for another
   port may not. A response is attributed to the port you passed, and
   that is only certain when every call in flight has the same port.
3. **Write after every device.** The file on disk is your memory. Do
   not hold nine devices in your head.
4. **Copy, do not reason.** A CDP row becomes a `neighbors[]` row
   with the fields renamed. That is the whole job.
5. **One retry, then move on.** A failed call is retried once. If it
   fails again the device goes on `coverage.failed`, keeps its prior
   row if one exists, and you continue with the next device.

## Setup (two reads)

1. `read_file` `inventory/prod.json`. Candidate set = devices with
   `access.restconf.host` and `access.restconf.port`. Honour `Scope:`
   device keys if present, else every candidate, in `prod.json` order.
   Note each device's `name`, `platform`, `role`,
   `source_metadata.node_definition`, `access.restconf.port`. Keep the
   full list of `prod.json` `name` values for neighbor resolution.
2. `read_file` `inventory/topology-observed.json` if it exists — the
   prior map. Missing → first map: `prior_mapped_at` null, `changes` [].

Set `mapped_at` now. Write the file once immediately with
`status gaps`, `coverage.state partial`, `probed 0`, `devices` = the
prior rows (or []), so a reader knows a map is in progress.

## Per device — exactly this sequence

Every call carries `params={"fields": ...}` as written (a native
dict). Never drop the filter.

**Call 1 — version.**
`iosxe_restconf_get(path="Cisco-IOS-XE-device-hardware-oper:device-hardware-data/device-hardware/device-system-data", port=<port>, params={"fields": "software-version"})`.
`software_version` = the token after `Version ` up to the next comma
(`... Version 17.15.1a, RELEASE ...` → `17.15.1a`). Ignore the rest
of the string.

**Call 2 — interfaces.**
`iosxe_restconf_get(path="Cisco-IOS-XE-native:native/interface", port=<port>, params={"fields": "GigabitEthernet(name;ip/address/primary);TenGigabitEthernet(name;ip/address/primary);Loopback(name;ip/address/primary);Tunnel(name;ip/address/primary);Vlan(name;ip/address/primary)"})`.
The payload is grouped by type (`GigabitEthernet[]`, `Loopback[]`,
...). For each entry: `name` = type + `name` field (`GigabitEthernet`
+ `3.51` → `GigabitEthernet3.51`; `Loopback` + `0` → `Loopback0`);
`cidr` = `ip.address.primary.address` + `/` + prefix length of
`ip.address.primary.mask` (255.255.255.252 → /30, .0 → /24, .255 →
/32), or null when the entry has no `ip`. A type absent from the
payload has no interfaces of that type.

**Call 3 — neighbors.**
`iosxe_restconf_get(path="Cisco-IOS-XE-cdp-oper:cdp-neighbor-details", port=<port>, params={"fields": "cdp-neighbor-detail(device-name;local-intf-name;port-id;platform-name)"})`.
For each `cdp-neighbor-detail[]` entry write one row:

| CDP field | Row field |
|-----------|-----------|
| `local-intf-name` | `local` = `interface:<this device name>/<value>` |
| `device-name` minus everything from the first `.` | `far_name` |
| `port-id` (expand `Gi`→`GigabitEthernet`, `Te`→`TenGigabitEthernet`, `Gig 0/0`→`GigabitEthernet0/0`) | `far_port` |
| `far_name` matched **case-insensitively** to a `prod.json` `name` | `far` = `interface:<that prod.json name>/<far_port>`; no match → null |
| `platform-name` | `platform_hint` (null when absent or blank) |

204, 404, or empty → call
`iosxe_restconf_get(path="Cisco-IOS-XE-lldp-oper:lldp-entries", port=<port>, params={"fields": "lldp-entry"})`
once; same mapping with `device-id`, `local-interface`,
`connecting-interface` (model leaf names; LLDP is disabled in this
lab, so unverified). No `lldp-entry[]` in the payload → no neighbor
protocol.
Both empty → `neighbors []` and the device goes on
`coverage.neighbor_protocol_absent`.

Do not drop a row because it looks wrong. Do not merge two rows. Do
not skip a row because another device already reported that link. Do
not check whether the far port's address matches. Two devices
reporting the same cable is expected and is the reader's job to pair.

**Reduce.** Build this device's row: `keys` (device key, every
`neighbors[].local`, every non-null `neighbors[].far`), `name`,
`platform`, `role`, `node_definition` (all from `prod.json`),
`software_version`, `probed_at` (now), `interfaces[]`, `neighbors[]`.

**Diff.** If the prior map has a row for this device, compare only
against that row and append events to `changes[]` (`at` =
`mapped_at`, `device` = this device):

| Event | When |
|-------|------|
| `neighbor_added` | a `local` present now, absent before (`current` = far or far_name) |
| `neighbor_removed` | a `local` present before, absent now |
| `neighbor_moved` | same `local`, different `far` (or `far_name` when unresolved) |
| `version_changed` | `software_version` differs |
| `interface_added` / `interface_removed` | interface name present on one side only |

No prior row → `device_added` if a prior map exists, nothing on a
first map.

**Write.** Replace this device's row in `devices[]` (or append),
update `coverage.probed`, `keys`, `updated_at`, and `write_file` the
whole file. Then start the next device.

## Finish

After the last device: `coverage.state` `complete` when `failed` is
empty, else `partial`; `status` `ok` / `gaps`; `prior_mapped_at` ←
the prior file's `mapped_at`. A device that was in the prior map but
is no longer in `prod.json`'s candidate set → `device_removed`, drop
its row. Trim `changes[]` to the last 20. `headline`: probed / in
scope, neighbor rows, count of rows with `far` null (name them), then
the change events in words or "first map". `next_action`: `none`, or
`Add <far_name> to inventory` when any `far` is null, or `Re-run:
<device> failed`. Write, then `read_file` it back.

## Budget

| Item | Max |
|------|----:|
| Workspace reads | 3 |
| Workspace writes | in-scope devices + 2 |
| IOS-XE `iosxe_restconf_get` calls | 4 × in-scope devices, cap 40 |

Over budget: finish the current device, write, stop with `gaps` and
the unprobed devices named in `coverage.detail`.

## Reply

```text
Visit: topology
Result: <ok | gaps | unavailable>
Wrote: inventory/topology-observed.json
Devices: <probed> of <in_scope> probed
Neighbors: <n> rows, <k> not in inventory (<names>)
Changes: <none since <prior_mapped_at> | first map | one line per event>
Next: <next_action>
```
