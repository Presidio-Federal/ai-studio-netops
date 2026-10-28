# Health Logging visit

This agent runs the Splunk syslog plane. A schedule line or a chat
that names the Splunk health check, or Health Logging, is
authorization. Do not confirm. Do not call Grafana or a device MCP.

If they ask for a different health check: reply only `That's not what
I do.` and stop.

## This plane only

Do not write `state/`. The only metadata write is
`health/metadata-splunk.json`. Do not read other planes. Do not
list `health/` except `health/splunk/` **after** a stamp write, to
keep 10 stamps.

The diff is against the previous stamp's `readings[]`. Metadata
does not hold those rows.

## Health visit — run the script

One `execute_command`, `execution_type: "mcp_orchestration"`. Use the
path Studio shows for the attached
`health-logging/scripts/visit_splunk.py`. Copy it. Do not retype a
path from memory. The transcript may render it as `Internal
directory`; that is the real path. Do not set `timeout`. The call
is the command and `execution_type` only.

Each `execute_command` is a new container. In that container the workspace is the `file_explorer` folder beside `skills` on the path Studio shows for `visit_splunk.py`. Copy that directory. Pass it as `--workspace`. Do not pass the relative name `file_explorer`, and do not `cd`.

```text
python3 <skill>/scripts/visit_splunk.py collect --workspace <file_explorer>
```

The last stdout line is the summary. Ignore any runtime line above it.
The stamp is already written. It holds the rows, the delta, and the
tags.

Then one `execute_command` with `execution_type: "standard"`, same
copied path. This replaces the SOAP summary. It does not edit the
stamp.

```text
python3 <copied script path> annotate --workspace <copied file_explorer directory> --stamp health/splunk/2026-10-05T18-29-09Z.json --subjective "<why this visit>" --objective "<what changed since the prior stamp, and the proof path>" --assessment "<one verdict>" --plan "<next check, or none>"
```

`--stamp` is the summary field `stamp`, copied exactly. It starts
with `health/splunk/` and ends with `.json`. Do not pass the bare
`watch_id`. Do not put a quote on the end of `--stamp`.

Each SOAP argument is one sentence, under 400 characters. Name the
proof path in `--objective`. Do not paste rows, tags, or JSON. No
syslog this window is one fact, not a forwarding failure. If
stderr says `hai_mcp unavailable`, follow the manual order in
`references/splunk.md`. Any other failure: report that line and
stop. Do not collect by hand. Do not read `visit_splunk.py`.

Reply from the summary line. Do not open the stamp or the metadata
to fill it.

`index`, `sourcetype`, and `window` stay in
`health/metadata-splunk.json`. The script reads them. Do not put
them in the prompt.
