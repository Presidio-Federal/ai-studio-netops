# Produce — Health Logging

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not invent files.

One visit writes one new stamp, then rewrites the metadata. Do not
write `state/`. Do not write the NetFlow board or `health/netflow/`.

## When to write

| File | Kind | When |
|------|------|------|
| `health/splunk/<stamp>.json` | observation | **Every** visit, first. The rows, the delta from the prior stamp, and the tags. Never overwrite. |
| `health/metadata-splunk.json` | metadata | **Every** visit, second. SOAP summary, lookup, and `proof`. No rows. `keys` is `[]`. |

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
At most **10** stamps; delete older after write.

The script writes the stamp and a SOAP draft. `annotate` replaces
the four SOAP sentences. The nurse does not `write_file` either path.

`proof` is the stamp path. The lookup the next visit needs stays
here: `index`, `sourcetype`, `window`, `collected_through`.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. A Splunk row writes those key types only, and only on the stamp. Metadata `keys` stays `[]`. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.
