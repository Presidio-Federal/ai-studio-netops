# Security event response

The visit runs `scripts/respond.py`. This file is the manual order
when stderr says `hai_mcp unavailable`.

Read `state/health.json` and the five boards first
(`health/metadata-application.json`, `health/metadata-netflow.json`,
`health/metadata-splunk.json`, `health/metadata-iosxe.json`,
`health/metadata-servicenow.json`). The prior scan rows are on the
NetFlow and Splunk boards. The other boards are the clock.

Then the same calls the nurses make. Copy the query text. Do not
write a query of your own. Do not set `timeout`.

Elasticsearch: `health-elastic` `references/netflow.md`, F1 then F2
then F3 then F4. `elasticsearch_query`. `timerange` is
`netflow.window`. `<measurement>` is `data_stream`. F4 is the port
spread. `dst_port` there is the distinct port count and `protocol`
is `scan`.

Splunk: `health-logging` `references/splunk.md`, S1 then S2 then S3.
`splunk_search`. Index and sourcetype come from the Splunk board.
S1 and S3 use `-<window>`. S2 uses `collected_through`. S3 is the
firewall spread.

F4 names the source and hides the client address. One more
`elasticsearch_query` on the same stream and window groups by
`source.ip` and the /24, and only rows with at least 20 destinations
or 20 service ports. That list finds the source. It is not the
destination of the block.

## What the numbers mean

A port scan is one source and many service ports, or one source and
many destinations, in this window. A single service port to one host
is ordinary traffic. An application container talking to a handful of
its own peers is not a block, even when the port count is high.

## Where a block goes

Both names come from `inventory/prod.json`. Do not invent one.

The device is the closest `platform` `iosxe` `role` `edge` to the
source, walked on `links[]`. Skip an edge whose name contains `ISP`
or `DC`. One scan source is one edge. Do not add the other edges.
Also the closest `platform` `ftd` or `node_definition` `ftdv` on that
same walk. One firewall for that source. A source with no firewall
on the path is a gap. The edge is still a block.

The destination is `any`. The task line is `On <device>, permit tcp to any ports 80, 443, 8080, then deny ip to any.`
It does not say deploy. Do not pass a prefix, 4403, 4461, or ports
from the scan.
