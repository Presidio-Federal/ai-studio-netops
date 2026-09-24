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

Order: setup → [A] → N(test 1) → N(test 2) → … → L → build → diff
→ write. Nothing else. No path-vis, no `te_get_alert`, no listing
tests when metadata has them.

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
| `keys` | `test:<test_id>`; `device:<src_device>` and `device:<dst_device>` when not null; `service:<service>` when metadata sets it |
| `at` | newest `date` |
| `ok_rounds` | rounds without `errorType` |
| `error_rounds` | rounds with `errorType`; `error_type` = the one seen most, null when none |
| `loss_pct` | mean of `loss` over ok rounds, rounded to a whole number; null when no ok round |
| `loss_max_pct` | highest `loss` on any ok round |
| `bad_rounds` | ok rounds with `loss` ≥ 5 |
| `latency_ms_avg`, `jitter_ms` | `avgLatency`, `jitter` on the **newest ok round** |
| `first_bad_round_at` | oldest `date` with `loss` ≥ 5 or `errorType`; null when none |
| `state` | rule below |

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
| row | scope not on the board (new test or new agent) | `row` |

Not material: `loss_max_pct`, `jitter_ms`, `bad_rounds`,
`first_bad_round_at`, `at`, `ok_rounds`, small loss moves. Those
land on the board only. Loss on this kind of test swings 0–35%
round to round; that is why the loss threshold is 10 points and
`state` uses the majority of rounds.

`changed[]` item: `{keys, field, prior, current, at}` — `prior` from
the board row (null when the row is new), `current` from this row.

**Delta.** `first` on the baseline. `worse` if any item is `state`
→ `degraded`, `loss_pct` rising, or `error_rounds` appearing.
`better` if items exist and none is worse. `changed` if only `row`
or `latency_ms_avg` items. `unchanged` if none.

## Stamp or quiet

- Baseline (no `baseline_visit_id`): stamp; every row is a reading;
  `delta` `first`; `unchanged` 0.
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

**Stamp** (schema `health-thousandeyes-check`): `readings` = moved
rows + `note`. `note` is the opinion against the board row: which
direction, since when (`first_bad_round_at`), whether the reverse
test agrees, whether latency moved with the loss (congestion) or
did not (a drop on the path). Not the columns again. `metrics` =
one `estate` row: `tests` (metadata count), `rows` measured,
`degraded_rows`, `worst_loss_pct` + `worst_scope`, `error_rounds`
sum, `alerts_firing`. `unchanged` = board rows not replaced.
`baseline_ref` = `health/thousandeyes/<baseline_visit_id>.json`.
`window_start` / `window_end` = oldest / newest `date` seen.
`headline`: test, direction, loss / latency / rounds, since when;
then rows unchanged and alerts firing. `concerns`: one
`{type: test, name, id}` per degraded row.

**Board** (schema `health-metadata-thousandeyes`) — every visit:
- `current[]` ← built rows replace rows with the same `scope`;
  rows for tests that failed are kept as they were; cap 32.
- `series[]` ← append the estate metric row; keep 10.
- `visits[]` ← append `{watch_id (null when quiet), checked_at,
  status, coverage, delta, stamp_written, window}`; keep 10.
- `agents[]` ← rewritten only when call A ran.
- `tests[].test_name` / `type` ← from the payload when null.
  `service` copied through, never set by you.
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
| `te_get_test_results` | one per metadata test, one retry each |
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
