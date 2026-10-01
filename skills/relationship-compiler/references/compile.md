# Compile — `state/relationships.json`

You copy edges out of columns other writers already filled. You do
not decide whether two things are related; the row you are reading
already says so. If a rule below does not name a column, there is
no edge.

Schema: `schemas/relationships-state.schema.json`. Example:
`examples/relationships-state.example.json`.

## 1. Read (fixed list, this order, fifteen at most)

| # | Path | Take | Watermark |
|---|------|------|-----------|
| 1 | `state/relationships.json` (prior) | `edges[]`, `drift[]`, `watermarks`, `compiled_at` | — |
| 2 | `inventory/topology-observed.json` | `devices[].name`, `probed_at`, `neighbors[]` | `mapped_at` |
| 3 | `health/metadata-iosxe.json` | `iosxe.current[]` rows with `kind` `bgp` | `iosxe.last_collected_at` |
| 4 | `health/metadata-splunk.json` | `splunk.current[]` rows with `kind` `bgp` | `splunk.last_collected_at` |
| 5 | `health/metadata-netflow.json` | `netflow.current[]` rows with `kind` `conversation` | `netflow.last_collected_at` |
| 6 | `health/metadata-application.json` | `application.current[]` rows with `kind` `probe`, `container`, `host` | `application.last_collected_at` |
| 7 | `inventory/applications.json` | `applications[]` rows (`name`, `service`, `hosts[]`, `depends_on[]`) | `updated_at` |
| 8 | `health/metadata-servicenow.json` | `servicenow.current[]` | `servicenow.last_collected_at` |
| 9 | `state/health.json` | `relations[]`, `updated_at` | `updated_at` |
| 10 | `state/network-ops.json` | `relations[]`, `git.commit_sha`, `status`, `change.devices`, `change.interfaces`, `change.operational_ref`, `updated_at` | `updated_at` |
| 11 | the path in `state/network-ops.json` `change.operational_ref` | `git.commit_sha`, `devices[]`, `interfaces[]`, `updated_at` | `updated_at` |
| 12 | `inventory/prod.json` | `links[]` | `collected_at`, else `snapshot_id`, else `updated_at` |
| 13 | `state/testing.json` | `latest`, `updated_at` | `updated_at` |
| 14 | the path in `state/testing.json` `latest` | `results.ran[]` rows (`device`, `keys`), `updated_at` | `updated_at` |

A path that does not exist goes in `coverage.missing`; keep going.
Rows 5, 6, and 7 are new planes and are often missing on an older
workspace — that is `missing`, not a failure. Never list `health/`,
`state/`, `inventory/`, or `operational/`. Rows 11 and 14 are the
only run records you open — each named by the state file before
it; if that state file is missing or the pointer is null, skip the
run. `coverage.read[]` lists the paths that returned content, in
order.

**No-op check.** After reading, compare every watermark with the
prior file's `watermarks`. All equal (and the prior file exists)
→ write nothing; reply with the no-op line. Any difference, or no
prior file → compile.

## 2. Copy edges

Every rule produces rows `(from, to, rel, basis, sides, source_time,
source_path)`. Key spellings are copied from the column as written;
`interface:` keys are always `interface:<device>/<interface>`;
`application:` keys are the `application` column as written (a
label, never a port, an address, or a container `name`).

**Symmetric rels** (`connected_to`, `peers_with`): the two ends
have no direction. Put the alphabetically earlier string in `from`.
Both devices usually report the same cable or peering; that is one
edge with `sides` 2. If only one reports it, `sides` 1.

**Directed rels** keep the row's direction: `flows_to` is client →
server (`src_device` → `dst_device`); `depends_on` is the thing
that needs → the thing it needs.

| Source | Condition | from | rel | to | basis | source_time |
|--------|-----------|------|-----|----|-------|-------------|
| topology `devices[].neighbors[]` | `far` is not null | `local` | `connected_to` | `far` | observed | that device's `probed_at` |
| topology `devices[].neighbors[]` | `far` is null | — no edge (name not in inventory) | | | | |
| iosxe `current[]` `kind` `bgp` | `peer` is not null | `device:<name>` | `peers_with` | `peer` | observed | board `last_collected_at` |
| splunk `current[]` `kind` `bgp` | `peer` is not null | `device:<name>` | `peers_with` | `peer` | observed | board `last_collected_at` |
| netflow `current[]` `kind` `conversation` | `src_device` and `dst_device` both not null and differ | `device:<src_device>` | `flows_to` | `device:<dst_device>` | observed | board `last_collected_at` |
| netflow `current[]` `kind` `conversation` | `exporter` not null and `src_device` not null and differs from `exporter` | `device:<src_device>` | `traverses` | `device:<exporter>` | observed | board `last_collected_at` |
| netflow `current[]` `kind` `conversation` | `exporter` not null and `dst_device` not null and differs from `exporter` | `device:<dst_device>` | `traverses` | `device:<exporter>` | observed | board `last_collected_at` |
| netflow `current[]` `kind` `exporter` | — no edge (an exporter reporting is a state, not a relation) | | | | | |
| application `current[]` `kind` `probe` | `application` not null | `test:probe/<application>@<vantage_site>` (the row's `test:` key) | `tests` | `application:<application>` | observed | board `last_collected_at` |
| application `current[]` `kind` `probe` | `application` and `site` not null | `application:<application>` | `located_at` | `site:<site>` | observed | board `last_collected_at` |
| application `current[]` `kind` `container` | `application` and `device` not null | `application:<application>` | `depends_on` | `device:<device>` | observed | board `last_collected_at` |
| application `current[]` `kind` `container` | `device` null | — no edge (host not in inventory; the row's `host` is text) | | | | |
| application `current[]` `kind` `host` | `device` and `site` not null | `device:<device>` | `located_at` | `site:<site>` | observed | board `last_collected_at` |
| application `current[]` `kind` `target` | — no edge | | | | | |
| applications.json `applications[]` | `service` not null | `service:<service>` | `depends_on` | `application:<name>` | intended | file `updated_at` |
| applications.json `applications[]` `depends_on[]` | each entry | `application:<name>` | `depends_on` | `application:<entry>` | intended | file `updated_at` |
| applications.json `applications[]` `hosts[]` | each entry | `application:<name>` | `depends_on` | `device:<entry>` | intended | file `updated_at` |
| ServiceNow `current[]` `type` `incident` | `device` column not null | `incident:<number>` | `impacted` | every `device:` key on that row | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `incident` | `interface` column not null | `incident:<number>` | `impacted` | the `interface:` key on that row | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `incident` | `service` column not null and row has a `service:` key | `incident:<number>` | `impacted` | that `service:` key | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `incident` | `rfc` not null | `incident:<number>` | `resolved_by` | `change:<rfc>` | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `change` | `device` column not null | `change:<number>` | `changed` | every `device:` key on that row | observed | board `last_collected_at` |
| ServiceNow `current[]` `type` `change` | `interface` column not null | `change:<number>` | `changed` | the `interface:` key on that row | observed | board `last_collected_at` |
| run (row 11) | `git.commit_sha` not null | `change:<commit_sha>` | `changed` | `device:<d>` for each of `devices[]`, `interface:<i>` for each of `interfaces[]` | observed | run `updated_at` |
| `state/network-ops.json` | `status` `merged` and `git.commit_sha` not null | `change:<commit_sha>` | `changed` | `device:<d>` for each `change.devices`, `interface:<i>` for each `change.interfaces` | observed | its `updated_at` |
| `state/health.json` `relations[]` | every row | `from` | `rel` | `to` | asserted | its `updated_at` |
| `state/network-ops.json` `relations[]` | every row | `from` | `rel` | `to` | asserted | its `updated_at` |
| `prod.json` `links[]` | every row | `interface:<a_device>/<a_interface>` | `connected_to` | `interface:<b_device>/<b_interface>` | intended | `collected_at` |
| testing run (row 14) `results.ran[]` | row has a `test:` key and `device` not null | that `test:` key | `tests` | `device:<device>` | observed | run `updated_at` |
| testing run (row 14) `results.ran[]` | row `keys` carry a `control:` key and `device` not null | each `control:` key | `checks` | `device:<device>` | observed | run `updated_at` |

A testing row's `status` (PASS / FAIL / SKIP) stays on the run; the
edge says the check or control was evaluated against the device,
not how it came out. A row in `results.not_applicable[]` produces
nothing. A NetFlow conversation's `dst_port`, `protocol`, `bytes`,
and `state` stay on the board; the edge says the pair was seen,
not how much or whether it is still present. A probe's `success`
and a container's `state` likewise stay on the board.

Never: a `device:` key from a ticket whose typed `device` column is
null (its title keys are prose); a hop with `device` null; a
neighbor with `far` null; a Splunk `config`/`link`/`reload` row;
a NetFlow row whose `src_device` / `dst_device` / `exporter` is
null (an address is not a device); an `application:` key from a
NetFlow row (it has none), from a container `name`, or from a
container's `service` text; an edge from a note, headline, `issue`,
or `detail` text; a `service:` key that is not already on the
source row (ServiceNow) or in `applications.json` `service`; a
`control:` key from `compliance/intel.json` (no device end).

## 3. Upsert against the prior file

Identity is `(from, to, rel, basis)`. For each row produced:

- **Exists in prior `edges[]`:** keep `first_seen`; `last_seen` =
  the newer of prior `last_seen` and this `source_time`;
  `seen_count` + 1; add `source_path` to `sources[]` if absent
  (keep the newest five); `sides` from this compile.
- **New:** `first_seen` = `last_seen` = `source_time`,
  `seen_count` 1, `sources` `[source_path]`.
- **In prior, not produced this compile:** carry it forward
  unchanged (it ages toward stale). A prior edge whose `sources[]`
  name only a path that no longer exists (for example
  `health/metadata-thousandeyes.json`) is carried the same way; it
  goes stale on its own clock.

`status` as of `compiled_at`: `observed` → `stale` when
`last_seen` is more than 7 days old; `asserted` → 30 days;
`intended` → always `current`. Over 500 rows: drop `stale` rows,
oldest `last_seen` first, until 500.

## 4. Drift (mechanical)

Only for `connected_to` and `depends_on`. Compare `intended` rows
against `current` `observed` rows with the same `(from, to, rel)`.

- `connected_to`: skip entirely when there is no `intended`
  `connected_to` row. Otherwise each intended row with no observed
  match → `intended_not_observed` (`evidence_ref`
  `inventory/prod.json`); each current observed row with no
  intended match → `observed_not_intended` (`evidence_ref`
  `inventory/topology-observed.json`).
- `depends_on`: skip entirely when `inventory/applications.json`
  was not read. Compare only rows whose `to` is a `device:` key
  (application on host); `service:` → `application:` and
  `application:` → `application:` intended rows have no observed
  counterpart yet and produce no drift. Each intended
  `application:<a> depends_on device:<h>` with no current observed
  match → `intended_not_observed` (`evidence_ref`
  `inventory/applications.json`); each current observed one whose
  `application:` is named in `applications.json` but not declared
  on that host → `observed_not_intended` (`evidence_ref`
  `health/metadata-application.json`). An observed application not
  named in `applications.json` at all produces no drift row.

`since` = prior drift row's `since` when the same
`(from, to, rel, kind)` was listed, else `compiled_at`. A drift row
whose condition no longer holds is dropped — including prior
`traverses` drift rows, which no source declares any more.

## 5. Envelope and write

- `keys` = every `from` and `to` in `edges[]`, deduplicated.
- `status`: `ok` when every path that exists was read; `partial`
  when a path exists but its content could not be used; `unknown`
  when nothing returned content.
- `headline`: counts (edges, current, stale, sources, drift) and
  what is new since the prior `compiled_at` — new edges, newly
  stale edges, new drift. One line. Names, not addresses.
- `next_action`: `none`, or `Review drift[]: <n> rows`.
- `watermarks`: the thirteen source values from step 1 (rows 2–14;
  null for a missing path).

`write_file` `state/relationships.json`, replace in full, read it
back. One write.

## Budget

≤ 15 `read_file`, 1 `write_file`, 1 read-back. File ≤ 80 KB for
this lab. No MCP. No `execute_command`.
