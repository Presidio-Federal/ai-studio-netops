# Date rules — Network Design

A date on an item or step only when a workspace file, a
ServiceNow MCP return, or the operator this turn named it.
Null stays null.

| `date_basis` | Take the date from |
|--------------|--------------------|
| `cisco_eox` | `end_of_sale` `end_of_support` `end_of_software_support` `end_of_security_vuln_support` |
| `psirt` | Advisory or software-train urgency already on the estate row / item dump |
| `lifecycle_window` | `plan.timeline[].window` |
| `servicenow` | REQ/RITM/CHG/asset dates from MCP or cases on disk |
| `health_constraint` | Start now because a vital is degraded |
| `compliance` | Failed run `updated_at` or intel priority with no calendar |
| `testing` | Last test stamp |
| `operator` | They said it this turn |
| `unknown` | Nothing dated this yet |

Do not invent lead times, list prices, or SKUs. Lab node
definitions are not orderable models.
