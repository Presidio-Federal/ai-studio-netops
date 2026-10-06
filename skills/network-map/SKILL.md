---
name: network-map
version: "1.2.3"
description: "v1.2.3 — Network Map: compile workspace boards into one HTML map; standing compliance and health percents, collapsed side cards, and a toggleable trend from the compliance and nurse series."
---

# Network Map skill

You produce one file: `reports/network-map.html`, a self-contained
interactive map of the estate — topology, application tiers, health
problems, compliance findings, relationships, Network Ops review,
tickets. Every pixel comes from a workspace board that another agent
wrote. You collect nothing live, reason about nothing, and never
type HTML or JSON yourself. The skill script does the compile.

## The one command

`execute_command` runs only this skill's `scripts/build_map.py`.
Copy the path Studio shows for that file. It contains
`/skills/network-map/scripts/build_map.py`. The words
`Internal directory` are not a path. Never pass them to `python3`.

Each `execute_command` is a new container. The workspace is the
`file_explorer` folder beside `skills` on that same path. Copy that
directory and pass it as `--workspace`. Do not `cd`. Do not pass the
relative name `file_explorer`. Keep `--out` relative.

```text
python3 <copied build_map.py path> --workspace <copied file_explorer directory> --out reports/network-map.html
```

Stdout is one JSON line (`references/data-bundle.md`, Summary line). That line is your
validation and the source of every number in your reply. Do not read
the HTML back. Do not `--json` unless the operator asks to inspect
the bundle.

`--template <path>` only if the operator supplies a custom template.
Never pass anything else.

## What the script reads

All optional except the first. A missing board is an empty card in
the page and a `missing_boards` entry in the summary — not an error.

| Path | Feeds |
|------|-------|
| `inventory/prod.json` | nodes (`devices[]`), cables (`links[]`), lab title, collect time. **Required.** |
| `inventory/applications.json` | service → tiers → hosts, `depends_on` |
| `state/relationships.json` | compiled edges (chips, flows_to arcs, peers_with), `connected_to` fallback when `links[]` is empty |
| `state/health.json` | problems, status, `impact`, coverage, headline |
| `state/compliance.json` | scores, findings (device badges) |
| `state/testing.json` | pass/fail/error counts, risk, run link, failing and scanned devices |
| `state/network-ops.json` | review rows, last change blast radius |
| `state/servicenow.json` | headline, open counts |
| `state/network-sync.json` | inventory headline |
| `health/metadata-application.json` | probes, containers, hosts per tier |
| `health/metadata-netflow.json` | conversations, exporter state |
| `health/metadata-splunk.json` | per-device syslog buckets (`hosts` map resolves addresses) |
| `health/metadata-iosxe.json` | `series[]` for the IOS-XE trend line (clean when idle BGP and not-ready interfaces are both zero) |
| `inventory/map-layout.json` | optional operator x/y overrides; otherwise auto layout |

`references/data-bundle.md` is the column-by-column contract between
boards and the page.

## What the script writes

`reports/network-map.html` only (plus `reports/network-map.json` with
`--json`). It is a derived artifact: no envelope, no `keys`, never read
by another agent. Overwrite every run. Do not write anywhere else.

## Reply

```text
Result: ok  Wrote: reports/network-map.html (<bytes> B, generated <ts>)
Map: <nodes> devices · <links> cables (<link_source>) · <edges> edges · <problems> problems · <findings> findings · <review_rows> review rows
Application: <services joined> on <hosts_mapped joined | no host resolved>
Gaps: <one line per missing board, or "none">
Open: download reports/network-map.html and open it in a browser.
```

`Result: failed` with the script's single error line when it exits
non-zero. No raw stdout, no HTML, no JSON in the reply.

## Do not

- Write HTML, JSON, or a "quick version" with `write_file`.
- Edit or copy the template; it ships with the skill.
- Retype or guess the script path; `ls` `/skills`; run any other command.
- Call MCP tools. Freshness is whatever the boards hold; say so if the
  operator wants newer numbers (run the nurse first, then rebuild).
- Interpret the data. "What does the map show" → quote the summary line
  and point at the file.
