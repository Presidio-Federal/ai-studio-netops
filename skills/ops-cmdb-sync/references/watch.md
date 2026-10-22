# Run

One `execute_command`, `execution_type: "mcp_orchestration"`. Use the path Studio shows for the attached `ops-cmdb-sync/scripts/sync_cmdb.py`. Copy it. Do not retype a path from memory. The transcript may render it as `Internal directory`; that is the real path.

Each `execute_command` is a new container. In that container the workspace is the `file_explorer` folder beside `skills` on the path Studio shows for `sync_cmdb.py`. Copy that directory. Pass it as `--workspace`. Do not pass the relative name `file_explorer`, and do not `cd`.

```text
python3 <skill>/scripts/sync_cmdb.py sync --workspace <file_explorer> --device <device-name> --signal <netbox|servicenow|unknown>
```

`--device` is the one token in `Sync <device-name>.` `--signal` is `netbox`, `servicenow`, or `unknown`. The last stdout line is the result. A line above it from the runtime is not the result. Do not open `state/cmdb-sync.json` to fill the reply.

If stderr says `hai_mcp unavailable`, follow the manual order. Any other failure: one line from stderr, then stop. Do not collect by hand.

## Manual order

Use this only when the script reports `hai_mcp unavailable`. Same scope as the script. One device. No second page.

1. `read_file` `inventory/prod.json`. The name must be a `devices[]` row. Tenant is `netbox.tenant`, else `source.name`. Missing either → write `state/cmdb-sync.json` `failed`, gap `outside lab inventory`, stop.
2. RESTCONF host and port from that row. Missing → `failed`, gap `no restconf`, stop.
3. `iosxe_restconf_get` hostname, then interfaces. Hostname must equal the name. Else `failed`, stop.
4. NetBox: snap id and `netbox_get`, or one `netbox_find` with `name`, `tenant`, and `limit` 5. Reject a row whose tenant is not the lab tenant or whose tags omit `{tenant}-simulate`.
5. One `snow_query_table` as in `references/fields.md`, `limit` 5. Drop any row whose name is not the device.
6. Update the existing NetBox primary only when its address host differs. Read it back.
7. `write_file` `state/cmdb-sync.json`. `read_file` it back.

Do not call `netbox_find` without `tenant`. Do not query `alm_hardware`. Do not search serials.
