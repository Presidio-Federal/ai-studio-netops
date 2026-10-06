# Splunk visit — syslog board

The health check runs `scripts/visit_splunk.py`. This file is the
rules that script implements. Use the manual order below only when
stderr says `hai_mcp unavailable`.

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
2. `read_file` `inventory/prod.json` — device names and `platform`.
   The **expected set** is every device whose `platform` is not
   `linux` (`iosxe`, `nxos`, `asa`); hosts do not syslog here.
3. `read_file` `inventory/topology-observed.json` if it exists —
   `devices[].name` + `interfaces[].cidr` resolve a syslog host
   address or a BGP neighbor address to a device. Missing is fine:
   then only the parsed hostname resolves.

Do not open the prior stamp; the board is the prior state.

**Window.** `collected_through` set → `earliest_time` =
`collected_through`, `latest_time` = `now`. Not set → baseline:
`earliest_time` = `-7d`, `latest_time` = `now`. The board is state,
not history; a week is enough to seed it. Never a rolling `-24h` on
a later visit.

## Searches

Both searches group by `dev` = the hostname parsed from the line,
lowercased, or the syslog `host` address when the line carries no
hostname. Three line shapes are parsed: IOS-XE
(`<seq>: HOST: *Mon DD`), ASA (`HH:MM:SS HOST : %ASA-`), and NX-OS
with `logging origin-id hostname` (`HOST: YYYY Mon DD`). An NX-OS
box without origin-id logs no hostname and shows up as its address.
Buckets and kinds cover IOS-XE (`SYS`, `LINEPROTO`, `LINK`,
`IPACCESSLOG*`), NX-OS (`ETHPORT`, `VSHD_SYSLOG_CONFIG_I`,
`PFM_SYSTEM_RESET`, `BGP ADJCHANGE`), and ASA (`411001/2` link,
`111005` end-of-configuration, `106023/106100` ACL, `605004/5`,
`611101/2`, `113005` auth, `199001` reload). ASA `111008/111010`
(every exec command) are deliberately **not** config events. Splunk
does the collapse of one device logging from two addresses; you do
not.

**S1 — per-device bucket counts. Always.** One row per `dev` and
bucket. This is the `metrics` row and the `series[]` row.

```
index=<index> sourcetype=<sourcetype>
| rex field=_raw "%(?<facility>[A-Z0-9_]+)-(?<sev>\d+)-(?<cisco_mn>[A-Z0-9_]+)"
| rex field=_raw "\d+: (?<ios_hostname>[A-Za-z][A-Za-z0-9._-]*): \*?[A-Z][a-z]{2} +\d"
| rex field=_raw "\d{2}:\d{2}:\d{2} (?<asa_hostname>[A-Za-z][A-Za-z0-9._-]*) : %ASA-"
| rex field=_raw " (?<nx_hostname>[A-Za-z][A-Za-z0-9._-]*): \d{4} [A-Z][a-z]{2} +\d"
| eval bucket=case(cisco_mn="ADJCHANGE" OR cisco_mn="NBR_RESET","bgp", facility="LINEPROTO" OR facility="LINK" OR facility="ETHPORT" OR (facility="ASA" AND (cisco_mn="411001" OR cisco_mn="411002")),"link", (facility="SYS" AND cisco_mn="CONFIG_I") OR cisco_mn="VSHD_SYSLOG_CONFIG_I" OR (facility="ASA" AND cisco_mn="111005"),"config", (facility="SYS" AND (cisco_mn="RELOAD" OR cisco_mn="RESTART")) OR cisco_mn="PFM_SYSTEM_RESET" OR (facility="ASA" AND cisco_mn="199001"),"reload", match(cisco_mn,"^IPACCESSLOG") OR (facility="ASA" AND (cisco_mn="106023" OR cisco_mn="106100")),"acl", cisco_mn="LOGIN_SUCCESS" OR cisco_mn="AUTH_PASSED" OR (facility="ASA" AND (cisco_mn="605005" OR cisco_mn="611101")),"auth_ok", cisco_mn="LOGIN_FAILED" OR cisco_mn="AUTH_FAILED" OR (facility="ASA" AND (cisco_mn="113005" OR cisco_mn="605004" OR cisco_mn="611102")),"auth_failed", cisco_mn="NO_MATCH","ssh_no_match", isnull(cisco_mn),"unparsed", 1=1,"other")
| eval dev=lower(coalesce(ios_hostname,asa_hostname,nx_hostname,host))
| eval ingest_delay_s=if(isnotnull(_indextime) AND isnotnull(_time), round(_indextime-_time), null())
| stats count, max(_time) as last_at, max(ingest_delay_s) as ingest_delay_s by dev, bucket
| eval last_at=strftime(last_at,"%Y-%m-%dT%H:%M:%SZ")
| sort dev bucket
```

**S2 — material subjects. Always.** One row per `dev`, kind,
subject. This is the `readings` row and the board row. Zero rows on
a quiet window is normal.

```
index=<index> sourcetype=<sourcetype> ("ADJCHANGE" OR "NBR_RESET" OR "LINEPROTO" OR "%LINK-" OR "SYS-5-CONFIG_I" OR "SYS-5-RELOAD" OR "SYS-5-RESTART" OR IPACCESSLOG* OR "LOGIN_FAILED" OR "AUTH_FAILED" OR "%ETHPORT-" OR "VSHD_SYSLOG_CONFIG_I" OR "PFM_SYSTEM_RESET" OR "%ASA-4-411001" OR "%ASA-4-411002" OR "%ASA-5-111005" OR "%ASA-4-106023" OR "%ASA-6-106100" OR "%ASA-6-113005" OR "%ASA-6-605004" OR "%ASA-6-611102" OR "%ASA-5-199001")
| rex field=_raw "%(?<facility>[A-Z0-9_]+)-(?<sev>\d+)-(?<cisco_mn>[A-Z0-9_]+)"
| rex field=_raw "\d+: (?<ios_hostname>[A-Za-z][A-Za-z0-9._-]*): \*?[A-Z][a-z]{2} +\d"
| rex field=_raw "\d{2}:\d{2}:\d{2} (?<asa_hostname>[A-Za-z][A-Za-z0-9._-]*) : %ASA-"
| rex field=_raw " (?<nx_hostname>[A-Za-z][A-Za-z0-9._-]*): \d{4} [A-Z][a-z]{2} +\d"
| eval dev=lower(coalesce(ios_hostname,asa_hostname,nx_hostname,host))
| rex field=_raw "[Nn]eighbor (?<neighbor_ip>[0-9a-fA-F.:]+) (?<bgp_state>Up|Down|active reset|passive reset) ?(?<bgp_reason>.*)"
| rex field=_raw "Interface (?<intf>[^,]+), changed state to (?<link_state>[a-z ]+)"
| rex field=_raw "Interface (?<nx_intf>\S+) is (?<nx_link_state>up|down)"
| rex field=_raw "Configured from (?<via>\S+) by (?<user>[^\s,]+)(?: on (?<line>\S+))?(?: \((?<source_ip>[0-9a-fA-F.:]+)\))?"
| rex field=_raw "(?<asa_cfg_line>\S+) end configuration: (?<asa_cfg_result>\S+)"
| rex field=_raw "\[user: (?<auth_user>[^\]]+)\] \[Source: (?<auth_ip>[^\]]+)\]"
| rex field=_raw "list (?<acl>\S+) (?<acl_action>denied|permitted) (?<ios_proto>\S+) (?<ios_src>[0-9a-fA-F.:]+)\((?<ios_src_port>\d+)\) -> (?<ios_dst>[0-9a-fA-F.:]+)\((?<ios_dst_port>\d+)\)"
| rex field=_raw "(?i)(?<asa_acl_action>Deny|Permit) (?<asa_proto>\S+) src (?<asa_src_if>[^:]+):(?<asa_src>[0-9a-fA-F.:]+)(?:/(?<asa_src_port>\d+))? dst (?<asa_dst_if>[^:]+):(?<asa_dst>[0-9a-fA-F.:]+)(?:/(?<asa_dst_port>\d+))?.*by access-group \"(?<asa_acl>[^\"]+)\""
| rex field=_raw "access-list (?<asa_acl2>\S+) (?<asa_acl_action2>permitted|denied)"
| rex field=_raw "user = (?<asa_auth_user>\S+)"
| rex field=_raw "Reload Reason: (?<reload_reason>[^.]+)"
| eval kind=case(cisco_mn="ADJCHANGE" OR cisco_mn="NBR_RESET","bgp", facility="LINEPROTO" OR facility="LINK" OR facility="ETHPORT" OR (facility="ASA" AND (cisco_mn="411001" OR cisco_mn="411002")),"link", (facility="SYS" AND cisco_mn="CONFIG_I") OR cisco_mn="VSHD_SYSLOG_CONFIG_I" OR (facility="ASA" AND cisco_mn="111005"),"config", (facility="SYS" AND (cisco_mn="RELOAD" OR cisco_mn="RESTART")) OR cisco_mn="PFM_SYSTEM_RESET" OR (facility="ASA" AND cisco_mn="199001"),"reload", match(cisco_mn,"^IPACCESSLOG") OR (facility="ASA" AND (cisco_mn="106023" OR cisco_mn="106100")),"acl", cisco_mn="LOGIN_FAILED" OR cisco_mn="AUTH_FAILED" OR (facility="ASA" AND (cisco_mn="113005" OR cisco_mn="605004" OR cisco_mn="611102")),"auth_failed", 1=1,null())
| where isnotnull(kind)
| eval subject=case(kind="bgp",neighbor_ip, kind="link",coalesce(intf,nx_intf), kind="config",coalesce(user,asa_cfg_line,"unknown"), kind="reload",cisco_mn, kind="acl",coalesce(asa_acl,acl,asa_acl2,"unknown"), kind="auth_failed",coalesce(auth_user,asa_auth_user,"unknown"))
| eval state=case(kind="bgp",coalesce(bgp_state,"reset"), kind="link",coalesce(link_state,nx_link_state), kind="acl",lower(coalesce(acl_action,asa_acl_action2,asa_acl_action)), 1=1,null())
| eval src=coalesce(asa_src,ios_src,source_ip,auth_ip)
| eval dst=coalesce(asa_dst,ios_dst)
| eval src_port=coalesce(asa_src_port,ios_src_port)
| eval dst_port=coalesce(asa_dst_port,ios_dst_port)
| eval protocol=coalesce(asa_proto,ios_proto)
| eval acl_name=if(kind="acl",subject,null())
| eval iface=coalesce(asa_src_if,asa_dst_if)
| eval actor=if(kind="config",coalesce(user,asa_cfg_line),null())
| eval access_method=if(kind="config",coalesce(line,via),null())
| eval detail=case(kind="bgp",bgp_reason, kind="reload",reload_reason, kind="config",coalesce(line,via,asa_cfg_result), 1=1,null())
| eval ingest_delay_s=if(isnotnull(_indextime) AND isnotnull(_time), round(_indextime-_time), null())
| eval ingested_at=if(isnotnull(_indextime), strftime(_indextime,"%Y-%m-%dT%H:%M:%SZ"), null())
| eval evidence=substr(_raw,1,300)
| stats count, max(_time) as at, latest(state) as state, latest(src) as source_ip, latest(dst) as dst, latest(src_port) as src_port, latest(dst_port) as dst_port, latest(protocol) as protocol, latest(acl_name) as acl, latest(iface) as interface, latest(actor) as actor, latest(access_method) as access_method, latest(detail) as detail, latest(ingest_delay_s) as ingest_delay_s, latest(ingested_at) as ingested_at, latest(evidence) as evidence by dev, kind, subject
| eval at=strftime(at,"%Y-%m-%dT%H:%M:%SZ")
| sort dev kind subject
```

A search that fails is retried **once**. S1 failing again →
`unavailable`, null metrics, watermark not advanced. S2 failing with
S1 good → `partial`, readings `[]`.

**S1 zero rows.** Before calling it a quiet window, one
`splunk_get_indexes`. `splunk.index` is listed → quiet window as
usual. Not listed → the lookup moved: `unavailable`, null metrics,
watermark **not** advanced, reply `Need: index` with the listed
indexes as options, stop. An operator-named index or sourcetype
beats metadata: confirm it with S1, write it
(`provenance.splunk` `user`), finish the visit. Do not re-run the
old search; do not defend the empty result.

S1 uses the board `window` (default `1h`). That bounded window is the
only interval whose bucket counts are comparable to the previous
visit. S2 uses `collected_through` (or `-7d` on the first visit) so
collection is incremental. An S2 count is not a rate and is not
compared with an earlier S2 count.

Each S2 row keeps the latest `_raw` line, trimmed to 300 characters,
as `evidence`. Fields the message does not contain stay null. A
config line has no change reference; `change_ref` stays null.
`at` is the event time (`_time`). `ingested_at` is `_indextime`.
`ingest_delay_s` is the difference for that latest event.

Nothing else. No third search, no `by severity`, no follow-up on a
mnemonic you found interesting.

## Resolve `dev` to a device

For each distinct `dev`, in this order; stop at the first hit:

1. `dev` equals a `prod.json` `devices[].name`
   **case-insensitively** → that name.
2. `dev` is an address equal to the address part of any
   `topology-observed.json` `devices[].interfaces[].cidr` → that
   device's name.
3. `dev` is a key in `splunk.hosts` on the board (an operator-pinned
   `address → prod.json name` map, `references/metadata.md`) → that
   name.
4. `dev` equals `access.restconf.host` or `access.ssh.host` on a
   `prod.json` device → that name.
5. No match → `name` = `dev` as logged, `keys []`, metric `scope`
   `host:<dev>`. Do not guess. List it under `Unresolved:` in the
   reply so the operator can pin it in `splunk.hosts` or enable
   `logging origin-id hostname` on the box.

Write the `prod.json` spelling. Usually every `dev` is a hostname
and this is a spelling lookup. Only a line logged without a
hostname shows up as an address; if such an address resolves to a
device that also has a hostname row, add its S1 counts to that
device's row and, for an S2 row with the same kind + subject, keep
whichever `at` is later.

## Coverage against `prod.json`

After resolving, compare the resolved names with the expected set.
A device in the expected set with **no S1 row** in the bounded window
is listed under no-events. That is not device health. It becomes a
pipeline question only when `source_registry` says `reporting:
expected` for that device. `idle_ok` and a missing value do not.
The nurse does not invent the value. Silence never degrades the plane.

## Build the rows

**Metric row** (stamp `metrics[]`) — one per resolved device from
S1. Has `scope`, no `keys`.

| Column | From |
|--------|------|
| `at` | `checked_at` |
| `scope` | `device:<name>` (`host:<dev>` when unresolved) |
| `name` | resolved name |
| `events` | sum of that device's bucket counts |
| `bgp_events` `link_events` `config_events` `reload_events` `acl_events` `auth_ok` `auth_failed` `ssh_no_match` | that bucket's `count`, or 0 when the bucket is absent |

**Reading / board row** — one per S2 row. Has `keys`, no `scope`.

| Column | From |
|--------|------|
| `name` | resolved name |
| `kind` `subject` `count` `at` `state` `source_ip` `detail` | copied from the S2 row (`null` where S2 has none) |
| `peer` | bgp only: the device whose `topology-observed.json` interface address equals `subject`, else null |
| `keys` | `device:<name>`; a link row adds `interface:<name>/<subject>`; a bgp row with `peer` adds `device:<peer>`; `[]` when unresolved |

## Diff against the board

Match an S2 row to `splunk.current[]` by `name` + `kind` + `subject`.
Every S2 row is a `vs_prior.changed[]` item (syslog is events; an
event is a change):

| kind | `field` | `prior` | `current` |
|------|---------|---------|-----------|
| bgp | `bgp_state` | board `state` or null | `state`, or `<state> x<count>` when `count` ≥ 2 |
| link | `link_state` | board `state` or null | `state`, or `<state> x<count>` when `count` ≥ 2 |
| config | `config` | board `at` or null | `<subject> via <detail> from <source_ip>` |
| reload | `reload` | board `at` or null | `detail` |
| acl | `acl` | board `at` or null | `<state> x<count>` |
| auth_failed | `auth_failed` | board `at` or null | `<subject> from <source_ip> x<count>` |

`at` = the row's `at`.

**Flap.** S2 keeps `latest(state)`, so a session or link that went
down and came back inside one window reads `Up` with `count` ≥ 2.
That is a **flap**: treat a bgp or link row with `count` ≥ 2 exactly
like a `Down`/reset for `delta`, plane status, and `concerns`, even
though `state` says `Up`. Say "flapped" in the note.

`delta`: `worse` when any item is a bgp `Down`/reset, a link `down`
(not `administratively down`), a bgp or link flap (`count` ≥ 2), a
reload, or an auth_failed; `better` when items are only `Up`/`up`
with `count` 1 and nothing worse; `changed` when only config, acl,
or administratively down; `unchanged` when S2 was empty; `first`
when there is no board.

**Stamp or quiet.** Write a stamp when: no board (first visit), S2
returned at least one row, or coverage ≠ `complete`. Otherwise the
visit is **quiet**: no stamp; board only.

## Plane status

`degraded` when any S2 row has bgp `state` `Down`/`active reset`/
`passive reset`, link `state` `down`, a bgp or link `count` ≥ 2
(flap), or kind `reload`. Config, ACL logs, admin-down, failed auth,
and SSH NO_MATCH never degrade on their own — they are `changed`
and, for failed auth and reload, `concerns`. `unknown` when S1
failed.

## Write

Order: **board first, then stamp.** The board is a copy of the rows
you already built; write it as soon as the rows exist so a visit
that dies while composing notes still leaves the board for the
next visit to diff against. Then the stamp (when due), `read_file`
it, prune to 10, and rewrite the board once more with
`last_visit_id` set.

**Stamp** (schema `health-splunk-check`): `readings` = every S2 row +
`note`. `note` is one sentence against the board row: new subject
vs flap vs recovered (compare `state` and `count` to the board
row), who committed from where and whether it looks interactive
(`vty`, an operator address) or pipeline (`console`), why it
reloaded. Not the columns again. **On the baseline** there is no
board to compare to: `note` is `"Baseline."` unless the row is a
bgp Down/reset, a link `down`, a flap, a reload, or an auth_failed —
those get the one sentence. `unchanged` = board rows not replaced.
`baseline_ref` = `health/splunk/<baseline_visit_id>.json`.
`headline`: device, subject, state or user, when; then devices
logged and unchanged count. `concerns`: devices with a bgp
Down/reset, a flap, non-admin link down, reload, or auth_failed.

**Board** (schema `health-metadata-splunk`) — every visit:
- `current[]` ← S2 rows replace rows with the same
  `name`+`kind`+`subject`; others kept (cap 120, drop oldest `at`).
- `series[]` ← append one `estate` row (sums over S1); keep 10.
- `visits[]` ← append `{watch_id (null when quiet), checked_at,
  status, coverage, delta, stamp_written, window_start,
  window_end, silent[] (expected names with no S1 row),
  unresolved[] (dev values that resolved to nothing)}`; keep 10.
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
| Workspace writes | 4 (board, stamp, prune, board) |
| `splunk_search` | 2 (plus one retry each); +1 S1 for an operator-named index |
| `splunk_get_indexes` | 1 (S1 zero rows, or resolve) |

## Reply

Stamp written:

```text
Visit: splunk
Search: <ok|failed>; truncated <yes|no>; parse <complete|incomplete>
Reporting: <observed> of <expected> logged in <window>; expected-silent: <names | none>; no-events with no expectation: <count>
Result: <ok | degraded | unknown>
Coverage: <complete|partial|unavailable>
Wrote: health/splunk/<stamp>.json
Trend: <delta>
Findings:
- <event time> <device> <kind> x<count> window <window_start>..<window_end>; evidence on the stamp
Next: <the note's next check, or none>
```

Quiet:

```text
Visit: splunk
Search: ok; truncated no; parse <complete|incomplete>
Reporting: <observed> of <expected> logged in <window>; expected-silent: <names | none>; no-events with no expectation: <count>
Result: ok
Coverage: complete
Wrote: health/metadata-splunk.json (no material event)
Trend: unchanged
Board: <n> rows, last stamp <last_visit_id>
Next: none
```
