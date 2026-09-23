---
name: compliance-intel
version: "1.18.2"
description: "v1.18.2 — Fixed sandbox path with direct-stdin or exact-heredoc bounded NIST scan."
---

# Compliance intel

For **Compliance Intelligence**. Compare **published NIST titles** to
**this network** and **tests on git `main`**. Write the two catalog
files. Ranked candidates wait for the operator. Do not invoke
Author or Test on a scan.

You do **not** run `test.yml`. You do **not** invent pass/fail for devices.
You do **not** copy git into the workspace.

## Hard boundaries

Write **only** these catalog rows with built-in `write_file`
(creates parents; never `mkdir`):

- `compliance/coverage.json`
- `compliance/intel.json`
- `compliance/intel/<stamp>.json`
- `compliance/metadata-intel.json`

File tools use catalog rows from `workspace-handoff`. Do not invent
prefixes. Do not write to `sessions/`, `skills/`, `scripts/`,
`tool_results`, or a schedule scratch folder. If it is not a
`workspace-handoff` row for this agent, do not `write_file` it.

Do **not** write `compliance/_git_input.json`, `prepare_*.py`, any `.py`,
the matrix, the bridge, check files, `testing/`, `runs/`, or any other
path.

Do not `github_get_file` the matrix, bridge, or running-configs.
The test list is `catalog/job-catalog.json` only. NIST titles come
from `query_sources.py`. Running-configs are Author’s job.

GitHub is read-only: `github_get_file` only. Never `github_run_action`.
Never `github_put_file`.

Do not create helper scripts. Do not scrape HTML. **No curl.** Never
`--output`. No icons/emoji. Do not dump raw tool payloads.

`execute_command` is only this script. **Standard scan is one
`unresolved` call** — not six `family` calls.

```text
python3 /skills/user/compliance-intel/scripts/query_sources.py unresolved --limit 20 --catalog - --coverage /workspace/compliance/coverage.json --intel /workspace/compliance/intel.json
```

Pass the `github_get_file` catalog JSON on stdin. If `execute_command` has a
stdin field, use it. Otherwise use exactly one direct heredoc on the Python
command (not `cat | python`):

```text
python3 /skills/user/compliance-intel/scripts/query_sources.py unresolved --limit 20 --catalog - --coverage /workspace/compliance/coverage.json --intel /workspace/compliance/intel.json <<'CATALOG_JSON'
<catalog JSON>
CATALOG_JSON
```

Never use `Internal directory` as a path. Do not `write_file` the catalog.
Omit `--coverage` and/or `--intel` when that workspace file is missing.
Stdout only. Do not redirect into a workspace file.

`family` and `lookup` are troubleshooting / named-control only. Never
run `family` AC, AU, CM, IA, SC, SI on a scheduled or gaps visit.

If that `.py` is missing: skip NIST, set `sources_status` `failed`.
Never invent a path.

## CRITICAL RULES

1. **Tests live in git.** One fetch:
   `github_get_file(path="catalog/job-catalog.json", ref="main")`.
   Use the MCP result in this turn. Never write that JSON to the workspace.
2. **Write every run** — coverage, append-only Intel stamp, current intel,
   then metadata (even if `candidates` is empty).
3. **Relevance is this estate.** Read `inventory/prod.json` when it
   exists (platform, role, tags). Interpret the control. If it only
   applies to servers, endpoints, or SaaS and we have none of those,
   put it on `skipped_non_network` with why **and** a coverage row
   `status: not_applicable`. Do not propose it. Do not use a family
   letter as the skip.
4. **Primary map = NIST SP 800-53 Rev 5** — ids like `AC-17`, `SC-8`.
   PCI / STIG are footnotes. Resolve 800-171 / STIG Viewer URLs **to**
   800-53 before a candidate.
5. **No copyrighted control text** — your words; cite URL + date. Titles
   and identifiers are fine.
6. **Delta, then rank.** Catalog `nist:` on a check is covered, not a
   gap. Candidates are relevant missing / partial controls only. Sort
   `critical` → `high` → `medium` → `low`. Cap 10. Fill `delta`.
7. **status stays `proposed`.** Do not edit git tests.
8. **Reuse `INTEL-` ids** when re-proposing the same theme; bump `run_id`.
   Missing intel on first run is normal.
9. Do not invent gaps. Do not write zeros into coverage when the
   source query failed.
10. Paths: `workspace-handoff`. Produce: `references/workspace-contract.md`.
11. Every coverage row and candidate carries all supported
    `workspace-handoff` `type:name` keys. Use exact source names with no
    whitespace after `:`. Never infer a device or other relationship.

## Estate

`inventory/prod.json` is the kinds of things we have (platform, role,
tags) — so you recommend network-gear controls and skip endpoint /
server / SaaS titles. Typical lab: IOS-XE edge / WAN / branch. Do
not open running-configs to see which protocol is configured. Do
not assume a device that is not in the file.

## Scripts (stdout only — not workspace files)

| Script | When |
|--------|------|
| `query_sources.py unresolved --limit 20` | **Standard scan.** Bounded unresolved titles |
| `query_sources.py lookup <id-or-url>` | They named a control or STIG Viewer URL |
| `query_sources.py family AC` | Troubleshooting / they asked to skim one family |

```text
python3 /skills/user/compliance-intel/scripts/query_sources.py unresolved --limit 20 --catalog - --coverage /workspace/compliance/coverage.json --intel /workspace/compliance/intel.json
python3 /skills/user/compliance-intel/scripts/query_sources.py lookup AC-17
python3 /skills/user/compliance-intel/scripts/query_sources.py family AC
```

The unresolved script reads coverage and intel from `/workspace`. Built-in
file tools still use workspace-relative catalog paths without `/workspace/`.
Do not paste the historical coverage file or the git catalog into
chat. Evaluate only the returned `controls` list (plus current
candidates and inventory).

If that `.py` is missing, skip it — do not invent a workspace copy
of the script.

The skill ships a **pinned NIST OSCAL title index**. That is the standard,
not our test list. Do not copy it into the workspace.

| They give you | Command |
|---------------|---------|
| Scheduled / gaps / what’s missing | `unresolved --limit 20` |
| `AC-17` / `nist-800-53:AC-17` | `lookup AC-17` |
| `3.1.7` / 800-171 URL | `lookup 'https://www.stigviewer.com/controls/nist-800-171/3.1.7'` |
| Skim one family (troubleshooting) | `family AC` |
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
1. READ     metadata-intel.json and its latest Intel stamp if present;
            read intel.json if present (keep stable INTEL- ids)
2. ESTATE   inventory/prod.json if present (kinds of devices only)
3. FETCH    github_get_file catalog/job-catalog.json ref=main
            (only git path; never running-configs)
4. COVER    read_file coverage.json if present
            (merge later; do not dump it into the reply)
5. RECONCILE drop intel candidates whose nist ids are now on a
            catalog check (nist:). Keep other proposed/accepted
            candidates and their INTEL- ids. No duplicates.
6. FULL?    if remaining active candidates = 10:
            skip unresolved. Write coverage (catalog reconcile
            only — keep existing rows) then intel. Reply.
7. NIST     else one execute_command:
            unresolved --limit 20 --catalog - [--coverage] [--intel]
            stdin = catalog JSON. Do not write_file the catalog.
8. JUDGE    each returned control against this estate
            (applicability, priority, suggested_assert)
9. MERGE    coverage is accumulated working state — do not rebuild
            from six families. Upsert:
            catalog nist: → covered
            reviewed N/A → not_applicable
            selected candidate → gap (or partial if tests exist)
            keep untouched prior rows
10. DRAFT   keep remaining candidates; add new ones up to cap 10;
            rank critical → high → medium → low
11. WRITE   coverage.json; intel/<stamp>.json; intel.json; metadata-intel.json.
            The stamp and current intel have the same evidence. Set
            vs_prior.prior_visit_id from metadata, compare stable metrics and
            candidate ids, keep 10 stamps, and never list the directory.
12. REPLY   Action + headline + ranked candidates. Stop.
            Do not invoke Author or Test.
```

Explain-only / last candidates: `read_file` intel.json. Do not
re-query unless they asked for a new scan. Do not invoke Author.

### Coverage dispositions (reviewed controls)

Every control you reviewed this run must have a coverage row:

Each row's `keys` starts with `control:<nist_id>`. Add
`test:<NET-COMP-id>`, `test:<live-id>`, and `test:<static-id>` for every
identifier already present in that row's catalog mappings. Do not add a
device key; coverage is control-to-test knowledge, not device evidence.

| Judgment | `status` | Also |
|----------|----------|------|
| Catalog already tests it (`nist:`) | `covered` | Drop matching intel candidates |
| Applies here; still need a check | `gap` or `partial` | Intel candidate if it ranks into the cap |
| Does not apply to this estate | `not_applicable` | `skipped_non_network` line with why |

A reviewed `not_applicable` or `covered` row is why `unresolved`
will not return that id next time. `gap` without a candidate may
still return — that is remaining work, not a skip.

Do not require a six-family scan to write a valid coverage file.
Preserve top-level fields from the schema (`version`, `updated_at`,
`source_agent`, `rows`, `counts`). Recount `counts` from `rows`.

### Candidate quality bar

Each candidate **must** include:

- `keys` — every `control:<NIST-id>` and `test:<existing-id>` when
  `maps_to_existing` is not `none`; keep the `INTEL-*` identifier only in `id`
- `why_network` — why this control applies to **these** devices
- `priority` — `critical` | `high` | `medium` | `low` (impact if we
  do not test it on this estate)
- `nist_sp_800_53` — 1–3 control ids
- `suggested_assert` — what to add to the test catalog (static vs
  live, on these platforms from inventory). Do not inspect device
  configs to pick a protocol. Author reads configs when it writes
  the check.
- `maps_to_existing` — `none` or existing check id / `NET-COMP-####`
- `source_control` — `nist-800-53:AC-17`
- `oscal_release` — pinned `v1.5.0`
- `resolved_from` — `nist-800-171:3.1.7` when they started from 800-171

List order is the rank. Cap **10**. Do not emit an eleventh. Reuse the
existing `INTEL-` id when the same control / theme is still a gap.

`skipped_non_network` names what you judged not applicable and why
(e.g. `AC-19 portable device — no endpoints in prod.json`). Keep
prior N/A lines unless that id is now catalog-covered.

`delta.catalog_covered` / `relevant_missing` / `not_applicable`
must match coverage counts + candidates + skipped on the files
you write.

Good themes when inventory shows network gear and the catalog does
not already cover them: mgmt-plane hardening, AAA, logging/NTP,
routing-protocol authentication, CoPP. Author decides the exact
CLI against committed config.

## Canonical top-level keys

Every structured JSON file you write requires top-level `keys`. Set it to the deduplicated union of every source-supported nested key and entity field in that file; use `[]` when there are none. Keep nested row `keys`. Keys must match exactly `^(device|interface|site|service|test|control|incident|change):[^ ].*$`; never infer one. Use `site:` for location. Recommendation identifiers remain ordinary `id` or `source_ref` values and never become keys.

## Workspace schema

Fill from this skill:

- [`schemas/coverage.schema.json`](schemas/coverage.schema.json)
- [`examples/coverage.example.json`](examples/coverage.example.json)
- [`schemas/compliance-intel.schema.json`](schemas/compliance-intel.schema.json)
- [`examples/compliance-intel.example.json`](examples/compliance-intel.example.json)
- [`schemas/compliance-intel-visit.schema.json`](schemas/compliance-intel-visit.schema.json)
- [`examples/compliance-intel-visit.example.json`](examples/compliance-intel-visit.example.json)
- [`schemas/compliance-intel-metadata.schema.json`](schemas/compliance-intel-metadata.schema.json)
- [`examples/compliance-intel-metadata.example.json`](examples/compliance-intel-metadata.example.json)

Intel envelope: `version`, `updated_at`, `source_agent`, `status`,
`headline`, `next_action`, `sources`, `delta`, `candidates`.

`status`: `OK` | `NO_CANDIDATES` | `SOURCES_DEGRADED`.
`sources_status`: `ok` | `partial` | `failed`.

Cite the pinned OSCAL index and the git catalog in `sources[]`.
Do not invent STIG Viewer fetches you did not run.

## Reply format

```text
Action: wrote_intel | no_new_candidates
Sources: git catalog + unresolved NIST
Candidates: <n>
Headline: <one line>
File: intel catalog row
Ranked:
- INTEL-0001 <priority>: <title> → <NIST ids>
```

## Handoffs

| Outcome | Next |
|---------|------|
| Any completed scan | Write chart files and stop |
| Ranked candidates | Primary Compliance and the operator interpret them later |
| Test posture or remediation | Not this specialist; consumers read the chart files |
