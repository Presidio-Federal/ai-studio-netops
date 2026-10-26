# Elasticsearch tools this visit calls

Names from `docs/mcp-index.md`. The script calls these. The nurse
does not, unless stderr says `hai_mcp unavailable`.

| Tool | When | Arguments |
|------|------|-----------|
| `elasticsearch_query` | F1, F2, F3 | `query` (the ES\|QL in `netflow.md`), `timerange` (the board `window`), `limit` 50 |
| `elasticsearch_list_data_streams` | F1 empty and the stream is not operator-pinned | none |

`elasticsearch_query` returns `{ok, query, took, truncated, rows}`.
`query` must start with `FROM`. The `FROM` target is a `logs-*` or
`metrics-*` data stream. `timerange` caps at `7d`. This visit uses
`15m`, `1h`, or `1d`. `rows` is a list of objects. `truncated` means
the tool cut the table.

`elasticsearch_list_data_streams` returns
`{ok, data_streams:[{name, indices, docs, health, template}]}`.
Keep a name that starts with `logs-` and contains `netflow`.

`elasticsearch_fields` is not this visit. The mapping is large.
`elasticsearch_status` is not this visit. Kibana rule tools are not
this visit.
