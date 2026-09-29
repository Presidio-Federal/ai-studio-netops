# Compile — `state/relationships.json`

You copy edges out of columns other writers already filled. You do
not decide whether two things are related; the row you are reading
already says so. If a rule below does not name a column, there is
no edge.

Schema: `schemas/relationships-state.schema.json`. Example:
`examples/relationships-state.example.json`.

## 1. Read (fixed list, this order, twelve at most)

| # | Path | Take | Watermark |
|---|------|------|-----------|
| 1 | `state/relationships.json` (prior) | `edges[]`, `drift[]`, `watermarks`, `compiled_at` | — |
| 2 | `inventory/topology-observed.json` | `devices[].name`, `probed_at`, `neighbors[]` | `mapped_at` |
| 3 | `health/metadata-iosxe.json` | `iosxe.current[]` rows with `kind` `bgp` | `iosxe.last_collected_at` |
| 4 | `health/metadata-splunk.json` | `splunk.current[]` rows with `kind` `bgp` | `splunk.last_collected_at` |
| 5 | `health/metadata-thousandeyes.json` | `thousandeyes.tests[]`, `thousandeyes.current[]` | `thousandeyes.last_collected_at` |
| 6 | `health/metadata-servicenow.json` | `servicenow.current[]` | `servicenow.last_collected_at` |
| 7 | `state/health.json` | `relations[]`, `updated_at` | `updated_at` |
| 8 | `state/network-ops.json` | `relations[]`, `git.commit_sha`, `status`, `change.devices`, `change.interfaces`, `change.operational_ref`, `updated_at` | `updated_at` |
| 9 | the path in `state/network-ops.json` `change.operational_ref` | `git.commit_sha`, `devices[]`, `interfaces[]`, `updated_at` | `updated_at` |
| 10 | `inventory/prod.json` | `links[]` | `collected_at`, else `snapshot_id`, else `updated_at` |
| 11 | `state/testing.json` | `latest`, `updated_at` | `updated_at` |
| 12 | the path in `state/testing.json` `latest` | `results.ran[]` rows (`device`, `keys`), `updated_at` | `updated_at` |

A path that does not exist goes in `coverage.missing`; keep going.
Never list `health/`, `state/`, or `operational/`. Rows 9 and 12
are the only run records you open — each named by the state file
before it; if that state file is missing or the pointer is null,
skip the run. `coverage.read[]` lists the paths that returned
content, in order.

**No-op check.** After reading, compare every watermark with the
prior file's `watermarks`. All equal (and the prior file exists)
→ write nothing; reply with the no-op line. Any difference, or no
prior file → compile.

## 2. Copy edges

Every rule produces rows `(from, to, rel, basis, sides, source_time,
source_path)`. Key spellings are copied from the column as written;
`interface:` keys are always `interface:<device>/<interface>`.

**Symmetric rels** (`connected_to`, `peers_with`): the two ends
have no direction. Put the alphabetically earlier string in `from`.
Both devices usually report the same cable or peering; that is one
edge with `sides` 2. If only one reports it, `sides` 1.

| Source | Condition | from | rel | to | basis | source_time |
|--------|-----------|------|-----|----|-------|-------------|
| topology `devices[].neighbors[]` | `far` is not null | `local` | `connected_to` | `far` | observed | that device's `probed_at` |
| topology `devices[].neighbors[]` | `far` is null | — no edge (name not in inventory) | | | | |
| iosxe `current[]` `kind` `bgp` | `peer` is not null | `device:<name>` | `peers_with` | `peer` | observed | board `last_collected_at` |
| splunk `current[]` `kind` `bgp` | `peer` is not null | `device:<name>` | `peers_with` | `peer` | observed | board `last_collected_at` |
| TE `current[]` row | `src_device` not null | `test:<test_id>` | `tests` | `device:<src_device>` | observed | board `last_collected_at` |
| TE `current[]` row | `dst_device` not null and differs from `src_device` | `test:<test_id>` | `tests` | `device:<dst_device>` | observed | board `last_collected_at` |
| TE `current[]` row `hops[]` | hop `device` not null | `test:<test_id>` | `traverses` | `device:<device>` | observed | board `last_collected_at` |
| TE `current[]` row `hops[]` | hop `device` and `interface` not null | `test:<test_id>` | `traverses` | `interface:<device>/<interface>` | observed | board `last_collected_at` |
| TE `tests[]` | `service` not null | `test:<test_id>` | `tests` | `service:<service>` | intended | board `last_collected_at` |
| TE `tests[]` | `path` not null | `test:<test_id>` | `traverses` | `device:<name>` for each name in `path` | intended | board `last_collected_at` |
| ServiceNow `current[]` `type` `incident` | `device` column not null | `incident:<number>` | `impacted` | every `device:` key on that row | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `incident` | `interface` column not null | `incident:<number>` | `impacted` | the `interface:` key on that row | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `incident` | `service` column not null and row has a `service:` key | `incident:<number>` | `impacted` | that `service:` key | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `incident` | `rfc` not null | `incident:<number>` | `resolved_by` | `change:<rfc>` | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `change` | `device` column not null | `change:<number>` | `changed` | every `device:` key on that row | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `change` | `interface` column not null | `change:<number>` | `changed` | the `interface:` key on that row | observed | board `last_collected_at` |
| run (row 9) | `git.commit_sha` not null | `change:<commit_sha>` | `changed` | `device:<d>` for each of `devices[]`, `interface:<i>` for each of `interfaces[]` | observed | run `updated_at` |
| `state/network-ops.json` | `status` `merged` and `git.commit_sha` not null | `change:<commit_sha>` | `changed` | `device:<d>` for each `change.devices`, `interface:<i>` for each `change.interfaces` | observed | its `updated_at` |
| `state/health.json` `relations[]` | every row | `from` | `rel` | `to` | asserted | its `updated_at` |
| `state/network-ops.json` `relations[]` | every row | `from` | `rel` | `to` | asserted | its `updated_at` |
| `prod.json` `links[]` | every row | `interface:<a_device>/<a_interface>` | `connected_to` | `interface:<b_device>/<b_interface>` | intended | `collected_at` |
| testing run (row 12) `results.ran[]` | row has a `test:` key and `device` not null | that `test:` key | `tests` | `device:<device>` | observed | run `updated_at` |
| testing run (row 12) `results.ran[]` | row `keys` carry a `control:` key and `device` not null | each `control:` key | `checks` | `device:<device>` | observed | run `updated_at` |

A testing row's `status` (PASS / FAIL / SKIP) stays on the run; the
edge says the check or control was evaluated against the device,
not how it came out. A row in `results.not_applicable[]` produces
nothing.

Never: a `device:` key from a ticket whose typed `device` column is
null (its title keys are prose); a hop with `device` null; a
neighbor with `far` null; a Splunk `config`/`link`/`reload` row;
an edge from a note, headline, `issue`, or `detail` text; a
`service:` key that is not already on the source row; a `control:`
key from `compliance/intel.json` (no device end).

## 3. Upsert against the prior file

Identity is `(from, to, rel, basis)`. For each row produced:

- **Exists in prior `edges[]`:** keep `first_seen`; `last_seen` =
  the newer of prior `last_seen` and this `source_time`;
  `seen_count` + 1; add `source_path` to `sources[]` if absent
  (keep the newest five); `sides` from this compile.
- **New:** `first_seen` = `last_seen` = `source_time`,
  `seen_count` 1, `sources` `[source_path]`.
- **In prior, not produced this compile:** carry it forward
  unchanged (it ages toward stale).

`status` as of `compiled_at`: `observed` → `stale` when
`last_seen` is more than 7 days old; `asserted` → 30 days;
`intended` → always `current`. Over 500 rows: drop `stale` rows,
oldest `last_seen` first, until 500.

## 4. Drift (mechanical)

Only for `connected_to` and `traverses`. Compare `intended` rows
against `current` `observed` rows with the same `(from, to, rel)`.

- `connected_to`: skip entirely when there is no `intended`
  `connected_to` row. Otherwise each intended row with no observed
  match → `intended_not_observed` (`evidence_ref`
  `inventory/prod.json`); each current observed row with no
  intended match → `observed_not_intended` (`evidence_ref`
  `inventory/topology-observed.json`).
- `traverses`: per test, and only for a test whose `tests[].path`
  is not null. Compare at device level only — observed
  `interface:` rows are ignored here. Same two kinds;
  `evidence_ref` `health/metadata-thousandeyes.json`.

`since` = prior drift row's `since` when the same
`(from, to, rel, kind)` was listed, else `compiled_at`. A drift row
whose condition no longer holds is dropped.

## 5. Envelope and write

- `keys` = every `from` and `to` in `edges[]`, deduplicated.
- `status`: `ok` when every path that exists was read; `partial`
  when a path exists but its content could not be used; `unknown`
  when nothing returned content.
- `headline`: counts (edges, current, stale, sources, drift) and
  what is new since the prior `compiled_at` — new edges, newly
  stale edges, new drift. One line. Names, not addresses.
- `next_action`: `none`, or `Review drift[]: <n> rows`.
- `watermarks`: the eleven source values from step 1 (rows 2–12;
  null for a missing path).

`write_file` `state/relationships.json`, replace in full, read it
back. One write.

## Budget

≤ 12 `read_file`, 1 `write_file`, 1 read-back. File ≤ 80 KB for
this lab. No MCP. No `execute_command`.
