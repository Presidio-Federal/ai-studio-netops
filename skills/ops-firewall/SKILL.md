---
name: ops-firewall
version: "1.1.4"
description: "v1.1.4 — Ops Firewall: apply_rule.py reads the device first. An existing SCAN-ALLOW-WEB list is left as it is."
---

# Ops Firewall

You change one live allow-list. IOS-XE gets a named ACL. FTD gets one
access rule. You do not commit git. Network Ops owns that path.

The write is one task:

```text
On <device>, permit tcp to <destination> ports 80, 443, 8080, then deny ip to <destination>.
```

`<device>` is the `inventory/prod.json` name. `<destination>` is `any`
or one host address. A prefix is not a destination. One device. A question is a read. `Deploy.` after an
FTD write deploys every pending change on that firewall.

## First action

`read_file` `inventory/prod.json` only to confirm the workspace.
Then one `execute_command`, `execution_type: "mcp_orchestration"`,
timeout 120. Use the path Studio shows for
`ops-firewall/scripts/apply_rule.py`. The workspace is the
`file_explorer` directory beside `skills` on that path.

```text
python3 <skill>/scripts/apply_rule.py apply --workspace <file_explorer> --device <device> --destination <destination> --permit-ports 80,443,8080
```

Add `--deploy` only when the task says deploy. Do not pass
`--remove`. You add the list. A request to delete it is not this
job. The last stdout line is the result. The script writes
`state/firewall.json`. Do not call `iosxe_restconf_patch` or
`ftd_post` yourself unless stderr says `hai_mcp unavailable`.

Host and port come from that device's `access.restconf`. The script
reads the live list before it writes. `state/firewall.json` does not
decide that. `SCAN-ALLOW-WEB` already inbound on the LAN, or already
an access rule, is result `present`. The box is not changed.

## What the list is

Checked 2026-10-27 on branch RESTCONF port 4403 and FTD port 4461.
The list is named `SCAN-ALLOW-WEB`.

IOS-XE: permit tcp to the destination on 80, 443, and 8080, then deny
ip to that destination. The list is applied inbound on the LAN
interface, the addressed port that is not the WAN. The WAN is a /30
or an address in 100.64.0.0/10. An interface that already has a
different inbound ACL is left alone.
FTD: one permit rule for those three TCP port objects. The policy
default action is the deny for everything else. A permit that names
no destination ports is left in place and reported as a gap.

## Files

- `scripts/apply_rule.py`
- `references/tools.md`
- `references/acl.md`
- `references/ftd.md`
- `schemas/firewall-state.schema.json`
- `examples/firewall-state.example.json`

Paths and the catalog row: **`workspace-handoff`**.
