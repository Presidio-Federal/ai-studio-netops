# Health Logging visit

This agent runs the Splunk syslog plane. A schedule line or a chat
that names the Splunk health check, or Health Logging, is
authorization. Do not confirm. Do not call Grafana or a device MCP.

If they ask for a different health check: reply only `That's not what
I do.` and stop.

## This plane only

The observation file is **this visit's plane**. Do not write
`state/`. The only metadata write is `health/metadata-splunk.json`.
Do not read other planes. Do not list `health/` except
`health/splunk/` **after** a stamp write, to keep 10 stamps.

The diff is against the board's `splunk.current[]`. Do not open the
prior stamp.

## Health visit — run the script

One `execute_command`, `execution_type: "mcp_orchestration"`. Use the
path Studio shows for the attached `health-logging/scripts/visit_splunk.py`.
Copy it. Do not retype a path from memory. The transcript may render
it as `Internal directory`; that is the real path.

Each `execute_command` is a new container. In that container the workspace is the `file_explorer` folder beside `skills` on the path Studio shows for `visit_splunk.py`. Copy that directory. Pass it as `--workspace`. Do not pass the relative name `file_explorer`, and do not `cd`.

```text
python3 <skill>/scripts/visit_splunk.py collect --workspace <file_explorer>
```

The last stdout line is the summary. Ignore any runtime line above it.

If `needs_note` is non-empty, one `execute_command` with
`execution_type: "standard"`, same copied path:

```text
python3 <skill>/scripts/visit_splunk.py annotate --workspace <file_explorer> --stamp <stamp> --headline "<one sentence>" --note "device:NAME=<one sentence>"
```

One `--note` per `needs_note` item. The separator is `=`. Several
keys on one note are joined with `+` before that `=`. If stderr says
`hai_mcp unavailable`, follow the manual order in
`references/splunk.md`. Any other failure: report that line and stop.
Do not collect by hand.

Reply from the summary line. Do not open the stamp or the board to
fill it.

`index` and `sourcetype` stay in `health/metadata-splunk.json`. The
script reads them. Do not put them in the prompt.
