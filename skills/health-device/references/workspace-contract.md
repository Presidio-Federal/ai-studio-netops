# Produce — Health Device

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`. Do not
invent files. Persist with `write_file` on catalog paths.

Two modes, selected by the task line. They never run in the same
conversation.

| Mode | Task line names | Writes |
|------|-----------------|--------|
| Health visit | network device / IOS-XE health check | `health/metadata-iosxe.json` (every visit) and at most one `health/iosxe/<stamp>.json` |
| Topology map | network topology map | `inventory/topology-observed.json` only |

Do not write `state/`. Do not write other `health/<source>/`
directories. Do not write a port or host into any of these files.

## When to write

| File | Kind | When |
|------|------|------|
| `health/metadata-iosxe.json` | metadata | Every health visit, quiet or not. `current[]` is this collection (out-of-scope rows kept); `series[]` one estate row per visit, ring of 10; `visits[]` ring of 10; `last_collected_at` this `checked_at`; `last_visit_id` only when a stamp was written. |
| `health/iosxe/<stamp>.json` | observation | First visit, or `vs_prior.changed[]` non-empty, or `coverage.state` ≠ `complete`. **Never overwrite.** |
| `inventory/topology-observed.json` | snapshot | Every topology map. Overwrite; `changes[]` is the ring of what moved. Envelope (`updated_at` `source_agent` `status` `headline` `next_action`). |

A quiet health visit (board exists, nothing material moved, coverage
complete) writes the metadata file only.

Do not write `health-board.md`.

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
`watch_id` matches **this** visit's new file. Never overwrite. At
most **10** stamps under `health/iosxe/`; delete older after write.

Do not write `runs/`, `inventory/prod.json`, `inventory/infra-sot.json`,
`trend-analysis.json`, or `state/network-sync.json`. Do not write
under `automations/schedules/`.

Health visit steps: `references/watch.md`. Field mapping and what is
material: `references/iosxe.md`. Topology map: `references/topology.md`.

Unavailable counts are null.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. An interface key is always `interface:<device>/<interface>` with the `inventory/prod.json` device spelling. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys. A neighbor name that matches no `prod.json` device gets no key — it goes on `topology-observed.json` `unresolved[]`.

## Edges

This agent writes no `relations[]`. Its edges are columns: a board
bgp row's `peer` is the BGP adjacency; a `topology-observed.json`
`links[]` row is the cable. The relationship compiler reads those
columns. Everything this agent writes is observed; it never asserts.
