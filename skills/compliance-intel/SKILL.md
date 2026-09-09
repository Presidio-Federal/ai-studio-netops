---
name: compliance-intel
version: "1.8.2"
description: "v1.8.2 — Workspace-relative write_file only. No file_explorer / sessions sandbox."
---

# Compliance intel

For the **Compliance** agent. Compare **NIST network/routing**
controls** to **tests on git `main`**. Write the two catalog files. Stop.

You do **not** run `test.yml`. You do **not** invent pass/fail for devices.
You do **not** copy git into the workspace.

## Hard boundaries

Write **only** these **workspace-relative** paths with built-in
`write_file` (creates parents; never `mkdir`):

- `compliance/coverage.json`
- `compliance/intel.json`

Do not use `/file_explorer`, `Internal directory`, or
`/shared_workspace/...` on built-in file tools. Do not write to
`sessions/`, `skills/`, `scripts/`, `tool_results`, or a schedule
scratch folder. Write ONLY to the main workspace catalog.

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

`execute_command` is only:

```text
python3 /skills/user/compliance-intel/scripts/query_sources.py …
```

Stdout only. Do not redirect into a workspace file from the shell.

## CRITICAL RULES

1. **Tests live in git.** One fetch:
   `github_get_file(path="catalog/job-catalog.json", ref="main")`.
   Use the MCP result in this turn. Never write that JSON to the workspace.
2. **Write every run** — coverage then intel (even if `candidates` is empty).
3. **Network / routing filter** — routers, switches, WAN/edge, routing,
   management plane, logging, NTP, SNMP, AAA, path/boundary. Drop the rest.
4. **Primary map = NIST SP 800-53 Rev 5** — ids like `AC-17`, `SC-8`.
   PCI / STIG are footnotes. Resolve 800-171 / STIG Viewer URLs **to**
   800-53 before a candidate.
5. **No copyrighted control text** — your words; cite URL + date. Titles
   and identifiers are fine.
6. **Cap 5 candidates.** Prefer gaps, not SSH/SNMPv3/NTP/AAA/logging already
   in the catalog.
7. **status stays `proposed`.** Do not edit git tests.
8. **Reuse `INTEL-` ids** when re-proposing the same theme; bump `run_id`.
   Missing intel on first run is normal.
9. Candidates from coverage rows `partial` or `gap` in families
   AC AU CM IA SC SI. Do not invent gaps. Catalog `nist:` on a check means
   that control is already tested (`covered`).
10. Paths: `workspace-handoff`. Produce: `references/workspace-contract.md`.

## Lab context

IOS-XE edges/WANs/branches in CML. Live checks target `iosxe` / `cat9kv`.

## Scripts (stdout only — not workspace files)

| Script | When |
|--------|------|
| `query_sources.py family AC` (AU CM IA SC SI) | Skim NIST titles for this estate |
| `query_sources.py lookup <id-or-url>` | They named a control or STIG Viewer URL |

```text
python3 /skills/user/compliance-intel/scripts/query_sources.py family AC
python3 /skills/user/compliance-intel/scripts/query_sources.py lookup AC-17
```

If `/skills` is empty, use the repo-relative path. After coverage exists,
`lookup … --coverage compliance/coverage.json` is allowed (that file is a
catalog path).

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
2. FETCH    github_get_file catalog/job-catalog.json ref=main
3. NIST     execute_command query_sources.py family AC AU CM IA SC SI (stdout)
4. COVER    built-in write_file compliance/coverage.json (workspace-relative)
            Catalog checks with nist: [ID] → covered. Missing → gap.
5. DRAFT    0–5 candidates from partial/gap rows (network/routing only)
6. WRITE    built-in write_file compliance/intel.json (workspace-relative)
7. REPLY    Action + headline + top candidates
```

### Candidate quality bar

Each candidate **must** include:

- `why_network` — routers/routing/mgmt plane
- `nist_sp_800_53` — 1–3 control ids
- `suggested_assert` — a concrete check idea naming a CAPABILITIES assert
- `maps_to_existing` — `none` or existing check id / `NET-COMP-####`
- `source_control` — `nist-800-53:AC-17`
- `oscal_release` — pinned `v1.5.0`
- `resolved_from` — `nist-800-171:3.1.7` when they started from 800-171

Good themes: BGP neighbor auth, prefix filters, no HTTP server, CoPP,
syslog+NTP only if still a gap, AAA exec authorization if not in catalog.

## Workspace schema

Fill from **`workspace-handoff`**:

- [`schemas/coverage.schema.json`](../workspace-handoff/schemas/coverage.schema.json)
- [`references/coverage.example.json`](../workspace-handoff/references/coverage.example.json)
- [`schemas/compliance-intel.schema.json`](../workspace-handoff/schemas/compliance-intel.schema.json)
- [`references/compliance-intel.example.json`](../workspace-handoff/references/compliance-intel.example.json)

Intel envelope: `version`, `updated_at`, `source_agent`, `status`,
`headline`, `next_action`, `sources`, `candidates`.

`status`: `OK` | `NO_CANDIDATES` | `SOURCES_DEGRADED`.
`sources_status`: `ok` | `partial` | `failed`.

## Reply format

```text
Action: wrote_intel | no_new_candidates
Sources: git catalog + <NIST names>
Candidates: <n>
Headline: <one line>
File: compliance/intel.json
Top:
- INTEL-0001: <title> → <NIST ids>
```

## Handoffs

| Outcome | Next |
|---------|------|
| User wants assessment of current devices | **Compliance Test** — `suites=compliance` |
| User approves implementing a candidate | **Compliance Author** — do not write YAML here |
| Ticket from a live gap | **Observability** |
