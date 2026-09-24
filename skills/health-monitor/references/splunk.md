# Splunk visit — syslog board

Use on a **Splunk visit** only. ThousandEyes: `references/thousandeyes.md`.
Tool is `splunk_search`. `index` and `sourcetype` come from
`health/metadata-splunk.json`; substitute them into every search.
Never `index=*`. Never put `earliest=` in SPL — the window goes in
the MCP `earliest_time` / `latest_time` arguments. `max_results` 200.

Syslog events have `_raw` and `host`; they do **not** have `severity`
or `log_level`. Facility, severity, mnemonic come from
`%FACILITY-SEV-MNEMONIC` in `_raw`. The SPL below already extracts
everything you need. **Copy each search exactly.** Do not add, drop,
or reorder pipes. Do not write new SPL.

## Setup (reads, before any search)

1. `read_file` `health/metadata-splunk.json` — lookup, watermark, and
   the **board** (`splunk.current[]`, `series[]`, `visits[]`).
   Missing ids → `references/metadata.md` (resolve), then continue.
2. `read_file` `inventory/prod.json` — device names.
3. `read_file` `inventory/topology-observed.json` if it exists —
   `devices[].name` + `interfaces[].cidr` resolve a syslog host
   address or a BGP neighbor address to a device. Missing is fine:
   then only the parsed hostname resolves.

Do not open the prior stamp; the board is the prior state.

**Window.** `collected_through` set → `earliest_time` =
`collected_through`, `latest_time` = `now`. Not set → baseline: run
S0 first and use its `oldest` as `earliest_time`. Never `-24h`.

## Searches

**S0 — baseline only.** Oldest event still stored.

```
index=<index> sourcetype=<sourcetype>
| stats min(_time) as oldest
| eval oldest=strftime(oldest,"%Y-%m-%dT%H:%M:%SZ")
```

**S1 — per-host bucket counts. Always.** One row per host and
bucket. This is the `metrics` row and the `series[]` row.

```
index=<index> sourcetype=<sourcetype>
| rex field=_raw "%(?<facility>[A-Z0-9_]+)-(?<sev>\d+)-(?<cisco_mn>[A-Z0-9_]+)"
| rex field=_raw "\d+: (?<ios_hostname>[A-Za-z][A-Za-z0-9._-]*): \*?[A-Z][a-z]{2} +\d"
| eval bucket=case(cisco_mn="ADJCHANGE" OR cisco_mn="NBR_RESET","bgp", facility="LINEPROTO" OR facility="LINK","link", facility="SYS" AND cisco_mn="CONFIG_I","config", facility="SYS" AND (cisco_mn="RELOAD" OR cisco_mn="RESTART"),"reload", match(cisco_mn,"^IPACCESSLOG"),"acl", cisco_mn="LOGIN_SUCCESS" OR cisco_mn="AUTH_PASSED","auth_ok", cisco_mn="LOGIN_FAILED" OR cisco_mn="AUTH_FAILED","auth_failed", cisco_mn="NO_MATCH","ssh_no_match", isnull(cisco_mn),"unparsed", 1=1,"other")
| stats count, max(_time) as last_at, values(ios_hostname) as ios_hostname by host, bucket
| eval last_at=strftime(last_at,"%Y-%m-%dT%H:%M:%SZ")
| sort host bucket
```

**S2 — material subjects. Always.** One row per host, kind, subject.
This is the `readings` row and the board row. Zero rows on a quiet
window is normal.

```
index=<index> sourcetype=<sourcetype> ("ADJCHANGE" OR "NBR_RESET" OR "LINEPROTO" OR "%LINK-" OR "SYS-5-CONFIG_I" OR "SYS-5-RELOAD" OR "SYS-5-RESTART" OR IPACCESSLOG* OR "LOGIN_FAILED" OR "AUTH_FAILED")
| rex field=_raw "%(?<facility>[A-Z0-9_]+)-(?<sev>\d+)-(?<cisco_mn>[A-Z0-9_]+)"
| rex field=_raw "\d+: (?<ios_hostname>[A-Za-z][A-Za-z0-9._-]*): \*?[A-Z][a-z]{2} +\d"
| rex field=_raw "[Nn]eighbor (?<neighbor_ip>[0-9a-fA-F.:]+) (?<bgp_state>Up|Down|active reset|passive reset) ?(?<bgp_reason>.*)"
| rex field=_raw "Interface (?<intf>[^,]+), changed state to (?<link_state>[a-z ]+)"
| rex field=_raw "Configured from (?<via>\S+) by (?<user>[^\s,]+)(?: on (?<line>\S+))?(?: \((?<source_ip>[^)]+)\))?"
| rex field=_raw "\[user: (?<auth_user>[^\]]+)\] \[Source: (?<auth_ip>[^\]]+)\]"
| rex field=_raw "list (?<acl>\S+) (?<acl_action>denied|permitted)"
| rex field=_raw "Reload Reason: (?<reload_reason>[^.]+)"
| eval kind=case(cisco_mn="ADJCHANGE" OR cisco_mn="NBR_RESET","bgp", facility="LINEPROTO" OR facility="LINK","link", facility="SYS" AND cisco_mn="CONFIG_I","config", facility="SYS" AND (cisco_mn="RELOAD" OR cisco_mn="RESTART"),"reload", match(cisco_mn,"^IPACCESSLOG"),"acl", cisco_mn="LOGIN_FAILED" OR cisco_mn="AUTH_FAILED","auth_failed", 1=1,null())
| where isnotnull(kind)
| eval subject=case(kind="bgp",neighbor_ip, kind="link",intf, kind="config",coalesce(user,"unknown"), kind="reload",cisco_mn, kind="acl",acl, kind="auth_failed",coalesce(auth_user,"unknown"))
| eval state=case(kind="bgp",coalesce(bgp_state,"reset"), kind="link",link_state, kind="acl",acl_action, 1=1,null())
| eval src=coalesce(source_ip,auth_ip)
| eval detail=case(kind="bgp",bgp_reason, kind="reload",reload_reason, kind="config",coalesce(line,via), 1=1,null())
| stats count, max(_time) as at, latest(state) as state, latest(src) as source_ip, latest(detail) as detail, values(ios_hostname) as ios_hostname by host, kind, subject
| eval at=strftime(at,"%Y-%m-%dT%H:%M:%SZ")
| sort host kind subject
```

A search that fails is retried **once**. S1 failing again →
`unavailable`, null metrics, watermark not advanced. S2 failing with
S1 good → `partial`, readings `[]`.

Nothing else. No `head`-sampled raw events, no `by severity`, no
third search, no follow-up on a mnemonic you found interesting.

## Resolve a host to a device

For each S1/S2 `host`, in this order; stop at the first hit:

1. `ios_hostname` equals a `prod.json` `devices[].name`
   **case-insensitively** → that name.
2. `host` equals the address part of any
   `topology-observed.json` `devices[].interfaces[].cidr` → that
   device's name.
3. `host` equals `access.restconf.host` or `access.ssh.host` on a
   `prod.json` device → that name.
4. No match → `name` = `host` as logged, `scope` `host:<host>`,
   `keys []`. Do not guess.

Write the `prod.json` spelling. One device is one row even when it
logs from two addresses: sum the S1 counts, keep the latest S2 row
per kind + subject.

## Build the rows

**Metric row** per resolved device (from S1): `events` = sum of every
bucket; `bgp_events` `link_events` `config_events` `reload_events`
`acl_events` `auth_ok` `auth_failed` `ssh_no_match` = that bucket's
count or 0. `scope` `device:<name>`.

**Reading / board row** per S2 result row: `name`, `kind`, `subject`,
`count`, `at`, `state`, `source_ip`, `detail` copied. `peer` (bgp
only): the device whose `topology-observed.json` interface address
equals `subject`, else null. `keys`: `device:<name>`; plus
`interface:<name>/<subject>` on a link row; plus the `peer` key on a
resolved bgp row; `[]` when the host is unresolved.

## Diff against the board

Match an S2 row to `splunk.current[]` by `name` + `kind` + `subject`.
Every S2 row is a `vs_prior.changed[]` item (syslog is events; an
event is a change):

| kind | `field` | `prior` | `current` |
|------|---------|---------|-----------|
| bgp | `bgp_state` | board `state` or null | `state` |
| link | `link_state` | board `state` or null | `state` |
| config | `config` | board `at` or null | `<subject> via <detail> from <source_ip>` |
| reload | `reload` | board `at` or null | `detail` |
| acl | `acl` | board `at` or null | `<state> x<count>` |
| auth_failed | `auth_failed` | board `at` or null | `<subject> from <source_ip> x<count>` |

`at` = the row's `at`.

`delta`: `worse` when any item is a bgp `Down`/reset, a link `down`
(not `administratively down`), a reload, or an auth_failed; `better`
when items are only `Up`/`up` and nothing worse; `changed` when
only config, acl, or administratively down; `unchanged` when S2 was
empty; `first` when there is no board.

**Stamp or quiet.** Write a stamp when: no board (first visit), S2
returned at least one row, or coverage ≠ `complete`. Otherwise the
visit is **quiet**: no stamp; board only.

## Plane status

`degraded` when any S2 row has bgp `state` `Down`/`active reset`/
`passive reset`, link `state` `down`, or kind `reload`. Config, ACL
logs, admin-down, failed auth, and SSH NO_MATCH never degrade on
their own — they are `changed` and, for failed auth and reload,
`concerns`. `unknown` when S1 failed.

## Write

**Stamp** (schema `health-splunk-check`): `readings` = every S2 row +
`note`. `note` is the opinion against the board: new subject vs
flap vs recovered (compare `state` and `count` to the board row),
who committed from where and whether it looks interactive (`vty`,
an operator address) or pipeline (`console`), why it reloaded.
Not the columns again. `unchanged` = board rows not replaced.
`baseline_ref` = `health/splunk/<baseline_visit_id>.json`.
`headline`: device, subject, state or user, when; then devices
logged and unchanged count. `concerns`: devices with a bgp
Down/reset, non-admin link down, reload, or auth_failed.

**Board** (schema `health-metadata-splunk`) — every visit:
- `current[]` ← S2 rows replace rows with the same
  `name`+`kind`+`subject`; others kept (cap 120, drop oldest `at`).
- `series[]` ← append one `estate` row (sums over S1); keep 10.
- `visits[]` ← append `{watch_id (null when quiet), checked_at,
  status, coverage, delta, stamp_written, window_start,
  window_end}`; keep 10.
- `collected_through` ← the latest S1 `last_at` when events exist,
  else `checked_at`. Never backward. Not on `unavailable`.
- `last_collected_at` ← `checked_at`. `last_visit_id` ← this
  `watch_id` only when a stamp was written. `baseline_visit_id` ←
  this `watch_id` on the first visit.
- `keys` ← union of keys on `current[]`.

## Budget

| Item | Max |
|------|----:|
| Workspace reads | 4 |
| Workspace writes | 3 (stamp, board, prune) |
| `splunk_search` | 3 (4 on the baseline) |

## Reply

Stamp written:

```text
Visit: splunk
Result: <ok | degraded | unknown>
Coverage: <complete|partial|unavailable>
Window: <window_start> -> <window_end>
Wrote: health/splunk/<stamp>.json
Trend: <delta>
Findings:
- <device> <kind> <subject> <state|user> at <at>
Next: none
```

Quiet:

```text
Visit: splunk
Result: ok
Coverage: complete
Window: <window_start> -> <window_end>
Wrote: health/metadata-splunk.json (no material event)
Trend: unchanged
Board: <n> rows, last stamp <last_visit_id>
Next: none
```
