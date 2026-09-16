---
name: compliance-intel
version: "1.10.0"
description: "v1.10.0 — suggested_assert names what this estate runs. One family per query."
---

# Compliance intel

For the **Compliance** agent. Compare **published NIST titles** to
**this network** and **tests on git `main`**. Write the two catalog
files. The prompt then hands Author and Test the ranked gaps.

You do **not** run `test.yml`. You do **not** invent pass/fail for devices.
You do **not** copy git into the workspace.

## Hard boundaries

Write **only** these **workspace-relative** paths with built-in
`write_file` (creates parents; never `mkdir`):

- `compliance/coverage.json`
- `compliance/intel.json`

Do not use `Internal directory`, `/app/`, or `/shared_workspace/...`
on built-in file tools. Do not write to `sessions/`, `skills/`,
`scripts/`, `tool_results`, or a schedule scratch folder. Write
ONLY to the main workspace catalog. Access denied with allowed
`file_explorer`: retry once `file_explorer/<catalog row>`.

Do **not** write `compliance/_git_input.json`, `prepare_*.py`, any `.py`,
the matrix, the bridge, check YAML, `testing/`, `runs/`, or any other
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

`execute_command` is only this script, **one family per call**:

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
If that `.py` is missing: skip NIST, set `sources_status` `failed`.
Never `Internal directory`. Never `/app/`. Never invent a path.

## CRITICAL RULES

1. **Tests live in git.** One fetch:
   `github_get_file(path="catalog/job-catalog.json", ref="main")`.
   Use the MCP result in this turn. Never write that JSON to the workspace.
2. **Write every run** — coverage then intel (even if `candidates` is empty).
3. **Relevance is this estate.** Read `inventory/prod.json` when it
   exists (platform, role, tags). Interpret the control. If it only
   applies to servers, endpoints, or SaaS and we have none of those,
   put it on `skipped_non_network` with why. Do not propose it. Do
   not use a family letter as the skip.
4. **Primary map = NIST SP 800-53 Rev 5** — ids like `AC-17`, `SC-8`.
   PCI / STIG are footnotes. Resolve 800-171 / STIG Viewer URLs **to**
   800-53 before a candidate.
5. **No copyrighted control text** — your words; cite URL + date. Titles
   and identifiers are fine.
6. **Delta, then rank.** Catalog `nist:` on a check is covered, not a
   gap. Candidates are relevant missing / partial controls only. Sort
   `critical` → `high` → `medium` → `low`. Cap 5. Fill `delta`.
7. **status stays `proposed`.** Do not edit git tests.
8. **Reuse `INTEL-` ids** when re-proposing the same theme; bump `run_id`.
   Missing intel on first run is normal.
9. Do not invent gaps. Do not write zeros into coverage when the
   source query failed.
10. Paths: `workspace-handoff`. Produce: `references/workspace-contract.md`.

## Estate

The network is whatever `inventory/prod.json` says this visit.
Typical lab: IOS-XE edge / WAN / branch. Live checks target those
platforms. Do not assume a device that is not in the file.

## Scripts (stdout only — not workspace files)

| Script | When |
|--------|------|
| `query_sources.py family AC` (AU CM IA SC SI) | Skim NIST titles for this estate |
| `query_sources.py lookup <id-or-url>` | They named a control or STIG Viewer URL |

```text
python3 /skills/user/compliance-intel/scripts/query_sources.py family AC
python3 /skills/user/compliance-intel/scripts/query_sources.py lookup AC-17
```

After coverage exists, `lookup … --coverage /workspace/compliance/coverage.json`
is allowed on **that command only**. If the script file is missing, skip
it — do not invent `Internal directory` or a workspace copy of the
script.

Do **not** run `build_coverage.py` in Studio. Do not pass git bodies as
`--input`. That script is for a local repo checkout only.

The skill ships a **pinned NIST OSCAL title index**. That is the standard,
not our test list.

| They give you | Command |
|---------------|---------|
| `AC-17` / `nist-800-53:AC-17` | `lookup AC-17` |
| `3.1.7` / 800-171 URL | `lookup 'https://www.stigviewer.com/controls/nist-800-171/3.1.7'` |
| A family to skim | `family AC` |
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
1. READ     built-in read_file compliance/intel.json if present (keep stable ids)
2. ESTATE   built-in read_file inventory/prod.json if present
            Protocol-specific asserts: github_get_file
            inventory/configs/<edge-or-wan> and name what is there
3. FETCH    github_get_file catalog/job-catalog.json ref=main
4. NIST     six execute_command calls — family AC, then AU, CM, IA, SC, SI
            (one family each; stdout)
5. COVER    built-in write_file compliance/coverage.json (workspace-relative)
            Catalog checks with nist: [ID] → covered. Missing → gap
            only after you judged the control applies here.
6. DRAFT    0–5 relevant missing/partial, ranked by priority
            suggested_assert from this estate, not a protocol textbook
7. WRITE    built-in write_file compliance/intel.json (workspace-relative)
8. REPLY    Action + headline + ranked candidates
```

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

Intel envelope: `version`, `updated_at`, `source_agent`, `status`,
`headline`, `next_action`, `sources`, `delta`, `candidates`.

`status`: `OK` | `NO_CANDIDATES` | `SOURCES_DEGRADED`.
`sources_status`: `ok` | `partial` | `failed`.

## Reply format

```text
Action: wrote_intel | no_new_candidates
Sources: git catalog + <NIST names>
Candidates: <n>
Headline: <one line>
File: compliance/intel.json
Ranked:
- INTEL-0001 <priority>: <title> → <NIST ids>
```

## Handoffs

| Outcome | Next |
|---------|------|
| Ranked candidates (default scan) | Prompt invokes **Compliance Author**, then **Compliance Test** |
| Report-only / intel-only | Stop after the two files |
| User wants device score only | **Compliance Test** — `suites=compliance` |
| Ticket from a live gap | **Observability** |
