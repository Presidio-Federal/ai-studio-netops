# Live check format

One YAML file per check at `tests/live/checks/<suite>/<id>.yml`. **The filename
stem must equal the `id`** — the smoke gate derives ids from filenames.

Suites come from `live_suites` in `tests/CAPABILITIES.yml`: `reachability`,
`routing`, `path`, `compliance`. Only the first three run by default; `compliance`
is opt-in.

## Shape

```yaml
category: routing
description: BGP receiving prefixes from at least one neighbor (CM-6)
platforms:
  - iosxe
  - cat9kv
assert: genie_parser
parser: show_bgp_summary
expect:
  min_established: 1
  min_prefixes: 1
nist:
  - CM-6
stig:
  - CISC-RT-000050
# From compliance/intel.json: nist_sp_800_53 and disa_footnote. Titles only.
'on':
  tags:
    - edge
    - wan
id: bgp-receiving-prefixes
suite: routing
```

`on` needs quoting in YAML — bare `on` parses as boolean true.

Do not add a check for a protocol or feature that is not in
`inventory/configs/`. A regex that passes when the section is empty
is not a test.

## Fields

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | matches the filename stem |
| `suite` | yes | from `live_suites` |
| `category` | yes | from `live_categories` |
| `description` | yes | what is proven and why, with the control in parentheses |
| `assert` | yes | from `assert_types` — anything else is silently skipped |
| `platforms` | yes | from `platforms`; the check is skipped on others |
| `on.tags` | yes | device roles from `test_groups`. **This is the selector** |
| `expect` | depends | required by `genie_parser`, thresholds and matches |
| `parser` | for `genie_parser` | from `genie_parsers` |
| `nist` / `stig` | optional | control ids; required to wire into the bridge |

## Choosing the assert

| Requirement | `assert` |
|-------------|----------|
| the device answers at all | `device_reachable` |
| a show command contains text | `show_contains` |
| command output contains / matches | `output_contains`, `output_matches` |
| output is non-empty | `output_not_empty` |
| an interface is up | `interface_up` |
| BGP neighbors are up | `bgp_neighbors_up` |
| structured parse with thresholds | `genie_parser` |
| running config contains text | `config_contains` |
| reachability to a target | `ping` |

`config_contains` reads the config off the **live device**, which is different
from a static rule reading the committed file. Use it when you care whether the
running device has drifted from what git says.

## on.tags is the most common mistake

`on.tags` decides which devices run the check. Too narrow and it matches nothing —
`NOT SELECTED`, which looks like a clean run. Too broad and it runs on devices
where the assertion cannot hold — `MIXED`.

Tags are device roles: `common`, `edge`, `wan`, `gateway`, `firewall`,
`compliance`. Check which roles actually exist in the lab before choosing.

## Path checks

Checks in the `path` suite target entries in
`tests/live/paths/site_targets.yml`. Add the target there first — validation
fails on a path check pointing at an unknown target.

## Smoke it alone

The gate sets `CHECK_IDS` so only your check runs. Locally:

```bash
CHECK_IDS=my-new-check SUITES=all TAGS=wan bash automation/scripts/run-live.sh
```

Explicit ids bypass the suite filter, so a new `compliance` check still runs
without being in the default suite set.
