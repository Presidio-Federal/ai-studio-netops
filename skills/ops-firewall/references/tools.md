# Tools

IOS-XE names from `skills/ops-cisco-iosxe-mcp`. FTD names from
`cisco-ftd` in `docs/mcp-index.md` (2026-10-26). Do not invent tools.
Do not pass `username` or `password`. Host and port come from
`inventory/prod.json` `access.restconf`.

| Tool | Use |
|------|-----|
| `iosxe_restconf_get` | Read `Cisco-IOS-XE-native:native/ip/access-list`. |
| `iosxe_restconf_patch` | Add an ACE. Merges. |
| `iosxe_restconf_put` | Replace an ACL or ACE. Overwrites that resource. |
| `iosxe_restconf_delete` | Remove the ACL or ACE the operator named. |
| `iosxe_save_config` | After a verified IOS-XE write. |
| `ftd_get` | Read a policy, rule, or object. `path` is relative to `/api/fdm/latest/`. |
| `ftd_post` | Create a rule or object. Payload includes `type`. |
| `ftd_put` | Replace a rule or object. Send the `version` from the GET. |
| `ftd_delete` | Remove a rule or object. `path` includes the id. |
| `ftd_pending_changes` | After every FTD write, and before deploy. |
| `ftd_hit_counts` | Read hit counts. Omit `policy_id` for every access policy. |
| `ftd_deploy` | `confirm=true` only when the operator says deploy. |

`ftd_deploy` deploys every undeployed change on that firewall, not
only the last write. `confirm=false` does not deploy.

Do not call `iosxe_ssh_command`.
