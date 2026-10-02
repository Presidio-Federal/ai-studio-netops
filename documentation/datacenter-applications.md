# Datacenter applications

How the chart learns what runs on the datacenter hosts, what each
plane observes about it, and how a change or an incident is read
back as application impact. Nothing here is a new MCP tool; the
generic Grafana tools and one scoped ServiceNow reader are enough.

## The model

An **application** is a tier the CMDB names (`web`, `api`,
`database`). A **service** is the business service those tiers
compose (`Order Management`). A **host** is a `prod.json` device
that is not a router or switch — the Ubuntu node the containers run
on. Routers and switches stay `device:`; the application sits on top
of them through edges, never through a hostname convention.

Three layers, three writers:

| Layer | Says | Writer | File |
|-------|------|--------|------|
| Intended | service → tiers → tiers → hosts, from the CMDB | Application Map | `inventory/applications.json` |
| Observed | which container actually runs on which host, which probe watches which tier, which flows cross which exporter | Health Application, Health Monitor (NetFlow) | `health/metadata-application.json`, `health/metadata-netflow.json` |
| Compiled | the two above as one edge set, with drift where they disagree | Relationship agent | `state/relationships.json` |

Readers (Analyzer, Network Ops, Network Design) open only the
compiled file. They never open `inventory/applications.json`
directly; if the compiler has not run, the walk returns `none`.

## Naming contract

The CMDB application `name` **is** the Grafana `service` label on
the probe and on the container. That one spelling joins intended to
observed. If the two drift the compiler reports it as
`depends_on` drift and the Analyzer's impact walk stops short — fix
the label or the CI, not the prompt.

Keys: `application:<name>`, `service:<name>` (only names in
`inventory/services.json`), `device:<host>`, `site:<site>`,
`test:probe/<application>@<vantage_point>`. A TCP port is never an
application. A container name is not a key; it is a column on the
container row.

Lab CIs carry the CML lab title in `comments` so every CMDB query is
scoped `commentsLIKE<marker>`. The seed contract is
`skills/application-map/references/cmdb-seed.md`.

## What each plane observes

| Plane | Rows | Edge columns copied by the compiler |
|-------|------|-------------------------------------|
| Application — probes | `probe:<application>@<vantage>` success, HTTP code, latency, success % over the window | `test:probe/… tests application:`, `application: located_at site:` |
| Application — containers | `container:<host>/<name>` started, cpu, memory, rx | `application: depends_on device:<host>` (observed) |
| Application — hosts | `host:<host>` boot, memory, root fs, interfaces down | `device: located_at site:` |
| Application — annotations | Grafana annotations tagged `change:*` in the window | none; the Analyzer reads them for change follow-up |
| NetFlow — exporters | per exporter bytes / flows, `reporting` / `silent` | none |
| NetFlow — conversations | top client→server pairs with resolved `src_device`, `dst_device`, `exporter` | `device: flows_to device:`, each end `traverses device:<exporter>` |
| CMDB (Application Map) | `cmdb_ci_appl`, `cmdb_ci_service`, `cmdb_ci_server`, `cmdb_rel_ci` | intended `service: depends_on application:`, `application: depends_on application:`, `application: depends_on device:` |

East-west tier traffic inside the host is not exported, so the
api→database path is invisible to NetFlow; the compiler does not
invent an application↔application flow edge from it. The intended
`depends_on` chain from the CMDB carries that dependency.

## Reading impact (Health Analyzer)

For every problem the Analyzer walks `state/relationships.json`
upward from the problem's keys and writes `problems[].impact`:

1. hosts — the devices named plus anything `flows_to` / `traverses`
   touches;
2. applications — `depends_on` rows onto those hosts, then
   `depends_on` rows onto those applications, until nothing is
   added;
3. services — `depends_on` rows from a `service:` onto a collected
   application;
4. `basis` — `intended`, `observed`, `both`, or `none`.

Names are copied from edges with the prefix stripped. Nothing is
inferred from a hostname, a role, or a port. `impact` names are
not chart keys. The reply shows them on each problem line
(`— impact: database, api, web; Order Management`).

Change follow-up: a `change:` annotation on the application board
inside the window **and** a `changed` edge in the compiled set →
the hypothesis says the symptom *follows* that change. Annotation
alone → *coincides with*; no cause is named.

## Reading blast radius (Network Ops)

Before any prescription Network Ops walks the same file from the
target devices and interfaces instead of from a symptom, and writes
`change.blast_radius` (`hosts[]`, `applications[]`, `services[]`,
`basis`, `source_ref`). It is reported — `Blast radius:` reply line,
PR body — and never a reason to stop an authorized change. After a
merge Network Ops creates one Grafana annotation tagged
`change:<sha>` and each `device:<d>`, and asserts
`change:<sha> impacted application:<a>` for each application in the
radius. The Health Application nurse copies the annotation onto its
board on the next visit; the Analyzer then has the change next to
the probes.

## Order of operations on a fresh workspace

1. Ops ServiceNow Operator — services registry
   (`inventory/services.json`; Order Management from the CMDB).
2. Application Map — `inventory/applications.json`.
3. Health Application and Health Monitor (NetFlow) — boards.
4. Relationship agent — `state/relationships.json` with intended
   and observed `depends_on`, `flows_to`, `traverses`.
5. Health Analyzer — `impact` on problems.
6. Network Ops — `blast_radius` on changes.
7. Network Map — `reports/network-map.html`, the picture of 1–6.

Until step 4 has run, both walks return `basis none` with empty
arrays. That is the honest answer, not a gap.

## Names must match

The walks and the map join on names, and three systems spell them:
the CML node label becomes `prod.json` `devices[].name`; Prometheus
`host_name` must equal that name for Health Application to resolve
a host or container to a device; the cAdvisor `service` label must
equal the CMDB tier name for the container to land on the same
`application:` node as the probe and the CMDB row. A host whose CML
label differs from its `host_name` is invisible to every walk.

## Network map

The Network Map agent runs `network-map` `scripts/build_map.py`
once; the script reads the boards above plus `state/compliance.json`,
`state/testing.json`, `state/network-ops.json`, `state/servicenow.json`
and the splunk board, and writes one self-contained interactive HTML.
Cables come from `prod.json` `links[]` (Ops Network Sync copies
them from the CML lab), so the host → switch → firewall → edge path
is drawn even before NetFlow sees it. Node positions come from the
CML canvas (`source_metadata.position`, Sync 2.5.2) when every device
has one; otherwise the page lays nodes out by site and role. Click a device for its
problems, findings, review rows, syslog buckets, cables and compiled
edges; click an app tier to trace its path to the WAN; click a
problem or finding to light up its devices. The page is as fresh as
the boards; its footer lists each board's own timestamp.

## Not here

No application↔application flow edges from NetFlow. No `service:`
key from a Grafana label. No CMDB writes by any agent — the seed is
an operator step. No Loki or Tempo. The ServiceNow nurse has no
typed `application` column; tickets join the walk through
`service:` and `device:` keys.
