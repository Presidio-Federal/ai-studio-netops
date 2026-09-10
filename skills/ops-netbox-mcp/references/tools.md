# NetBox tools

Slice of `mcp-tool-capability-lookup.yaml` (2026-08-23). Studio uses live MCP for schemas.
Prefix: `netbox_`. Lookup id: `netbox-mcp`.

Use when:
- Source-of-truth DCIM/IPAM: sites, devices, interfaces, cables, IPs, prefixes, VLANs, VRFs, circuits, VMs, types/roles, tenants, tags
- Search, get, create/update/upsert, bulk write, or delete (confirm required)

Do not use for:
- Live device config (cisco-iosxe) — NetBox is inventory, not the box
- ITSM tickets (ops-snow-mcp)

Typical flows:
- Lookup: netbox_test_connection → netbox_find(object_type='device', site=...) → netbox_get
- Create: netbox_manage(action='create', object_type=..., data={...}) — dry_run=true to preview
- Cable two interfaces: netbox_find object_type=interface (needs device) → netbox_manage cable with a_terminations/b_terminations
- Many objects: netbox_bulk. Delete: netbox_delete(confirm=true)

| Tool | Access | Required | Purpose |
|------|--------|----------|---------|
| `netbox_test_connection` | read | — | Verify NetBox API authentication and reachability. |
| `netbox_find` | read | object_type | Search NetBox objects. |
| `netbox_get` | read | object_type | Get one NetBox object by object_type and object_id, or name/slug. |
| `netbox_manage` | write | action, object_type | Create, update, or upsert one NetBox object. |
| `netbox_bulk` | write | action, object_type | Bulk create or update many objects of one object_type. |
| `netbox_delete` | write | object_type | Delete NetBox objects. |

