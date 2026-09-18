---
name: compliance-intel
version: "1.11.0"
description: "v1.11.0 — Fingerprints choose Intel work. Reconcile candidates every visit. One family per query when the framework changes."
---

# Compliance intel

For the **Compliance** agent. Compare **published NIST titles** to
**this network** and **tests on git `main`**. Fingerprints decide
how much work this visit does. Reconcile open INTEL candidates
against the live catalog every time.

You do **not** run `test.yml`. You do **not** invent pass/fail for devices.
You do **not** copy git into the workspace.

## Hard boundaries

Write **only** these **workspace-relative** paths with built-in
`write_file` (creates parents; never `mkdir`):

- `compliance/coverage.json`
- `compliance/intel.json`
- `compliance/metadata.json`

Do not use `Internal directory`, `/app/`, or `/shared_workspace/...`
on built-in file tools. Do not write to `sessions/`, `skills/`,
`scripts/`, `tool_results`, or a schedule scratch folder. Write
ONLY to the main workspace catalog. Access denied with allowed
`file_explorer`: retry once `file_explorer/<catalog row>`.

Do **not** write `compliance/_git_input.json`, `prepare_*.py`, any `.py`,
the matrix, the bridge, check files, `testing/`, `runs/`, or any other
path. If it is not a `workspace-handoff` row for this agent, do not
`write_file` it. Do not invent files.

Do not `github_get_file` the matrix or bridge. The test list is
`catalog/job-catalog.json`. NIST titles come from `query_sources.py`
(pinned OSCAL index + optional STIG Viewer HTTP).

GitHub is read-only: `github_get_file` only. Never `github_run_action`.
Never `github_put_file`.

Do not create helper scripts. Do not scrape HTML. **No curl.** The query
script performs HTTP. Never `--output`. No icons/emoji. Do not dump raw
tool payloads.

`execute_command` is only these scripts (stdout). Fingerprints first:

```text
python3 /skills/user/compliance-intel/scripts/fingerprint_inputs.py --estate /workspace/inventory/prod.json --prior /workspace/compliance/metadata.json --coverage /workspace/compliance/coverage.json --catalog -
```

Pass the `github_get_file` catalog JSON on stdin (`--catalog -`).
Do not `write_file` that JSON. Omit `--estate` when `inventory/prod.json`
is missing. Family queries **only** when stdout `work.framework_rescan`
is true (or the fingerprint script is missing):

```text
python3 /skills/user/compliance-intel/scripts/query_sources.py family AC
python3 /skills/user/compliance-intel/scripts/query_sources.py family AU
python3 /skills/user/compliance-intel/scripts/query_sources.py family CM
python3 /skills/user/compliance-intel/scripts/query_sources.py family IA
python3 /skills/user/compliance-intel/scripts/query_sources.py family SC
python3 /skills/user/compliance-intel/scripts/query_sources.py family SI
```

`family` takes **one** letter. Never `family AC AU CM IA SC SI`.

Stdout only. Do not redirect into a workspace file from the shell.
If `query_sources.py` is missing on a rescan: skip NIST, set
`sources_status` `failed`. Never `Internal directory`. Never `/app/`.
Never invent a path.

## CRITICAL RULES

1. **Tests live in git.** One fetch:
   `github_get_file(path="catalog/job-catalog.json", ref="main")`.
   Use the MCP result in this turn. Never write that JSON to the workspace.
2. **Fingerprints choose the visit.** Do not skim six families unless
   `work.framework_rescan` is true (or coverage/metadata is missing).
3. **Reconcile every visit.** Drop INTEL rows whose NIST ids are now
   on a catalog check (`nist:`). Keep stable `INTEL-` ids for the rest.
   Refill to cap 5 from remaining relevant gaps.
4. **Relevance is this estate.** Read `inventory/prod.json` when it
   exists (platform, role, tags). Interpret the control. If it only
   applies to servers, endpoints, or SaaS and we have none of those,
   put it on `skipped_non_network` with why. Do not propose it. Do
   not use a family letter as the skip.
5. **Primary map = NIST SP 800-53 Rev 5** — ids like `AC-17`, `SC-8`.
   PCI / STIG are footnotes. Resolve 800-171 / STIG Viewer URLs **to**
   800-53 before a candidate.
6. **No copyrighted control text** — your words; cite URL + date. Titles
   and identifiers are fine.
7. **Delta, then rank.** Catalog `nist:` on a check is covered, not a
   gap. Candidates are relevant missing / partial controls only. Sort
   `critical` → `high` → `medium` → `low`. Cap 5. Fill `delta`.
8. **status stays `proposed`.** Do not edit git tests.
9. **Reuse `INTEL-` ids** when re-proposing the same theme; bump `run_id`.
   Missing intel on first run is normal.
10. Do not invent gaps. Do not write zeros into coverage when the
    source query failed.
11. Paths: `workspace-handoff`. Produce: `references/workspace-contract.md`.
12. Write coverage/intel only when that file changed this visit.
    Write `compliance/metadata.json` from fingerprint stdout `persist`
    after a successful evaluation (including a visit that only
    reconciled). If nothing material changed, do not rewrite coverage
    or intel; still report inputs unchanged.

## Estate

The network is whatever `inventory/prod.json` says this visit.
Typical lab: IOS-XE edge / WAN / branch. Live checks target those
platforms. Do not assume a device that is not in the file.

## Scripts (stdout only — not workspace files)

| Script | When |
|--------|------|
| `fingerprint_inputs.py` | Every scheduled / gaps / implement visit |
| `query_sources.py family AC` (AU CM IA SC SI) | Only if `work.framework_rescan` |
| `query_sources.py lookup <id-or-url>` | They named a control or STIG Viewer URL |

```text
python3 /skills/user/compliance-intel/scripts/fingerprint_inputs.py --estate /workspace/inventory/prod.json --prior /workspace/compliance/metadata.json --coverage /workspace/compliance/coverage.json --catalog -
python3 /skills/user/compliance-intel/scripts/query_sources.py family AC
python3 /skills/user/compliance-intel/scripts/query_sources.py lookup AC-17
```

After coverage exists, `lookup … --coverage /workspace/compliance/coverage.json`
is allowed on **that command only**. If that `.py` is missing, skip
it — do not invent `Internal directory` or a workspace copy of the
script.

Do **not** run `build_coverage.py` in Studio. Do not pass git bodies as
`--input`. That script is for a local repo checkout only.

The skill ships a **pinned NIST OSCAL title index**. Fingerprints hash
that index. Do not copy it into the workspace. It is the standard,
not our test list.

| They give you | Command |
|---------------|---------|
| `AC-17` / `nist-800-53:AC-17` | `lookup AC-17` |
| `3.1.7` / 800-171 URL | `lookup 'https://www.stigviewer.com/controls/nist-800-171/3.1.7'` |
| A family to skim | `family AC` (only on `framework_rescan` or they named the family) |
| No network | `lookup … --offline` |

Optional `STIGVIEWER_TOKEN` / `SAMS_TOKEN` for the crosswalk API; otherwise
Table D-1 and a `warnings` line. STIG Viewer 800-171 is **Rev 2**. OSCAL
800-171 is **Rev 3**. Do not mix.

Use `title`, `source_control`, `resolved_from`, `maps_to_existing`,
`disa_footnote`, `oscal_release`. Never print control statements.

If `github_get_file` fails: still write intel with `sources_status: failed`
/ `SOURCES_DEGRADED`. Do not invent a test list.

## Execution

```text
1. READ     intel.json, coverage.json, metadata.json if present
            (keep stable INTEL- ids)
2. ESTATE   inventory/prod.json if present
            Protocol-specific asserts: github_get_file
            inventory/configs/<edge-or-wan> and name what is there
3. FETCH    github_get_file catalog/job-catalog.json ref=main
4. FINGER   fingerprint_inputs.py (catalog JSON on stdin)
5. RECON    drop INTEL rows now covered by catalog nist:
6. WORK     follow stdout work.* flags (table below)
7. REFILL   candidates to cap 5 from remaining relevant gaps
8. WRITE    coverage and/or intel if they changed
            metadata.json from persist after a successful evaluation
9. REPLY    Action + work kind + ranked candidates
```

Explain-only / last candidates: `read_file` intel.json. Do not
fingerprint. Do not write. Do not invoke Author.

### Work flags (`fingerprint_inputs.py` stdout)

| Flag | Do |
|------|----|
| `reconcile_candidates` | Always on this path. Drop covered INTEL rows. |
| `framework_rescan` | Six `family` calls. Rebuild coverage from titles + catalog + estate. |
| `estate_rejudge` | Rejudge existing coverage rows and `skipped_non_network` vs prod.json. No family calls unless `framework_rescan`. |
| `coverage_from_catalog` | Join catalog `nist:` onto coverage rows (`net_comp` / `live` / `static` / `status`). Do not re-skim NIST. Do not rejudge estate N/A. |

First visit (missing prior or missing coverage): `framework_rescan`.

All flags false after reconcile, queue still full: do not rewrite
coverage or intel. Report inputs unchanged.

### Candidate quality bar

Each candidate **must** include:

- `why_network` — why this control applies to **these** devices
- `priority` — `critical` | `high` | `medium` | `low` (impact if we
  do not test it on this estate)
- `nist_sp_800_53` — 1–3 control ids
- `suggested_assert` — a concrete check idea naming a CAPABILITIES assert.
  It must be runnable on **these** devices. If the idea is a routing
  protocol setting, name the protocol that appears in git
  `inventory/configs/` — do not write “applicable IGP” as a stand-in
  for processes this estate does not run.
- `maps_to_existing` — `none` or existing check id / `NET-COMP-####`
- `source_control` — `nist-800-53:AC-17`
- `oscal_release` — pinned `v1.5.0`
- `resolved_from` — `nist-800-171:3.1.7` when they started from 800-171

List order is the rank. `skipped_non_network` names what you judged
not applicable and why (e.g. `AC-19 portable device — no endpoints
in prod.json`).

`delta.catalog_covered` / `relevant_missing` / `not_applicable`
must match coverage + candidates + skipped this run.

Good themes when they apply here: BGP neighbor auth, prefix filters,
no HTTP server, CoPP, syslog+NTP if still a gap, AAA exec
authorization if not in catalog.

## Workspace schema

Fill from this skill:

- [`schemas/coverage.schema.json`](schemas/coverage.schema.json)
- [`examples/coverage.example.json`](examples/coverage.example.json)
- [`schemas/compliance-intel.schema.json`](schemas/compliance-intel.schema.json)
- [`examples/compliance-intel.example.json`](examples/compliance-intel.example.json)
- [`schemas/compliance-metadata.schema.json`](schemas/compliance-metadata.schema.json)
- [`examples/compliance-metadata.example.json`](examples/compliance-metadata.example.json)

Intel envelope: `version`, `updated_at`, `source_agent`, `status`,
`headline`, `next_action`, `sources`, `delta`, `candidates`.

`status`: `OK` | `NO_CANDIDATES` | `SOURCES_DEGRADED`.
`sources_status`: `ok` | `partial` | `failed`.

Metadata is **not** the five-field envelope. Prefer stdout `persist`.

## Reply format

```text
Action: wrote_intel | reconciled | unchanged | no_new_candidates
Work: framework_rescan | estate_rejudge | catalog_join | reconcile_only
Changed: none | framework, estate, catalog
Sources: git catalog + <NIST names>
Candidates: <n>
Headline: <one line>
File: compliance/intel.json
Ranked:
- INTEL-0001 <priority>: <title> → <NIST ids>
```

`Work:` is the heaviest flag that ran (`framework_rescan` beats
`estate_rejudge` beats `catalog_join` beats `reconcile_only`).

## Handoffs

| Outcome | Next |
|---------|------|
| Ranked candidates after refill (default scan) | Prompt invokes **Compliance Author**, then **Compliance Test** |
| Queue empty after reconcile | Do **not** invoke Author |
| Report-only / intel-only / explain | Stop. No fingerprint write |
| User wants device score only | **Compliance Test** — `suites=compliance` |
| Ticket from a live gap | **Observability** |
