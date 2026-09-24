# Topology map — observed physical topology

Use only when the task line names the **network topology map**
(`Run the network topology map only.`). It is not a health visit: no
counters, no BGP, no ACL, no stamp, no board write. One file:
`inventory/topology-observed.json` (schema
`schemas/topology-iosxe.schema.json`, example
`examples/topology-observed.example.json`).

The product is what a digital twin needs and nothing else: which
devices exist, what they are (`node_definition`, `software_version`),
what interfaces they have, and who is cabled to whom. Everything in
the file is **observed** from the devices. Intended topology lives in
git; another writer owns it.

## Inventory and scope

Same as `references/iosxe.md` steps 1–3: `read_file`
`inventory/prod.json`; candidate set = devices with RESTCONF; honour
`Scope:` device keys if present, else every candidate. Then `read_file`
`inventory/topology-observed.json` if it exists — that is the prior map.
Missing → first map, `prior_mapped_at` null, `changes` [].

## Calls per device in scope

| # | Purpose | Call |
|---|---------|------|
| 1 | Software version | `iosxe_get_platform_and_yang(port=<port>)` with **no other arguments** — do not pass `yang_model` or `list_modules`. Keep `version` only. |
| 2 | Interface list and addresses | `iosxe_restconf_get(path="Cisco-IOS-XE-interfaces-oper:interfaces", port=<port>)` — keep every `interface[].name` and its `ipv4` (as `address/prefix`, null when none). Include admin-down and Loopback. Discard counters and states. |
| 3 | Neighbors | `iosxe_restconf_get(path="Cisco-IOS-XE-cdp-oper:cdp-neighbor-details", port=<port>)` |
| 3b | Only when 3 returned 204/404/empty | `iosxe_restconf_get(path="Cisco-IOS-XE-lldp-oper:lldp-entries", port=<port>)` once |

Both 3 and 3b empty → the device goes on
`coverage.neighbor_protocol_absent`; its interfaces are still recorded.
A failed call → `coverage.devices_failed`; the device row keeps its
prior values from the old map (or `software_version` null and
`interfaces` [] on a first map). Never retry more than once. Never
GET native config. Never SSH.

## Build `devices[]`

One row per device in scope (`collected` true) plus one per
`prod.json` device that a neighbor row resolved to but was not in
scope or has no RESTCONF (`collected` false, `interfaces` [],
`software_version` null). `platform`, `role`, `node_definition` come
from `prod.json` (`platform`, `role`,
`source_metadata.node_definition`) — never from the box. Devices in
the prior map but out of this scope are carried over unchanged.

## Build `links[]`

From each CDP row: local end = `interface:<this device>/<local-intf-name>`;
far device = `device-name` with any domain suffix removed, matched
case-insensitively to a `prod.json` `name`; far end =
`interface:<that name>/<port-id>`. LLDP: `device-id`,
`local-interface`, `port-id` the same way. Expand short names
(`Gi1` → `GigabitEthernet1`, `Te` → `TenGigabitEthernet`, `Gig 0/0` →
`GigabitEthernet0/0`) so they match the interface list.

- Far device matched → a link. `a` is the interface key whose device
  name sorts first; `b` the other. Two devices reporting the same
  pair are **one** row with both in `seen_from`.
- Far device not matched → an `unresolved[]` row (`neighbor_name`
  as returned minus suffix, `port`, `platform_hint` from the CDP
  `platform` field when present). Do not mint a key. Do not add it to
  `devices[]`.
- Skip local ends that are `Loopback*`, `Vlan*`, or a management port
  the CDP row names as such.

Merge with the prior map: a link present before and now keeps
`first_seen`; `last_seen` = `mapped_at`. A scoped map replaces only
links that have a scoped device in `seen_from`; other links carry over.

## `changes[]` — what moved since the prior map

Compare against the prior file. One event per item, appended to the
ring (keep the last 10, oldest first), `at` = `mapped_at`:

| Event | When |
|-------|------|
| `link_added` | pair not in the prior `links[]` |
| `link_removed` | prior pair not seen now, and at least one end was in scope and did not fail |
| `link_moved` | a local end that pointed at one far end now points at another (`subject` the local end, `prior`/`current` the far ends) |
| `link_one_sided` | both ends are RESTCONF devices in scope, only one reported it (`current` the reporting device) |
| `device_added` / `device_removed` | a `collected` device appeared in or vanished from `prod.json`'s candidate set |
| `version_changed` | `software_version` differs from the prior row |
| `interface_added` / `interface_removed` | interface list of a collected device differs |

First map: `changes` [].

## Status and headline

`status`: `ok` when every device in scope was probed and no
`link_one_sided` event was raised this map; `gaps` when a device
failed or a link between two probed devices was one-sided;
`unavailable` when nothing was probed. `coverage.state` likewise.

`headline`: devices mapped, links, unresolved count, then the changes
since `prior_mapped_at` in words (or "first map"). `next_action`:
`none`, or `Add <neighbor_name> to inventory` when `unresolved[]` is
non-empty, or `Re-run: <device> failed` on gaps.

`keys`: every `device:` in `devices[]` and every interface key on
`links[]`.

## Budget

| Item | Max |
|------|----:|
| Workspace file read/write | 6 |
| IOS-XE calls (`iosxe_get_platform_and_yang` + `iosxe_restconf_get`) | 40 |

Over budget: write what you have as `gaps`, list the devices not
probed in `coverage.detail`.

## Reply

```text
Visit: topology
Result: <ok | gaps | unavailable>
Wrote: inventory/topology-observed.json
Devices: <n> mapped, <m> inventory neighbors without RESTCONF
Links: <n> (<k> one-sided)  Unresolved: <n>
Changes: <none since <prior_mapped_at> | first map | one line per event>
Next: <next_action>
```
