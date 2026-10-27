# FTD access rules

Host and port from this device's `access.restconf` (the `pat:*:443`
tag). Omit username and password. FDM has no PATCH.

`path` is relative to `/api/fdm/latest/`. These are the only paths:

| Path | What |
|------|------|
| `policy/accesspolicies` | The access policies. |
| `policy/accesspolicies/{id}/accessrules` | Rules on one policy. |
| `policy/accesspolicies/{id}/accessrules/{ruleId}` | One rule. |
| `object/networks` and `object/networks/{id}` | Network objects. |
| `object/tcpports`, `object/udpports`, `object/ports`, and the same path plus `/{id}` | Port objects. |

Read the policy, then its rules, before a write. `ftd_get` with
`params` `limit` when the list is paged.

Add: `ftd_post` to `policy/accesspolicies/{id}/accessrules`. Copy an
existing rule's fields. Change only what the operator named. Include
`type`. Do not send `id` or `version` on a create.

Change: `ftd_put` to the rule path. Body is the GET object with the
same `version` and the named fields changed.

Remove: `ftd_delete` that rule path.

A missing object the rule needs is one `ftd_post` to the object path,
then the rule. Do not invent an object the operator did not name.

These resource paths are the FDM API the client proxies. They were
not in a server file in this repo. A 404 on a path is a gap. Do not
try a second path.

After a write, `ftd_pending_changes`. Put `count` on
`pending_count`. Do not deploy.

Deploy, only when the operator says deploy: call
`ftd_pending_changes` again. The reply states `pending_count` and
that deploy sends every undeployed change. Then `ftd_deploy` with
`confirm=true` and the same host and port. `state` `DEPLOYED` is
success. Nothing pending does not start a job.

Hit counts are `ftd_hit_counts`. That call does not change the policy.
