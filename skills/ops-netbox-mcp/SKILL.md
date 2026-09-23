---
name: ops-netbox-mcp
version: "1.17.2"
description: >-
  v1.17.2 — Canonical top-level workspace keys plus GET
  iosxe_get_platform_and_yang for software_version on
  infra-sot devices. device_type stays node_definition. Onboard /
  populate / bootstrap runs bootstrap even when snap ok (create
  missing). refresh stays audit. Details inventory/infra-sot.json.
---

# Ops NetBox MCP skill

NetBox is infrastructure. Git is config.

This MCP is a thin NetBox REST client. It does not ingest IOS-XE or map
vendor names. You map GET rows → NetBox bodies **here**. Before POST it
unwraps host list shapes (`{ "item": … }`, JSON string) into NetBox
arrays. Do not invent XML tricks.

Workspace: read **`inventory/prod.json`** (seed). Write
**`inventory/infra-sot.json`** (ids) and **`state/netbox.json`** (summary).
Never write `state/network-sync.json`. Paths: **`workspace-handoff`**.
Missing json → stop (Ops Network Sync).

Every JSON write includes top-level `keys`: the deduplicated union of exact
entity keys supported by structured fields in that artifact, or `[]`. Do not
infer from prose. Use `site:` for location and
`interface:<device>/<interface>` whenever the device is known. Allowed
prefixes are `device|interface|site|service|test|control|incident|change`.
Keep any nested `keys`.

[references/modes.md](references/modes.md) picks **bootstrap** / **audit** /
**reconcile**. [references/populate.md](references/populate.md) is the
create/update order (tenant → site → type → device → interface → IP →
cable) and when to skip finds using the snap.

## Rules

1. `state/netbox.json` `kind: git` → stop. Missing state file → treat as NetBox.
2. Tenant = `source.name`. Find or create (`name` + `slug`). Write only there.
3. Seed = `tag:simulate`.
4. `device_type` = `source_metadata.node_definition` (`cat8000v`), not a
   product title.
5. Device tags: `[ { "slug": "{tenant}-simulate" }, … ]`.
6. IOS-XE with restconf host+port: when GET is required (modes.md),
   `iosxe_get_platform_and_yang` (no YANG args) for `version`, then
   `iosxe_restconf_get` for interfaces/CDP. Map names and masks here.
   `device_type` stays `node_definition`. No invented IPs or versions.
   GET JSON is not a NetBox body.
7. GET only on the box. Never guess PAT.
8. One cable → `netbox_manage`. Many devices / interfaces / IPs / cables
   → one `netbox_bulk`. Call once. No six retries.
9. A 400 is a bad field in `data`. Fix that field. If the error is still
   `missing: a_terminations` or `data must be a list of objects`, the
   running server is old pass-through — stop and say restart netbox-mcp.
10. Prefer ids in `inventory/infra-sot.json`. `netbox_find` only for a
    missing name or HTTP 404.
11. After the snap, write `state/netbox.json` with `mode` and `links[]`
    copied from snap cable names. Other agents read that first. The human
    reply lists those links. A count of cables with no names is not done.
12. Resolve mode first (modes.md). `refresh` is `audit`. Onboard /
    `populate` / `bootstrap` is `bootstrap` even when the snap is `ok`.
    Never write NetBox in `audit`. `bootstrap` creates missing only.
    `reconcile` applies an approved set only. A board reset is not a write.

## Tools

| Tool | Use |
|------|-----|
| `iosxe_get_platform_and_yang` | Live software `version` (no `yang_model` / `list_modules`) |
| `iosxe_restconf_get` | Read the box (interfaces, CDP) |
| `netbox_test_connection` | Auth / reachability |
| `netbox_find` / `netbox_get` | Lookup |
| `netbox_manage` | One object: parents, **or one cable** (`bootstrap` / `reconcile` only) |
| `netbox_bulk` | Many of one type: device, interface, ip_address, cable (`bootstrap` / `reconcile` only) |
| `netbox_delete` | Remove; `confirm=true` only when the user intends it (`reconcile` only) |

There is no `netbox_sync_device`. Do not call it.

`object_type` closed set: site, device, interface, cable, ip_address,
prefix, vlan, vrf, circuit, virtual_machine, device_type, device_role,
manufacturer, tenant, tag.

## Write contract

NetBox always receives arrays for list fields. The MCP accepts:

| On the wire | What the tool does |
|-------------|--------------------|
| Native list `[{…}, {…}]` | use as-is |
| `{ "item": [ {…}, {…} ] }` | unwrap to that list |
| `{ "item": { …one object… } }` | unwrap to one object |
| `{ "item": { "object_type", "object_id" } }` on a termination | unwrap to a one-element array |
| `'[{…}]'` JSON string | `json.loads`, then same as above |

XML `<item>` under a list field is the host's array encoding. Leave it.
Do not add `type="array"`, CDATA, or `<value>`.

**One cable** — `netbox_manage`, `data` is one object:

```
netbox_manage action=create object_type=cable
data={
  "status": "connected",
  "a_terminations": [{"object_type": "dcim.interface", "object_id": 8328}],
  "b_terminations": [{"object_type": "dcim.interface", "object_id": 8339}]
}
```

**Many cables** — one `netbox_bulk` with that same body repeated in a list.

`object_id` is a number. Related fields: id, slug, or name. Interface
`type` is a NetBox slug (`1000base-t`, `virtual`, `lag`) — map Cisco
names in this skill.

## Workflows

- Locate: `netbox_find` with `tenant=` — skip when ids are in the snap
- Modes: [modes.md](references/modes.md)
- Populate writes: [populate.md](references/populate.md)
- Twin: [twin-from-netbox.md](references/twin-from-netbox.md)

Skill resources — use exactly:

- `references/modes.md`
- `references/populate.md`
- `references/environment.md`
- `references/state.md`
- `references/workspace-contract.md`
- `references/sot-from-iosxe.md`
- `references/object-types.md`
- `references/twin-from-netbox.md`
- `references/tools.md`
- `schemas/infra-sot.schema.json`
- `schemas/netbox-state.schema.json`
- `examples/infra-sot.example.json`
- `examples/netbox-state.example.json`
- `examples/netbox-state-audit.example.json`
