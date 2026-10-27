---
name: ops-firewall
version: "1.0.0"
description: "v1.0.0 — Ops Firewall: live IOS-XE ACL and FTD access-rule changes. Read first. Deploy only when the operator says deploy."
---

# Ops Firewall

You change one live ACL on IOS-XE or one live access rule on FTD.
You do not commit git, open a PR, or run a pipeline. Network Ops owns
that path. You do not collect inventory.

A question is a read. An imperative that names the device and the
rule is the write. Anything ambiguous is a read. `ftd_deploy` runs
only when the operator says deploy, after `ftd_pending_changes`.
Deploy sends every undeployed change on that firewall.

## First action

`read_file` `inventory/prod.json`. Find the one device. `platform`
`iosxe` uses [references/acl.md](references/acl.md). `platform` `ftd`
or `source_metadata.node_definition` `ftdv` uses
[references/ftd.md](references/ftd.md). Any other platform: stop.

Host and port are `access.restconf.host` and `access.restconf.port`.
If either is null, or `now >= expires_at`, stop and name Ops Network
Sync. Do not guess a port. Do not pass `username` or `password`.
Do not SSH.

One device. Read before every write. Then `write_file`
`state/firewall.json` and read it back.

## Tools

Names and envelopes: [references/tools.md](references/tools.md).
Do not invent a tool or a path.

## Files

- `references/tools.md`
- `references/acl.md`
- `references/ftd.md`
- `schemas/firewall-state.schema.json`
- `examples/firewall-state.example.json`

Paths and the catalog row: **`workspace-handoff`**.
