# Produce — Health Device

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`. Do not
invent files. Persist with `write_file` on catalog paths.

One device visit writes **one** new `health/iosxe/<stamp>.json`
and updates `health/metadata-iosxe.json` (`last_visit_id`,
`last_collected_at` only). Do not write `state/`. Do not write
other `health/<source>/` directories. Do not write a port or host
into metadata.

## When to write

| File | Kind | When |
|------|------|------|
| `health/metadata-iosxe.json` | metadata | After each visit. `last_visit_id` is this stamp. No port, no host. |
| `health/iosxe/<stamp>.json` | observation | Each device visit; **never overwrite**. |

Do not write `health-board.md`.

Stamp `YYYY-MM-DDTHH-MM-SSZ.json`. If that path exists, bump 1s.
`watch_id` matches **this** visit’s new file. Never overwrite. At
most **10** stamps under `health/iosxe/`; delete older after write.

Do not write `runs/`, `inventory/`, `trend-analysis.json`, or
`state/network-sync.json`. Do not write under
`automations/schedules/`.

Visit steps: `references/watch.md`.

Unavailable counts are null.
