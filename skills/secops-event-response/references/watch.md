# Visit procedure

One visit. An API call, or a line that says to run the security
event response, is authorization. Do not confirm.

If they ask for a health check, a chart rewrite, or a firewall
change with no event, reply `That's not what I do.` and stop.

Read `state/health.json`, `health/metadata-netflow.json`, and
`health/metadata-splunk.json` before the script. The script then
queries Elasticsearch and Splunk and writes `state/secops-event.json`.

You name the kind. The script does not. A port scan is the shape in
`references/assess.md`. Order a block only for that kind, and only
for a placement the script listed.

After the blocks are on the file, invoke Ops Firewall once per block
and wait. Task line `Deny <source> to <destination> on <device>.`
Do not add the word deploy. If Ops Firewall is not attached, the
blocks stay on the file and the reply says the writer is not attached.
