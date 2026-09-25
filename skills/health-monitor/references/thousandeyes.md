# ThousandEyes visit — path board

Use on a **ThousandEyes visit** only. Splunk: `references/splunk.md`.
Tools are `te_get_test_results`, `te_list_alerts`, and — on the
baseline or when an agent is unknown — `te_agents_get_agents`.
`account_id`, `window`, `tests[]`, `agents[]` come from
`health/metadata-thousandeyes.json`. Do not put ids in this file.
Do not create tests. Do not use `te_raw_api_call`. Do not read
`inventory/infra-sot.json`.

One test per call. One call per message. Copy numbers; do not
reason about the platform. If a call fails, retry once; a second
failure is that test's row kept from the board and coverage
`partial`.

## Setup (reads, before any TE call)

1. `read_file` `health/metadata-thousandeyes.json` — lookup and the
   **board** (`thousandeyes.current[]`, `series[]`, `visits[]`).
   Missing `account_id` or `tests[]` → `references/metadata.md`
   (resolve), write metadata, then continue.
2. `read_file` `inventory/topology-observed.json` if it exists —
   `devices[].name` + `interfaces[].cidr` resolve an agent IP or a
   `serverIp` to a device. Missing is fine: `src_device` and
   `dst_device` stay null.

Do not open the prior stamp; the board is the prior state.

**Window.** Always `thousandeyes.window` from metadata (default
`1h`). Same window on every visit, first or later. Do not use `7d`
or `24h`. Do not change `window`.

## Calls

**A — agents (baseline, or when `agents[]` is empty, or when a
result names an agent not in `agents[]`).**
`te_agents_get_agents(agent_types=["enterprise"], aid=<account_id>)`.
For each agent: `agent_id` = `agentId`, `agent_name` = `agentName`,
`ip` = the `ipAddresses` entry that falls inside a topology `cidr`
(else the first entry), `device` = that cidr's device (else null).
Write `agents[]` to metadata. Never list agents otherwise.

**N — network results, one call per test in `tests[]`.**
`te_get_test_results(test_id=<test_id>, result_type="network",
window=<window>, aid=<account_id>)`.
The payload has `test.testName`, `test.type`, and `results[]`. Each
result row is one round: `date`, `roundId`, `loss`, `avgLatency`,
`jitter`, `serverIp`, `agent.agentName`, and — only on a failed
round — `errorType`. A round without `errorType` is an **ok round**.
Agent-to-agent tests have `direction`; agent-to-server rows may add
`healthScore`, `minLatency`, `maxLatency` — ignore those.

**L — alerts, once.**
`te_list_alerts(state="trigger", window=<window>, aid=<account_id>)`.
`alerts.firing` = number returned; `items[]` = up to 10 of
`{id, test_id, state}`. Zero can mean no rule is bound to these
tests. It is not proof of health; do not write "no alerts, healthy".

**P and D — the measured path.** Which rows get it this visit:

- **Baseline visit** (board has no `baseline_visit_id`): every row.
- **Every later visit**: rows whose `state` is `degraded` — cap 4,
  worst `loss_pct` first; the rest keep the board's `hops`.
- Any other row: copy `hops` from the board row with the same
  `scope` (null when the board has none). An `ok` row does **not**
  reset `hops` to null; the last measured path stays until it is
  remeasured.

One test at a time. One call per message. P then D per row.

**P** `te_get_test_results(test_id=<test_id>, result_type="path-vis",
window="10m", aid=<account_id>)`. Ten minutes, not the metadata
window: this call only finds the newest round. This summary has no
hop addresses. Take the result rows whose `agent.agentName` equals
this row's `agent`; from the one with the **highest `roundId`** copy
`agent.agentId` and `roundId`. No row for that agent → call P once
more with `window=<window>`; still none → `hops` stays as the board
had it and you do not call D.

**D** `te_get_test_results(test_id=<test_id>,
result_type="path-vis-detail", agent_id=<agent.agentId>,
round_id=<roundId>, aid=<account_id>)`. Read
`results[0].pathTraces[0].hops[]` **in array order** (the API's
`hopNumber` is null; do not read it), at most 16. Each hop is
`{n, ip, device, interface}`: `n` = 1-based position in that
array, `ip` = `ipAddress`. Resolve `ip` against topology
`interfaces[].cidr` the same way as `serverIp`. A containing cidr
sets `device` to that device's `name` and `interface` to that
interface's `name`. No containing cidr: both null. Do not use
`rdns`, `location`, `prefix`, or `network` to name a device. Do not
drop a hop because it did not resolve. A failed D leaves `hops` as
the board had it; the reading still stands.

**`path_devices`** (not stored; used for the diff) = the sequence
of non-null `hop.device` values in `n` order, consecutive
duplicates collapsed. Hop *count* is not compared: unresponsive
hops make it swing round to round.

Order: setup → [A] → N(test 1) → N(test 2) → … → L → build →
P+D for each row that gets a path → diff → write. No
`te_get_alert`, no `te_raw_api_call`, no listing tests when
metadata has them.

## Build rows

One row per **test + agent** in the N payload (agent-to-agent tests
return one agent; a test with several agents returns several — one
row each). Group the rounds by `agent.agentName`, then fill:

| Column | From |
|--------|------|
| `scope` | `test:<test_id>/<agent.agentName>` |
| `test_id`, `name` | metadata `test_id`; `test.testName` |
| `agent` | `agent.agentName` |
| `server` | `serverIp` (same on every round) |
| `src_device` | metadata `agents[]` row with this `agent_name` → `device` |
| `dst_device` | topology device whose `cidr` contains `server`; else metadata `agents[]` row with `ip` = `server` → `device`; else null |
| `keys` | `test:<test_id>`; `device:<src_device>` and `device:<dst_device>` when not null (once when equal); `service:<service>` when metadata sets it. After D, also `device:<hop.device>` and `interface:<device>/<interface>` for each hop that resolved. Deduplicate. At most 16. |
| `at` | newest `date` |
| `ok_rounds` | rounds without `errorType` |
| `error_rounds` | rounds with `errorType`; `error_type` = the one seen most, null when none |
| `loss_pct` | mean of `loss` over ok rounds, rounded to a whole number; null when no ok round |
| `loss_max_pct` | highest `loss` on any ok round |
| `bad_rounds` | ok rounds with `loss` ≥ 5 |
| `latency_ms_avg`, `jitter_ms` | `avgLatency`, `jitter` on the **newest ok round** |
| `first_bad_round_at` | see carry-forward below |
| `state` | rule below |

There is no `type` column on a row (`type` lives on metadata
`tests[]`). **Hops come only from D.** `hops` is null until a D
call has returned for that `scope`, then it is the last measured
list (carried on the board). Do not add a device or interface that
D did not return and topology did not match. An operator may still
declare the expected sequence on metadata `tests[].path`; copy
`path` through and do not write it onto a row. That sequence is
intended. `hops` is the measured path, and it is the edge — no
`relations[]` on this stamp; the Relationship agent reads `hops`.

**`first_bad_round_at` carry-forward.** Let `w` = the oldest `date`
in this window with `loss` ≥ 5 or `errorType` (null when none).

- No bad round in this window → null.
- Board row for this `scope` has a non-null `first_bad_round_at` and
  this window has a bad round → keep the board value (the older one).
- Otherwise → `w`.

So a row that has been bad since before the window keeps its original
onset instead of restarting every hour; the value resets to null only
when a whole window is clean.

**State rule** (fixed, no judgment):
- `degraded` when `ok_rounds` = 0, **or** `bad_rounds` > half of
  `ok_rounds`, **or** `loss_pct` ≥ 5.
- `unknown` when the call failed twice (row copied from the board
  with `state` `unknown`, numbers kept).
- else `ok`.

A test in `tests[]` that returned zero rounds is one row with
`agent` null, every number null, `state` `unknown`, `scope`
`test:<test_id>/none`.

## Diff against the board

Match each built row to `current[]` by `scope`. Only these move a
row onto the stamp:

| Field | Material when | `changed[].field` |
|-------|---------------|-------------------|
| `state` | differs from the board row | `state` |
| `loss_pct` | moved 10 or more points | `loss_pct` |
| `latency_ms_avg` | moved 20 ms or more | `latency_ms_avg` |
| `error_rounds` | was 0 and is now > 0, or `error_type` differs | `error_rounds` |
| `hops` | D ran this visit, the board row already had `hops`, and `path_devices` differs (a device entered or left the resolved sequence, or the order changed) | `hops` |
| row | scope not on the board (new test or new agent) | `row` |

For a `hops` item, `prior` and `current` are the two
`path_devices` sequences joined with `>` (e.g.
`<a>><b>><c>`). A first measurement (board `hops` null) is not a
change. A hop count that moved with the same device sequence is
not a change.

Not material: `loss_max_pct`, `jitter_ms`, `bad_rounds`,
`first_bad_round_at`, `at`, `ok_rounds`, small loss moves, hop
count. Those land on the board only. Loss on this kind of test swings 0–35%
round to round; that is why the loss threshold is 10 points and
`state` uses the majority of rounds.

`changed[]` item: `{keys, field, prior, current, at}` — `prior` from
the board row (null when the row is new), `current` from this row.
`keys` on the item = the row's `keys`.

**Delta.** `first` on the baseline. `worse` if any item is `state`
→ `degraded`, `loss_pct` rising, or `error_rounds` appearing.
`better` if items exist and none is worse. `changed` if only `row`,
`latency_ms_avg`, or `hops` items. `unchanged` if none.

## Stamp or quiet

- Baseline (no `baseline_visit_id`): stamp; every row is a reading;
  `delta` `first`; **`changed` `[]`** (there is no board to diff
  against — do not write one `row` item per reading); `unchanged` 0;
  `prior_watch_id` null.
- `changed[]` non-empty, or coverage not `complete`: stamp; readings
  = the rows that moved (+ rows whose call failed, `state`
  `unknown`).
- Otherwise **quiet**: no stamp. Board only.

Plane `status`: `degraded` when any measured row is `degraded`;
`unknown` when every row is `unknown`; else `ok`. Coverage:
`complete` when every test returned rounds; `partial` when some;
`unavailable` when none (stamp with a single all-null estate metric
row, `readings` `[]`).

## Write

**Stamp** (schema `health-thousandeyes-check`). Top-level fields,
these names and no others:

```json
{
  "keys": [], "schema": "health-thousandeyes-check/v3", "source": "thousandeyes",
  "watch_id": "<YYYY-MM-DDTHH-MM-SSZ>", "checked_at": "<ISO Z>", "ok": true,
  "status": "ok|degraded|unknown", "headline": "...",
  "window": "1h", "window_start": "<oldest date>", "window_end": "<newest date>",
  "coverage": { "state": "complete|partial|unavailable", "detail": "..." },
  "metrics": [ { "at": "...", "scope": "estate", "tests": 3, "rows": 4, "degraded_rows": 2,
                 "worst_loss_pct": 19, "worst_scope": "test:<id>/<agent>", "error_rounds": 0, "alerts_firing": 0 } ],
  "readings": [ { "...row columns...", "hops": [ { "n": 1, "ip": "...", "device": "...", "interface": "..." } ], "note": "..." } ],
  "unchanged": 0, "baseline_ref": null,
  "alerts": { "firing": 0, "items": [] },
  "vs_prior": { "prior_watch_id": null, "delta": "first", "changed": [] },
  "concerns": [ { "type": "test", "name": "<test_name>", "id": "<test_id>" } ]
}
```

It is `watch_id`, not `visit_id`. `coverage` is an object. The
metric row is `rows` and `error_rounds` (not `rows_measured`,
`rows_total`, `error_rounds_total`) and carries `at`. `readings` =
moved rows + `hops` + `note`. `hops` is null, or the last measured
list `[{n, ip, device, interface}]`. There is **no `relations`**
key on this stamp. `metrics` = one `estate` row: `tests` (metadata count),
`rows` measured, `degraded_rows`, `worst_loss_pct` + `worst_scope`,
`error_rounds` sum, `alerts_firing`. `unchanged` = board rows not
replaced. `baseline_ref` = `health/thousandeyes/<baseline_visit_id>.json`
(null on the baseline). `window_start` / `window_end` = oldest /
newest `date` seen. `headline`: test, direction, loss / latency /
rounds, since when; then rows unchanged and alerts firing.
`concerns`: one `{type: test, name, id}` per degraded row.

`note` is one or two sentences about **this row against its board
row**: which direction, since when (`first_bad_round_at`), whether
the reverse test agrees, whether latency moved with the loss. Not
the columns again. Do not list hops or addresses in the note; they
belong on `hops`. Do not name a cause, a probe protocol, or a
device that is not `src_device`, `dst_device`, or a resolved hop.
Do not conclude across tests. No addresses in prose.

`hops` is the edge. Do not write `relations[]` for it, on the stamp
or the board; the Relationship agent turns `hops` into `traverses`
edges and compares them with `tests[].path`. Row `keys` gain
`device:<hop.device>` and `interface:<hop.device>/<hop.interface>`
for each resolved hop, so a reader can join a hop to a device row
on another board. When replacing a board row you did not remeasure,
copy its `hops` through.

**Board** (schema `health-metadata-thousandeyes`) — every visit:
- `current[]` ← built rows replace rows with the same `scope`;
  rows for tests that failed are kept as they were; cap 32.
- `series[]` ← append the estate metric row; keep 10.
- `visits[]` ← append `{watch_id (null when quiet), checked_at,
  status, coverage, delta, stamp_written, window}`; keep 10.
- `agents[]` ← rewritten only when call A ran.
- `tests[].test_name` / `type` ← from the payload when null.
  `service` and `path` copied through, never set by you (write
  `null` when absent).
- `last_collected_at` ← `checked_at`. `last_visit_id` ← this
  `watch_id` only when a stamp was written. `baseline_visit_id` ←
  this `watch_id` on the first visit.
- `keys` ← union of keys on `current[]`.

Write the stamp first (when due), `read_file` it, prune to 10
stamps in `health/thousandeyes/` only, then write the board.

## Budget

| Item | Max |
|------|----:|
| Workspace reads | 3 |
| Workspace writes | 3 (stamp, board, prune) |
| `te_get_test_results` network | one per metadata test, one retry each |
| `te_get_test_results` path-vis | every row on the baseline; then one per degraded reading, max 4; one retry with the metadata window when `10m` returns no row |
| `te_get_test_results` path-vis-detail | one per path-vis that returned a roundId |
| `te_list_alerts` | 1 |
| `te_agents_get_agents` | 1 (baseline / unknown agent only) |

## Reply

Stamp written:

```text
Visit: thousandeyes
Result: <ok | degraded | unknown>
Coverage: <complete|partial|unavailable>
Window: <window> (<window_start> -> <window_end>)
Wrote: health/thousandeyes/<stamp>.json
Trend: <delta>
Findings:
- <test name> <agent> -> <server or dst_device>: <state>, loss <loss_pct>% (max <loss_max_pct>%), <ok_rounds> ok / <error_rounds> error rounds, since <first_bad_round_at>
Alerts: <firing> firing
Next: none
```

Quiet:

```text
Visit: thousandeyes
Result: <ok | degraded>
Coverage: complete
Window: <window> (<window_start> -> <window_end>)
Wrote: health/metadata-thousandeyes.json (no material change)
Trend: unchanged
Board: <n> rows, <k> degraded, last stamp <last_visit_id>
Next: none
```
