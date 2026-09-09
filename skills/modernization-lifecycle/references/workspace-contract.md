# Produce — Modernization Lifecycle

Paths: **`workspace-handoff`**. Do not `execute_command`. Do not
invent files. Do not `ls` `lifecycle/`.

| File | Kind | When |
|------|------|------|
| `lifecycle/items/<pid>.json` | observation | Each PID collected this turn; replace that file. |
| `state/lifecycle.json` | state | Re-read, merge research onto matching `items[]`, stamp `updated_at`. Keep other PIDs, identity, `source`, `recommendations`, `guidance`, `roadmap_ref`, `selected_replacement`. Cisco SKU → `recommended_replacement`. Family ask → `replacement_ask`. Software train → `recommended_software`. CCW costs when a SKU to price exists. |

MiniMax sandbox: if Access denied lists `file_explorer`, retry
`file_explorer/<row>` once. Same files. Never a UUID. Never
`/shared_workspace/HAI-ASSISTANTS-WAPSPACES/...`. `detail_ref`
stays `lifecycle/items/<pid>.json`.

Do not create `state/lifecycle.json` if it is missing. Stop
`unknown`.

`expires_at` = `updated_at` + 90 days.
