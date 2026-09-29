# Review — "look at everything and tell me what to fix"

An open-ended ask names no problem: *what should I improve*, *review
the network*, *look at all the data and recommend*, *what would you
fix*. That is **review** mode. It is still read-only (`mode`
`recommend`, `status` `recommended`) and still ends in exact config
lines — for every finding git can verify, not just one.

"Two problems fit → `Gaps:`" is for an *ambiguous reference* (the
operator's words match two problems). It does not apply here. In
review you rank; you do not decline.

## 1. Read the workspace (≤ 10 `read_file`)

In order, skipping paths that do not exist:

1. `state/health.json` — `problems[]` (`id`, `status`, `keys`,
   `hypothesis`, `evidence_refs`), `assessment.unhealthy`,
   `assessment.contradictions`.
2. `health/metadata-iosxe.json` — `current[]`.
3. `health/metadata-splunk.json` — `current[]`.
4. `health/metadata-thousandeyes.json` — `current[]`, `tests[]`.
5. `health/metadata-servicenow.json` — `current[]`.
6. `state/testing.json` — `latest`, `risk`, `run.suites`; then
7. the `operational/testing/<stamp>.json` it names in `latest` —
   failing result rows (control, device, detail) and the devices
   that passed the same control (your canonical peers).
8. `inventory/topology-observed.json` — `devices[].neighbors[]`
   (who is cabled to whom; the passing peer is usually the device
   in the same role).
9. `inventory/prod.json` — `devices[].name`, `role`.
10. `state/relationships.json` — only if it exists; optional.

An old compliance run is still evidence: the failing control names
the feature and the devices; git on `dev` is where you check whether
it is still true. Note the run date in the row's `finding`; do not
drop the row for age.

Do not open stamps. Do not list directories. The boards are the
last-known state of every subject; a stamp adds nothing here.

## 2. Find config-class symptoms on the boards

A symptom is config-class when the fix could be lines in a config
file. Collect these; each is a candidate row:

| Board | Row | Candidate when | Compare in git |
|-------|-----|----------------|----------------|
| iosxe | `kind bgp` | `state` not `fsm-established` | target `router bgp` stanza vs a same-role device whose rows are established |
| iosxe | `kind interface` | `input_acl` / `output_acl` set | is the ACL defined and bound in the target's git config? absent → `unplanned_change` |
| iosxe | `kind interface` | `num_flaps`, `in_errors`, `in_crc_errors` above 0 and rising on the ring | interface stanza (mtu, duplex, speed, encapsulation) vs the cabled far end (`topology-observed` `neighbors[].far`) |
| iosxe | `kind device` | `unsaved_config true` | none — `kind unsaved_config`, owner `operator`, `proposed` null; a save on the box is not a git line |
| splunk | `kind config` | any row | is there a ServiceNow `change` row for that device? none → `unplanned_change`, owner Ops Network Sync (the config pipeline reconciles box vs git); git alone cannot show what moved |
| splunk | `kind bgp` / `link` | `count` ≥ 2 | same as the iosxe bgp / interface rows for that device |
| thousandeyes | row | `state degraded` | `src_device` and `dst_device` WAN-facing interface stanzas (mtu, bandwidth, qos, acl) vs a pair whose row is `ok`; `hops[]` names the transit devices to include |
| servicenow | row | typed `device` set, `active true` | the named device / interface stanza for what `issue` describes |
| testing | failing result row | control is a config control (NTP, AAA, logging, SNMP, banner, ACL, BGP) | the feature's stanza on a failing device vs a device that passed the same control; a row whose `detail` is a check error (a Python traceback, `'dict' object has no attribute`) is `test_bug`, owner Compliance Author |
| chart | `problems[]` `active` / `watching` | keys carry `device:` or `interface:` | the hypothesis names what to compare |

Not config-class (list under `Not mine`, owner named, `proposed`
null): a nurse plane unavailable (Health Monitor / Health Device /
Health ServiceNow), topology map pending (Health Device), a ticket
state that contradicts device evidence (Ops ServiceNow), a syslog
feed missing (operator), hardware (Network Design), a check that
is wrong (Compliance Author). One line each; never in `Proposed:`.

## 3. Read git (1 list, ≤ 6 gets)

`github_list_files` `inventory/configs` on `dev` **once**. Then
`github_get_file` for each candidate target and its passing or
canonical peer, using only paths the listing returned, newest
symptom first, until six files or the candidates are exhausted.
A candidate you could not open gets `verified_in_git false` and
`proposed null` with the reason in `finding`.

For each candidate decide from the two bodies: the missing line,
the wrong value, the extra binding — or that git shows no
difference (then `verified_in_git false`, `proposed null`, and the
`finding` says what you compared).

## 4. Rank and write

Rank: chart `active` problems with a verified difference first;
then board symptoms with a verified difference; then unverified
config-class rows; then `unplanned_change`. Eight rows at most.

`review[]` rows per the schema. Row 1 becomes the record:
`problem_ref` (its `problem_ref`, may be null), `finding` (its
`finding` / `kind` — `unplanned_change` and `unsaved_config` map to
`other` — / `verified_in_git`), `change.devices` / `interfaces` /
`peer` / `files` / `summary` = its proposal. `relations[]` follow
`references/relations.md` for row 1 only. `keys` = union of row 1's
devices, interfaces, relation ends — review rows 2–8 add no keys.

No candidate at all: row-less review — `review []`, `problem_ref`
null, `finding.kind other`, `headline` says the boards show no
config-class symptom, `change.devices []`.

`headline`: `Review: <n> config-class findings across <d> devices;
top is <row 1 finding, short>`.

## Budget

≤ 8 `read_file`, 1 `github_list_files`, ≤ 6 `github_get_file`,
1 `write_file`. No GitOps Change, no Pipeline Monitor, no PR.
