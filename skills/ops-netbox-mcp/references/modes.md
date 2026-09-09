# Operating modes

Resolve **one** mode before any RESTCONF or NetBox write. Then do only that
mode. MCP names stay exact: `iosxe_get_platform_and_yang`,
`iosxe_restconf_get`, `netbox_test_connection`,
`netbox_find`, `netbox_get`, `netbox_manage`, `netbox_bulk`, `netbox_delete`.

There is no `netbox_sync_device`. There is no silent overwrite.

| Mode | Meaning |
|------|---------|
| `bootstrap` | Create **missing** NetBox infrastructure from `inventory/prod.json` and live IOS-XE / CDP. Do not update objects that already have ids. |
| `audit` | Compare Network Sync seed + live observations to NetBox. **No** NetBox writes. |
| `reconcile` | Apply **approved** differences to NetBox (create missing and update those approved rows). |

Write `mode` on both `inventory/infra-sot.json` and `state/netbox.json`.

## Resolve mode

Match the operator text (case-insensitive). First matching row wins.

| Operator said | Mode |
|---------------|------|
| `bootstrap`, `populate`, `create SoT`, `create NetBox`, `first populate`, `seed NetBox`, `onboard infra`, Onboard | `bootstrap` |
| `audit`, `compare`, `diff`, `check NetBox`, `refresh` | `audit` |
| `reconcile`, `apply approved`, `apply diffs`, `apply the gaps`, `push diffs` | `reconcile` |

Named `populate` / `bootstrap` / Onboard: **`bootstrap` even when snap
`ok` or `gaps`**. Create missing only. Do not update existing ids. A board
reset is not `refresh`.

Unnamed invoke:

| Workspace | Mode |
|-----------|------|
| No snap, or snap `status` is `failed` | `bootstrap` |
| Snap present (`ok` or `gaps`) | `audit` |
| `state/workspace.json` `planes.netbox` is `yes` | `audit` (skip writes) |

Never default to `reconcile`. `refresh` is **always** `audit`. Do not treat
`refresh`, `sync NetBox`, `update NetBox`, or board reset as a write.

`state/netbox.json` `kind: git` → stop (any mode). Missing `inventory/prod.json`
→ stop (Network Sync).

Find-in-NetBox and twin-from-NetBox are not these modes
([twin-from-netbox.md](twin-from-netbox.md)).

## GET required

`iosxe_get_platform_and_yang` (version) then `iosxe_restconf_get` on every
seed box with `access.restconf.host` + `.port` when the table says yes.
Never guess PAT. Never pass `yang_model` on the version call.

| Mode | RESTCONF |
|------|----------|
| `bootstrap` | Yes |
| `audit` + operator said `refresh` / `audit` / `compare` / `diff` / `check NetBox` | Yes |
| `audit` + unnamed and seed **differs** | Yes |
| `audit` + unnamed and seed **matches** | No — compare seed to snap only |
| `reconcile` | Yes if any approved row is interface / IP / cable / `primary_ip4`; else NetBox ids from the snap |

GET JSON is not a NetBox body. No PUT/PATCH/DELETE/save/SSH on IOS-XE.

## `bootstrap`

Create missing only. Sequence: [populate.md](populate.md) steps 1–10 with
**create**, never **update** of an existing snap/`id`.

- Missing parent → `netbox_manage` create. Existing parent id → leave it.
- Missing device name → `netbox_bulk` create. Device id present → skip that row.
- Missing interface name on a known device → `netbox_bulk` create. Known
  `device`+`name` → skip (do not `update` description, enabled, or type).
- Missing IPv4 on an interface → `netbox_bulk` create. Existing `ip_id` → skip.
- Missing CDP pair (both ends in seed, not already cabled) → create cable.
  Existing cable id / unordered pair → skip.
- `primary_ip4` null and a static IPv4 exists → `netbox_manage` update that
  field only. Already set → skip (curated).
- No `netbox_delete`. No bulk update of existing interface/IP/cable rows.

HTTP 404 on a snap id → one `netbox_find` for that object, rewrite the id,
continue. Do not treat 404 as license to refresh the whole device.

After writes: snap + state, `mode` = `bootstrap`, set `netbox_pushed_at`.

## `audit`

Read-only against NetBox.

Allowed: workspace reads, `iosxe_get_platform_and_yang` and
`iosxe_restconf_get` (when GET required), `netbox_test_connection`,
`netbox_find`, `netbox_get`.

Forbidden: `netbox_manage`, `netbox_bulk`, `netbox_delete`.

Compare, then put each difference in `gaps[]` (one line each):

| Observation | Gap if |
|-------------|--------|
| Seed name | in prod.json `tag:simulate`, missing in snap/NetBox |
| Snap/NetBox name | in NetBox, not in seed |
| Interface | live name missing in NetBox, or enabled/cidr differs |
| IPv4 | live static primary ≠ NetBox `address` on that iface |
| Cable | CDP pair in seed missing in NetBox, or NetBox pair not in CDP |
| `primary_ip4` | pick-order (populate.md) ≠ NetBox device primary |

Do not invent DHCP leases. Empty Loopback is not an IP.

Rewrite snap envelope only: `updated_at`, `headline`, `status`, `gaps`,
`mode` = `audit`. Keep all ids. Do **not** change `netbox_pushed_at`.
Then write `state/netbox.json` the same way (`links[]` still from snap
cables). Zero live/NetBox diffs and seed matches → `ok`. Any diff → `gaps`.
RESTCONF failure → `gaps` (name the host). Do not create interfaces from a
failed GET.

## `reconcile`

Approved set (required before any write):

1. Operator listed the rows this turn, or
2. Operator said apply/reconcile **and** current `state/netbox.json` `gaps`
   is a non-empty list from a prior audit.

Neither → run **`audit`** instead (no writes). `Next:` name the diffs to
apply. Do not write NetBox.

Apply only those rows. Create missing as in bootstrap. Update existing
(`netbox_bulk` `update` with snap `id`) only when that object is in the
approved set. `netbox_delete` only when the operator named a delete and
passed `confirm=true`. Unapproved extra cables/IPs in NetBox stay.

Cable/IP/interface mapping: [populate.md](populate.md) / [sot-from-iosxe.md](sot-from-iosxe.md).
`primary_ip4` pick order: populate.md.

After writes: snap + state, `mode` = `reconcile`, set `netbox_pushed_at`.

## Fail if

- You write NetBox during `audit`.
- You treat `refresh` or a board reset as `bootstrap` or `reconcile`.
- You `netbox_bulk` `update` an existing id during `bootstrap`.
- You reconcile with an empty approved set.
- GET is required and you skip `iosxe_restconf_get`.
- You omit `mode` on snap or state.
