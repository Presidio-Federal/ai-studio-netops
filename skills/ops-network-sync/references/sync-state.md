# Sync state

`state/network-sync.json` is a **replaceable coordination projection**.
Schema `network-sync-state/v2`. It is not an accumulating inventory.
Rewrite the object after every invocation. Durable Actions evidence stays
in GitHub (run URL + marker). Do not copy raw job logs or workflow YAML
into the workspace.

Canonical access data lives only in `inventory/prod.json` and
`inventory/dev.json`.

## Correlation (every invocation)

Always set:

| Field | Meaning |
|-------|---------|
| `operation_id` | Stamp for this invocation |
| `operation` | `onboard` `collect-prod` `collect-dev` `sync-prod` `sync-dev` `detect-drift-prod` `detect-drift-dev` `deploy-twin` `reconcile-dev` `author-check-wait` `status-read` |
| `started_at` / `completed_at` | This invocation |

Envelope `status` is the outcome of **this requested operation only**.
A prior `sync_dev` `gaps` or `drift_prod` `failed` must not permanently
poison an unrelated collect. Readers evaluate the subsection for the
action they asked about.

`next_action` is one line or JSON `null`. Never the string `"none"`.

## Publication order

1. Read the canonical inventory (`inventory/<env>.json` if present) and
   current `state/network-sync.json`.
2. Collect source evidence.
3. Merge into the inventory object without discarding unknown or
   user-authored fields.
4. Build, `write_file`, `read_file` back, and validate the inventory JSON.
5. Publish `state/network-sync.json` **last**.
6. `read_file` back and validate state. Prefer
   `validate_network_sync.py pair` so `snapshot_id` matches the file.

If collection or inventory validation fails: do **not** write an
incomplete inventory as current. Preserve last-known-good json. Write
state with a failed `latest_attempt` only.

Never publish state that names a `snapshot_id` different from the
inventory file it points at.

## Inventory slots

Each of `inventories.prod` and `inventories.dev`:

### `latest_attempt`

| Field | Meaning |
|-------|---------|
| `operation_id` | The collect/onboard attempt |
| `attempted_at` / `completed_at` | That attempt |
| `status` | `complete` `partial` `failed` `unavailable` |
| `headline` | One line |
| `coverage` | Required when the attempt failed. `state` `unavailable`; discovered/inspected/accessible **null**, not `0` |

A failed collection updates `latest_attempt` and leaves
`current_snapshot` (and the json file) unchanged.

### `current_snapshot`

Last-known-good published inventory. Null only if that env has never
been published.

| Field | Meaning |
|-------|---------|
| `snapshot_id` | Must equal the file’s `snapshot_id` |
| `path` | `inventory/prod.json` or `inventory/dev.json` |
| `status` | `complete` or `partial` (never failed) |
| `collected_at` / `expires_at` | Copied from the file |
| `device_count` / `accessible_count` | Copied from the file |
| `coverage` | Copied from the file |

If `now >= expires_at`, the snapshot is **stale**: inspect only; do not
treat as current access.

## Actions sections

After a workflow you triggered or a completed status read, store a
completed-run object — never infer success from the GitHub green check.
Judge `result` from the job-log report marker (`github-actions-mcp`).

A completed object **requires** `workflow`, `environment`, `result`,
`run_id`, `html_url`, `updated_at`. If that workflow has never completed,
the section is JSON `null`.

Allowed `result` values (separate per workflow):

| Workflow | State key | Result words |
|----------|-----------|--------------|
| `sync-prod.yml` | `sync_prod` | `ok` · `gaps` · `failed` |
| `sync-dev.yml` | `sync_dev` | `ok` · `gaps` · `failed` |
| `detect-drift.yml` lab=prod | `drift_prod` | `in_sync` · `drift` · `failed` |
| `detect-drift.yml` lab=dev | `drift_dev` | `in_sync` · `drift` · `failed` |
| `deploy-twin.yml` | `deploy_twin` | `deployed` · `gaps` · `failed` |
| `reconcile-dev.yml` | `reconcile_dev` | `in_sync` · `synced` · `partial` · `failed` |

After a successful named `deploy-twin` or `reconcile-dev` (Twin asked you
to run it), refresh Dev inventory before you close — PAT ports changed.

`author-check.yml`: wait, never trigger. Do not store an Actions section
for it unless you add a future key; report in envelope + `operation`
`author-check-wait`.

## Envelope status (this operation)

Map **this** `operation` only:

- this collect failed → `failed`
- this Actions marker `failed` → `failed`
- this collect `partial` or this marker `gaps` / `drift` / `partial` → `gaps` or `partial`
- else `ok`

Do not fold unrelated historical subsections into envelope `status`.

`next_action` after inventory collect may name Ops NetBox SoT (seed mismatch).
After `sync-prod.yml` it must be `null`.

## Merge of state

1. `read_file` the current `state/network-sync.json` if it exists.
2. Keep untouched env slots and Actions sections unless this operation
   updates them. Never add or preserve `infra_sot` here.
3. Set correlation, envelope, `gaps`, `next_action` for **this** operation.
4. `write_file` the full object (replace, not patch) **after** inventory
   is valid (or after a failed collect that did not rewrite inventory).

## NetBox is a different state file

Do not write `state/netbox.json` or `inventory/infra-sot.json`.
That selection lives on `inventory/prod.json` / `dev.json`. Twin reads
those files + `state/netbox.json`. You may compare prod.json simulate
seed to snap `seed` only to decide whether to **invoke** Ops NetBox SoT
(inventory collect only).
