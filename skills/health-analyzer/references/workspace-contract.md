# Produce — Health Analyzer

Paths, Kind, catalog: **`workspace-handoff`**.
Write schemas live in this skill. Do not `execute_command`. Do not
invent files. Persist with `write_file` on the catalog path.

Every completed analysis replaces **`state/health.json`**.
Do not write `health/<source>/` or other catalog files.

## When to write

| File | Kind | When |
|------|------|------|
| `state/health.json` | state | Every completed analysis; replace in full. |

Envelope `status`: `ok` when current vital consults were rolled up
and none degraded; `partial` when a vital plane is missing or
`not_requested`; `stale_chart` when a needed vital plane was stale
or dispatched; `degraded` when a voting vital consult is degraded;
`unknown` when no vital observation is usable.

`headline` is regenerated from `series`. `next_action` is usually
`none`.

Do not write visit files under `health/`.

Analysis steps: `references/analyze.md`.
