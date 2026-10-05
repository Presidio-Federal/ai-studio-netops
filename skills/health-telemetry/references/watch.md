# Health Telemetry visit

This agent runs the NetFlow plane through Grafana. A schedule line
or a chat that names the NetFlow health check, or Health Telemetry,
is authorization. Do not confirm. Do not call Splunk or a device MCP.

If they ask for a different health check: reply only `That's not what
I do.` and stop.

## This plane only

Do not write `state/`. The only metadata write is
`health/metadata-netflow.json`. Do not read other planes. Do not
list `health/` except `health/netflow/` **after** a stamp write, to
keep 10 stamps.

The diff is against the board's `netflow.current[]`. Do not open the
prior stamp.

## Health visit — run the script

One `execute_command`, `execution_type: "mcp_orchestration"`. Use the
path Studio shows for the attached
`health-telemetry/scripts/visit_netflow.py`. Copy it. Do not retype a
path from memory. The transcript may render it as `Internal
directory`; that is the real path.

Each `execute_command` is a new container. In that container the workspace is the `file_explorer` folder beside `skills` on the path Studio shows for `visit_netflow.py`. Copy that directory. Pass it as `--workspace`. Do not pass the relative name `file_explorer`, and do not `cd`.

```text
python3 <skill>/scripts/visit_netflow.py collect --workspace <file_explorer>
```

The last stdout line is the summary. Ignore any runtime line above it.

If `needs_note` is non-empty, one `execute_command` with
`execution_type: "standard"`, same copied path:

```text
python3 <copied script path> annotate --workspace <copied file_explorer directory> --stamp health/netflow/2026-10-05T18-29-09Z.json --headline "<one sentence>" --note "device:NAME=<one sentence>"
```

`--stamp` is the summary field `stamp`, copied exactly. It starts
with `health/netflow/` and ends with `.json`. Do not pass the bare
`watch_id`. Do not put a quote on the end of `--stamp`.

One `--note` per `needs_note` item. The separator is `=`. Several
keys on one note are joined with `+` before that `=`. If stderr says
`hai_mcp unavailable`, follow the manual order in
`references/netflow.md`. Any other failure: report that line and
stop. Do not collect by hand. Do not read `visit_netflow.py`.

Reply from the summary line. Do not open the stamp or the board to
fill it.

`bucket`, `measurement`, `datasource_uid`, and `window` stay in
`health/metadata-netflow.json`. The script reads them. Do not pass
them on the command. When the board has no lookup, or F1 returns no
rows and `provenance.netflow` is not `user`, the script discovers
the lookup with the Grafana tools and writes it back.
