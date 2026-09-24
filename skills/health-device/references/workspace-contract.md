# Produce — Health Device

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`. Do not
invent files. Persist with `write_file` on catalog paths.

One device visit always rewrites `health/metadata-iosxe.json` (the
board) and writes **at most one** new `health/iosxe/<stamp>.json`.
Do not write `state/`. Do not write other `health/<source>/`
directories. Do not write a port or host into metadata.

## When to write

| File | Kind | When |
|------|------|------|
| `health/metadata-iosxe.json` | metadata | Every visit, quiet or not. `current[]` is this collection; `series[]`, `visits[]` rings of 10; `relations[]` rebuilt; `last_collected_at` this `checked_at`; `last_visit_id` only when a stamp was written. No port, no host. |
| `health/iosxe/<stamp>.json` | observation | First visit, or `vs_prior.changed[]` non-empty, or `coverage.state` ≠ `complete`. **Never overwrite.** |

A quiet visit (board exists, nothing material moved, coverage
complete) writes the metadata file only.

Do not write `health-board.md`.

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
`watch_id` matches **this** visit's new file. Never overwrite. At
most **10** stamps under `health/iosxe/`; delete older after write.

Do not write `runs/`, `inventory/`, `trend-analysis.json`, or
`state/network-sync.json`. Do not write under
`automations/schedules/`.

Visit steps: `references/watch.md`. Field mapping and what is
material: `references/iosxe.md`.

Unavailable counts are null.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. An interface key is always `interface:<device>/<interface>` with the `inventory/prod.json` device spelling. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## Relations

`relations[]` on the board is every observed edge this collection saw
(`connected_to` from CDP/LLDP, `peers_with` from a BGP neighbor that
resolved to an inventory device). On a stamp it is only the edges new
this visit. `basis` is always `observed`. Both ends must be in that
file's `keys`. Do not infer an edge from a description, a name, or
`prod.json` `links[]` — those are intended, and another writer owns
them.
