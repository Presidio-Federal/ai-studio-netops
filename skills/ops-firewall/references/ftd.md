# FTD access rule

The script owns the write. These are the calls it makes if
`hai_mcp` is unavailable.

Host and port from this device's `access.restconf`. Omit username
and password. List name `SCAN-ALLOW-WEB`.

Checked on the prod firewall, HTTPS port 4461, 2026-10-27. One
policy, default action `DENY`. Port objects `HTTP` (80), `HTTPS`
(443), and `TCP-8080` (8080) already exist.

1. `ftd_get` `policy/accesspolicies`. Use the first policy id.
2. `ftd_get` `object/tcpports` with `params` `limit` `100`. Match
   `port` 80, 443, and 8080.
3. `ftd_post` `policy/accesspolicies/{id}/accessrules`. Payload
   `type` `accessrule`, `ruleAction` `PERMIT`, `name`
   `SCAN-ALLOW-WEB`, `destinationPorts` the three objects
   (`id`, `type` `tcpportobject`, `name`).
4. `ftd_pending_changes`. Do not deploy unless the task says deploy.

The default action is the deny for every other port. Do not add a
second deny-all rule. A permit whose `destinationPorts` is empty
still matches every port. Report that rule's name. Do not delete it.

Remove: `ftd_delete` `policy/accesspolicies/{id}/accessrules/{ruleId}`
for the rule named `SCAN-ALLOW-WEB`. A delete of that test rule
returned 204, and a following get returned 404.
