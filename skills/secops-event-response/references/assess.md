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
or 20 service ports. That list is what a block is copied from.

## What the numbers mean

A port scan is one source and many service ports, or one source and
many destinations, in this window. A single service port to one host
is ordinary traffic. An application container talking to a handful of
its own peers is not a block, even when the port count is high.

## Where a block goes

Both names come from `inventory/prod.json`. Do not invent one.

The IOS-XE device is the closest `platform` `iosxe` `role` `edge` to
the source device, walked on `links[]`. Skip an edge whose name
contains `ISP` or `DC`.

The firewall is the `ftdv` device whose name contains the destination
`zone` (`dev` or `prod`). Skip `platform` `asa`.

One destination is one prefix, written as `<prefix>/24`. One task is
one device. The task line is `Deny <source> to <destination> on <device>.`
It does not say deploy.
