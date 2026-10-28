# Produce — Health Elastic

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not invent files.

One visit writes one new stamp, then rewrites the metadata. Do not
write `state/`. Do not write the Splunk board or `health/splunk/`.

## When to write

| File | Kind | When |
|------|------|------|
| `health/netflow/<stamp>.json` | observation | **Every** visit, first. The rows, the delta from the prior stamp, and the tags. Never overwrite. |
| `health/metadata-netflow.json` | metadata | **Every** visit, second. SOAP summary, lookup, and `proof`. No rows. `keys` is `[]`. |

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
At most **10** stamps; delete older after write.

The script writes the stamp and a SOAP draft. `annotate` replaces
the four SOAP sentences. The nurse does not `write_file` either path.

`bucket` is the marker `elasticsearch`. `measurement` and
`data_stream` are the same `logs-*` stream name. `proof` is the
stamp path.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change|application):[^ ].*$`; never infer one. Use `site:` for location. A NetFlow row writes `device:` and `site:` keys only, and only on the stamp. Metadata `keys` stays `[]`. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
