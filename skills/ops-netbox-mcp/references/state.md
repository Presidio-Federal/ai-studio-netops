# Ops NetBox SoT board (`state/netbox.json`)

Same pattern as Health (`state/health.json`) and ServiceNow
(`state/servicenow.json`): **details** in a domain file, **summary** in
`state/`. Other agents open this file first. They open
`inventory/infra-sot.json` only when they need ids, cables, or seed rows.

You are the only writer. Never write `state/network-sync.json`.

## When to write

Every invoke that completes (`bootstrap`, `audit`, `reconcile`, or failed
push). Replace the file. Do not merge into Sync state.

| File | Role |
|------|------|
| `inventory/infra-sot.json` | Details — seed, parent/device/interface/cable **ids** |
| `state/netbox.json` | Summary — **links[]** (wiring names), counts, headline, next step |

## Order

1. Read `inventory/prod.json` (seed). Missing → stop (Network Sync).
2. Read `state/netbox.json` if present (prior headline / `kind`).
3. Read `inventory/infra-sot.json` if present (ids + seed compare).
4. Resolve mode ([modes.md](modes.md)). Do that job (or fail).
5. Write `inventory/infra-sot.json`, then `state/netbox.json`.
6. Validate if the script exists. Read both files back.

## `state/netbox.json`

Copy counts, gaps, and **links** from the snap. Ids stay in the snap.

- `links[]`: one row per snap cable — `a_device`, `a_interface`, `b_device`,
  `b_interface` (names only). Same order as `cables[]`. Length =
  `counts.cables`. This is what Twin and the operator use.
- `mode`: `bootstrap` · `audit` · `reconcile` — the job this invoke ran.
  Required. `refresh` records `audit`.
- `kind`: `netbox` after a NetBox path. `git` only if this run stopped
  because infra is git-only (operator / yaml intent already decided; you
  still write the summary so Twin can see it in `state/`).
- `source`: `cml` · `api` · `document` from prod.json `source.type`
  (`cml` / `api` / `document`).
- `tenant` / `site`: slugs you used in NetBox (`source.name`).
- `seed_match`: true when simulate seed in prod.json equals snap `seed`.
- `details`: always `inventory/infra-sot.json`.
- `next_action`: one line or null (never a Sync Actions job).
- `headline`: name the wiring (or `0 links`), not only device counts.

## Hard stop

Do not write `state/network-sync.json`. Do not copy this headline into
Sync's Gaps.
