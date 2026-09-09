# Scope — lab, mode, inventory, tags

Read inventory **before** you pick `devices` / `tags`. Do not invent a
device list. Do not prefix `AI-` onto a name they said. Copy `devices[].name`
exactly.

## Labs

| | Prod | Dev |
|--|------|-----|
| Inventory | `inventory/prod.json` | `inventory/dev.json` |
| `live_lab` | `prod` | `dev` (default) |
| What it is | Production CML | Digital twin |
| Same hostnames | Yes — **different** PAT ports | Yes |
| A pass means | Production evidence | Proposal validation only |

Never copy a port or a device set from one file into the other. If they did
not say **production**, send `environment=dev`. Reading `inventory/prod.json`
does **not** make the run prod. A hostname that exists in both files is
still Dev unless they said production.

Prod live also requires `production_authorized=true` and a real `reason`.
A device list does not skip that flag.

Also read `state/network-sync.json`. If that lab's inventory is `failed` or
`stale`, say so. Do not invent names. Offer: refresh inventory (Network
Sync) or run unscoped.

## Modes

| | `live` (default) | `static` |
|--|------------------|----------|
| What runs | pyATS over SSH on the lab | pytest against git `inventory/configs` |
| Needs PAT / twin | Yes | No |
| `live_lab` | Required | Ignored |
| `scan_dir` | unused | `inventory/configs` |
| Use when | "is it working" | "is it configured" |

Live + no inventory → you cannot resolve a tag group. Unscoped live tests
the runner's full lab. Say that.

## Read order (every run)

1. `state/network-sync.json` (freshness)
2. `inventory/<live_lab>.json` — names, `role`, `tags`, `agent_access`
3. Optional: `state/health.json` only if they asked to test what health
   flagged
4. `test-request.json` **only** when they said pick up the Design request

Missing `test-request.json` is normal. Do not retry, do not stop, do not
`find`. Continue from inventory.

You never write those files.

## Tags and groups

Inventory `devices[].tags` and `devices[].role` are the group list. Workflow
`tags` is a comma-separated **role/function** filter (`edge`, `wan`,
`branch`), used when `devices` is empty.

Do **not** pass as test selectors:

- `pat:*:*` (access maps, not groups)
- `tag:simulate` (Digital Twin topology)
- `synced:*` / `sot:*` (stamps)

`AI-CLOUD-EDGE` and `CLOUD-EDGE` are the same node. Send either. The
workflow matches both to the topology label.

| They say | You do |
|----------|--------|
| One hostname (`WAN-01`) | Find that exact `name` in inventory. `devices=WAN-01`. No `AI-WAN-01`. Missing → stop, list real names |
| "edge" / "wan" / "branch" | Filter inventory `tags` or `role`. Prefer `tags=edge` (or `wan`). Or expand to `devices=` if the set is small |
| `tag:sync` | Live devices that participate in config collect — names with `tag:sync` and `agent_access` |
| `tag:patch` | Design proposal on Dev only — include only if they are testing the proposal |
| "what health found" | Map Health headline/hosts to inventory **names**, then `devices=` |

Live tests: skip `agent_access: false` (no SSH PAT). Say which names you
dropped.

If a name is in Prod inventory but they asked Dev (or the reverse), say it
and use the file for the lab you are actually testing.

## Inputs you send

All strings.

```text
mode=live|static
environment=dev|prod|none    # live uses dev|prod; static uses none
devices=                     # comma hostnames, or empty
tags=                        # edge,wan,branch — only when devices is empty
suites=                      # see run.md
scan_dir=inventory/configs   # static only
allow_all_devices=true       # only for unscoped live
production_authorized=true   # only for environment=prod
```

Do not send `request_id`. The Actions run id is the correlation.

Do not send both a guessed devices list and tags. After the run, prove
`devices=` / `tags=` from the log.
