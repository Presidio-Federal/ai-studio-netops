# Signal

The invoke is one task line:

```text
Sync <device-name>.
```

`<device-name>` is one token: letters, digits, and hyphens. Take it from that line only. Do not take a name from a webhook body, a URL, or another sentence.

Optional label, anywhere in the invoke, ignored by the sync:

- `signal netbox` → `signal` is `netbox`
- `signal servicenow` → `signal` is `servicenow`
- neither → `signal` is `unknown`

No `Sync <device-name>.` line → do not call MCP. Write `state/cmdb-sync.json` with `result` `failed`, `device.name` `""`, `gaps` `["no device"]`, `keys` `[]`, `next_action` `null`. Stop.

`operation` is always `sync`. `operation_id` is the UTC time you started, `YYYY-MM-DDTHH-MM-SSZ`.
