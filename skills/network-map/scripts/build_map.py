#!/usr/bin/env python3
"""Build the interactive network map from workspace boards.

Reads the shared-workspace boards (inventory, health, relationships,
compliance, testing, network-ops, servicenow, nurse metadata), compiles
one data bundle, injects it into references/template.html and writes a
single self-contained HTML file. Standard library only. No network.

Usage (from the workspace root, i.e. file_explorer):
  python3 <skill>/scripts/build_map.py --out reports/network-map.html

Prints one JSON summary line to stdout. Exit 1 with one error line on a
hard failure (no inventory, no template, cannot write).
"""
import argparse
import json
import os
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, "..", "references", "template.html")

BOARDS = {
    "inventory": "inventory/prod.json",
    "applications": "inventory/applications.json",
    "relationships": "state/relationships.json",
    "health": "state/health.json",
    "compliance": "state/compliance.json",
    "testing": "state/testing.json",
    "netops": "state/network-ops.json",
    "servicenow": "state/servicenow.json",
    "sync": "state/network-sync.json",
    "md_application": "health/metadata-application.json",
    "md_netflow": "health/metadata-netflow.json",
    "md_splunk": "health/metadata-splunk.json",
    "md_iosxe": "health/metadata-iosxe.json",
    "layout": "inventory/map-layout.json",
}

VOTING_PLANES = ("application", "netflow", "splunk", "iosxe")

PLATFORM_RANK = {"iosxe": 0, "asa": 1, "nxos": 2, "l2": 2, "linux": 3}
ROLE_RANK = {"cloud": 0, "wan": 0, "edge": 0, "hq": 1, "branch": 1}
SITE_PREF = ["cloud", "wan", "core", "datacenter", "hq", "branch"]


def load(ws, rel):
    p = os.path.join(ws, rel)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def tag_val(tags, prefix):
    for t in tags or []:
        if t.startswith(prefix):
            return t[len(prefix):]
    return None


def platform_of(dev):
    plat = (dev.get("platform") or "unknown").lower()
    nd = ((dev.get("source_metadata") or {}).get("node_definition") or "").lower()
    if plat == "iosxe" and nd in ("iosvl2",):
        return "l2"
    return plat


def site_key(site):
    s = (site or "core").lower()
    for i, pref in enumerate(SITE_PREF):
        if s.startswith(pref):
            return (i, s)
    return (len(SITE_PREF), s)


def _xy(o):
    if isinstance(o, dict) and isinstance(o.get("x"), (int, float)) and isinstance(o.get("y"), (int, float)):
        return o["x"], o["y"]
    return None


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _ratio(part, whole):
    part, whole = _num(part), _num(whole)
    if part is None or whole is None or whole <= 0:
        return None
    return round(100.0 * max(0, part) / whole, 1)


def posture_pct(point):
    """Tested posture: verified / (verified + failing), else the checks_*_all shape."""
    verified, failing = _num(point.get("verified_tests")), _num(point.get("failing_tests"))
    if verified is not None and failing is not None and verified + failing > 0:
        return round(100.0 * verified / (verified + failing), 1)
    passed = _num(point.get("checks_passed_all"))
    failed = _num(point.get("checks_failed_all"))
    errored = _num(point.get("checks_errored_all"))
    if None not in (passed, failed, errored) and passed + failed + errored > 0:
        return round(100.0 * passed / (passed + failed + errored), 1)
    return None


def check_counts(point):
    if all(_num(point.get(k)) is not None for k in ("pass", "fail", "error")):
        return {k: int(point.get(k) or 0) for k in ("pass", "fail", "error", "skip")}
    return None


def plane_series(rows, kind):
    """One percent per nurse series row. Splunk event totals are not a percent."""
    out = []
    for r in rows or []:
        if not isinstance(r, dict) or not r.get("at"):
            continue
        pct = None
        if kind == "application":
            probes = _num(r.get("probes"))
            if probes:
                pct = _ratio(probes - (_num(r.get("probes_down")) or 0), probes)
        elif kind == "netflow":
            exporters = _num(r.get("exporters"))
            if exporters:
                pct = _ratio(exporters - (_num(r.get("exporters_silent")) or 0), exporters)
        elif kind == "iosxe":
            if _num(r.get("bgp_not_established")) is not None or _num(r.get("oper_not_ready")) is not None:
                clean = (_num(r.get("bgp_not_established")) or 0) == 0 and (_num(r.get("oper_not_ready")) or 0) == 0
                pct = 100.0 if clean else 0.0
        if pct is None:
            continue
        out.append({"at": r["at"], "pct": pct})
    return out


def health_score(health):
    """100 × voting consults that are ok / voting consults present. ServiceNow does not vote."""
    consults = health.get("consults") or {}
    present = ok = 0
    for plane in VOTING_PLANES:
        row = consults.get(plane)
        if not isinstance(row, dict) or not row.get("status"):
            continue
        present += 1
        if row.get("status") == "ok":
            ok += 1
    if not present:
        return None
    return round(100.0 * ok / present, 1)


def inherit_service(rows):
    """A tier with no service takes the service of a tier that depends_on it."""
    assigned = {}
    for row in rows:
        name = row.get("name")
        if name and row.get("service"):
            assigned[name] = row["service"]
    changed = True
    while changed:
        changed = False
        for row in rows:
            svc = assigned.get(row.get("name"))
            if not svc:
                continue
            for dep in row.get("depends_on") or []:
                if dep and not assigned.get(dep):
                    assigned[dep] = svc
                    changed = True
    return assigned


def worst_devices(findings, failing):
    """Devices with the most open test-failure findings, worst first, cap 10."""
    hits = defaultdict(int)
    for f in findings:
        if f.get("kind") != "test_failure" or f.get("status") == "remediated":
            continue
        for key in f.get("keys") or []:
            if str(key).startswith("device:"):
                hits[key[7:]] += 1
    ranked = sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))
    seen = {name for name, _ in ranked}
    extra = [(name, 0) for name in failing if name not in seen]
    ranked.extend(extra)
    return [{"name": name, "findings": n} for name, n in ranked[:10]]


def layout(nodes, links, override):
    """Precedence: operator override, then CML canvas positions, then tiers."""
    if override and isinstance(override.get("nodes"), dict):
        placed = []
        for n in nodes:
            xy = _xy(override["nodes"].get(n["label"]))
            placed.append(xy)
            if xy:
                n["x"], n["y"] = xy
        if placed and all(placed):
            return "override"
    placed = [n.get("position") for n in nodes]
    if placed and all(_xy(p) for p in placed):
        for n in nodes:
            n["x"], n["y"] = _xy(n["position"])
        return "cml"
    cols = defaultdict(list)
    for n in nodes:
        cols[n["site"] or "core"].append(n)
    order = sorted(cols.keys(), key=site_key)
    rowh, gap = 130, 110
    x0 = 0
    for ci, site in enumerate(order):
        col = cols[site]
        rows = defaultdict(list)
        for n in col:
            r = ROLE_RANK.get(n["role"], 1) if n["platform"] == "iosxe" else 0
            r += PLATFORM_RANK.get(n["platform"], 2)
            if n.get("mgmt"):
                r = 5
            rows[r].append(n)
        widest = max(len(g) for g in rows.values())
        colw = max(2, widest) * gap
        for r, group in rows.items():
            group.sort(key=lambda n: n["label"])
            k = len(group)
            for i, n in enumerate(group):
                n["x"] = x0 + colw / 2 + (i - (k - 1) / 2) * gap
                n["y"] = r * rowh + (ci % 2) * 20
        x0 += colw + gap
    return "auto"


def build(ws, template_path):
    missing, sources = [], {}

    def board(name):
        d = load(ws, BOARDS[name])
        if d is None:
            missing.append(BOARDS[name])
        else:
            sources[name] = d.get("updated_at") or d.get("compiled_at") or d.get("collected_at")
        return d

    inv = board("inventory")
    if inv is None:
        raise SystemExit("error: inventory/prod.json not found in the workspace")
    apps = board("applications") or {}
    rel = board("relationships") or {}
    health = board("health") or {}
    comp = board("compliance") or {}
    testing = board("testing") or {}
    netops = board("netops") or {}
    snow = board("servicenow") or {}
    sync = board("sync") or {}
    mda = (board("md_application") or {}).get("application") or {}
    mdn = (board("md_netflow") or {}).get("netflow") or {}
    mds = (board("md_splunk") or {}).get("splunk") or {}
    mdi = (board("md_iosxe") or {}).get("iosxe") or {}
    override = load(ws, BOARDS["layout"])
    if mda:
        sources["md_application"] = mda.get("last_collected_at")
    if mdn:
        sources["md_netflow"] = mdn.get("last_collected_at")
    if mds:
        sources["md_splunk"] = mds.get("last_collected_at")
    if mdi:
        sources["md_iosxe"] = mdi.get("last_collected_at")

    # ---- nodes
    nodes, by_name = [], {}
    for d in inv.get("devices") or []:
        name = d.get("name")
        nd = ((d.get("source_metadata") or {}).get("node_definition") or "").lower()
        if not name or nd in ("external_connector", "unmanaged_switch"):
            continue
        tags = d.get("tags") or []
        n = {
            "label": name,
            "platform": platform_of(d),
            "role": (d.get("role") or "unknown").lower(),
            "site": tag_val(tags, "site:"),
            "tags": [t for t in tags if not t.startswith(("pat:", "synced:"))],
            "access": bool(d.get("agent_access")),
            "state": d.get("operational_state"),
            "mgmt": name.upper().startswith("OOB") or "oob" in [t.lower() for t in tags],
            "position": (d.get("source_metadata") or {}).get("position"),
        }
        nodes.append(n)
        by_name[name] = n
    lower = {k.lower(): k for k in by_name}

    def resolve(name):
        if not name:
            return None
        if name in by_name:
            return name
        return lower.get(str(name).lower())

    # ---- links: prod.json links[] first, else compiled connected_to edges
    links, seen = [], set()

    def add_link(a, ai, b, bi):
        a, b = resolve(a), resolve(b)
        if not a or not b or a == b:
            return
        key = tuple(sorted([(a, ai or ""), (b, bi or "")]))
        if key in seen:
            return
        seen.add(key)
        links.append({"a": a, "ai": ai or "", "b": b, "bi": bi or "",
                      "mgmt": bool(by_name[a]["mgmt"] or by_name[b]["mgmt"])})

    for l in inv.get("links") or []:
        add_link(l.get("a_device"), l.get("a_interface"), l.get("b_device"), l.get("b_interface"))
    link_source = "inventory/prod.json links[]" if links else None
    edges = rel.get("edges") or []
    if not links:
        for e in edges:
            if e.get("rel") != "connected_to" or e.get("status") == "retired":
                continue
            fa, ta = e.get("from", ""), e.get("to", "")
            if fa.startswith("interface:") and ta.startswith("interface:"):
                a, _, ai = fa[10:].partition("/")
                b, _, bi = ta[10:].partition("/")
                add_link(a, ai, b, bi)
            elif fa.startswith("device:") and ta.startswith("device:"):
                add_link(fa[7:], None, ta[7:], None)
        link_source = "state/relationships.json connected_to" if links else "none"

    layout_mode = layout(nodes, links, override)
    for n in nodes:
        n.pop("position", None)
    adj = defaultdict(set)
    for l in links:
        if not l["mgmt"]:
            adj[l["a"]].add(l["b"])
            adj[l["b"]].add(l["a"])

    # ---- health
    problems = []
    for p in health.get("problems") or []:
        problems.append({k: p.get(k) for k in ("id", "status", "keys", "hypothesis", "opened_at", "order", "impact", "outcome")})
    health_out = {
        "present": bool(health),
        "headline": health.get("headline"),
        "status": health.get("status"),
        "coverage": health.get("coverage") or {},
        "updated_at": health.get("updated_at"),
        "problems": problems,
        "assessment": health.get("assessment") or {},
        "next_action": health.get("next_action"),
        "score": health_score(health) if health else None,
        "planes": {
            "application": plane_series(mda.get("series"), "application"),
            "netflow": plane_series(mdn.get("series"), "netflow"),
            "iosxe": plane_series(mdi.get("series"), "iosxe"),
        },
    }

    # ---- compliance + testing
    findings = [{k: f.get(k) for k in ("kind", "status", "severity", "summary", "keys", "next_owner")} for f in comp.get("findings") or []]
    series_points = ((comp.get("series") or {}).get("testing") or {}).get("points") or []
    results = testing.get("results") or {}
    counts = results.get("counts_ran") or {}
    if not counts:
        for point in reversed(series_points):
            found = check_counts(point)
            if found:
                counts = found
                break
    failing = [resolve(x) or x for x in testing.get("failing_devices") or []]
    if not failing:
        for f in findings:
            if f.get("kind") != "test_failure" or f.get("status") == "remediated":
                continue
            for key in f.get("keys") or []:
                if not str(key).startswith("device:"):
                    continue
                name = resolve(key[7:]) or key[7:]
                if name not in failing:
                    failing.append(name)
    trend_src = comp.get("trend_analysis") or {}
    flips = []
    for flip in trend_src.get("flips") or []:
        if isinstance(flip, dict) and flip.get("at"):
            flips.append({k: flip.get(k) for k in ("at", "direction", "test", "device", "from", "to")})
        elif isinstance(flip, str) and flip.strip():
            flips.append({"text": flip.strip()})
    comp_out = {
        "present": bool(comp) or bool(testing),
        "headline": comp.get("headline") or testing.get("headline"),
        "updated_at": comp.get("updated_at"),
        "test_updated": testing.get("updated_at"),
        "scores": comp.get("scores") or {},
        "findings": findings,
        "trend": {
            "direction": trend_src.get("direction"),
            "environment": trend_src.get("environment"),
            "newly_passing": trend_src.get("newly_passing"),
            "newly_failing": trend_src.get("newly_failing"),
            "still_failing": trend_src.get("still_failing"),
            "narrative": trend_src.get("narrative"),
            "points": [{"at": p.get("at"), "pct": posture_pct(p)} for p in series_points if p.get("at") and posture_pct(p) is not None],
            "flips": flips,
        },
        "counts": {k: int(counts.get(k) or 0) for k in ("pass", "fail", "error", "skip")},
        "risk": testing.get("risk") or {},
        "run": testing.get("run") or {},
        "failing_devices": failing,
        "worst_devices": worst_devices(findings, failing),
        "scanned_devices": [resolve(x) or x for x in (testing.get("scope") or {}).get("devices_scanned") or []],
    }

    # ---- network ops
    netops_out = {
        "present": bool(netops),
        "headline": netops.get("headline"),
        "updated_at": netops.get("updated_at"),
        "mode": netops.get("mode"),
        "review": [{k: r.get(k) for k in ("rank", "devices", "interfaces", "finding", "kind", "proposed", "verified_in_git", "problem_ref")} for r in netops.get("review") or []],
        "change": {k: (netops.get("change") or {}).get(k) for k in ("devices", "interfaces", "blast_radius", "annotation_ref")} if netops.get("change") else None,
    }

    # ---- servicenow
    snow_out = {
        "present": bool(snow),
        "headline": snow.get("headline"),
        "updated_at": snow.get("updated_at"),
        "open": snow.get("open") or {},
        "next_action": snow.get("next_action"),
    }

    # ---- application
    probes = defaultdict(dict)   # tier -> site -> row
    container_rows = []  # every container Health Application wrote from Grafana
    hosts = {}
    for r in mda.get("current") or []:
        kind = r.get("kind")
        if kind == "probe" and r.get("application"):
            probes[r["application"]][r.get("site") or r.get("vantage_site") or "site"] = {
                "up": r.get("state") == "up", "state": r.get("state"), "http": r.get("http_code"),
                "ms": r.get("duration_ms"), "target": r.get("target"), "pct": r.get("success_pct_window")}
        elif kind == "container":
            container_rows.append({
                "name": r.get("name"), "host": r.get("host"), "device": r.get("device") or resolve(r.get("host")),
                "application": r.get("application"), "service": r.get("service"),
                "label": r.get("application"), "state": r.get("state"), "cpu": r.get("cpu_pct"),
                "mem": round((r.get("mem_bytes") or 0) / 1048576) if r.get("mem_bytes") else None,
                "rx": r.get("rx_bytes_s"), "start": r.get("started_epoch"), "image": r.get("image")})
        elif kind == "host":
            hn = r.get("device") or resolve(r.get("host")) or r.get("host")
            if hn:
                hosts[hn] = {"device": r.get("device") or resolve(r.get("host")), "instance": r.get("instance"),
                             "state": r.get("state"), "boot": r.get("boot_epoch"), "mem": r.get("mem_available_pct"),
                             "fs": r.get("fs_root_avail_pct"), "ifdown": r.get("interfaces_down"), "role": r.get("role"), "site": r.get("site")}

    services = []
    app_rows = apps.get("applications") or []
    inherited = inherit_service(app_rows)
    by_service = defaultdict(list)
    for a in app_rows:
        by_service[inherited.get(a.get("name")) or a.get("service") or "(no service)"].append(a)
    if not by_service and (probes or container_rows):
        names = set(probes)
        for c in container_rows:
            if c.get("application"):
                names.add(c["application"])
            elif c.get("name"):
                names.add(c["name"])
        by_service["(from telemetry)"] = [{"name": t} for t in sorted(names)]

    def path_to_edge(start):
        """BFS from a host device over non-mgmt links until an iosxe edge/wan device."""
        if not start or start not in by_name:
            return []
        prev, q, seen_ = {start: None}, deque([start]), {start}
        while q:
            cur = q.popleft()
            n = by_name[cur]
            if cur != start and n["platform"] == "iosxe" and n["role"] in ("edge", "wan", "cloud", "hq", "branch"):
                out = []
                while cur is not None:
                    out.append(cur)
                    cur = prev[cur]
                return out[::-1]
            for nb in sorted(adj[cur]):
                if nb not in seen_:
                    seen_.add(nb)
                    prev[nb] = cur
                    q.append(nb)
        return [start]

    tier_names = sorted({a.get("name") for a in app_rows if a.get("name")}, key=len, reverse=True)

    def container_tier(c):
        """CMDB tier for a container. Exact label, else a hyphen prefix plus the tier (`dc-api` → `api`)."""
        labels = [c.get("application"), c.get("name")]
        for label in labels:
            if label in tier_names:
                return label
        for label in labels:
            if not label:
                continue
            for tier in tier_names:
                if label.endswith("-" + tier):
                    return tier
        return None

    def containers_for(name):
        hit = []
        for c in container_rows:
            if c.get("_used"):
                continue
            if container_tier(c) == name:
                c["_used"] = True
                hit.append(c)
        return hit

    for svc, rows in sorted(by_service.items()):
        tiers, host_devices = [], []
        for a in rows:
            name = a.get("name")
            # Application Map files a host as unmapped when it missed prod.json.
            # Inventory may have the device now. Resolve again and walk from it.
            tier_hosts, still_unmapped = [], []
            for h in list(a.get("hosts") or []) + list(a.get("hosts_unmapped") or []):
                rh = resolve(h)
                if rh and rh not in tier_hosts:
                    tier_hosts.append(rh)
                elif not rh and h not in still_unmapped:
                    still_unmapped.append(h)
            tier_containers = containers_for(name)
            for c in tier_containers:
                if c.get("device") and c["device"] not in tier_hosts:
                    tier_hosts.append(c["device"])
            for h in tier_hosts:
                if h not in host_devices:
                    host_devices.append(h)
            tiers.append({"name": name, "depends_on": a.get("depends_on") or [], "hosts": tier_hosts,
                          "hosts_unmapped": still_unmapped, "status": a.get("operational_status"),
                          "probes": probes.get(name, {}), "containers": tier_containers})
        host_node = next((h for h in host_devices if h in by_name), None)
        services.append({"service": svc, "tiers": tiers, "hosts": host_devices, "host_node": host_node,
                         "path": path_to_edge(host_node)})
    # Container rows Health Application wrote that matched no inventory tier.
    # Keep the Grafana label. Do not rename it.
    extra = defaultdict(list)
    for c in container_rows:
        if c.get("_used"):
            continue
        label = c.get("application") or c.get("name") or "(container)"
        extra[(c.get("service") or "(from telemetry)", label)].append(c)
    existing = {s["service"]: s for s in services}
    for (svc, label), rows in sorted(extra.items()):
        hosts_here = []
        for c in rows:
            if c.get("device") and c["device"] not in hosts_here:
                hosts_here.append(c["device"])
        tier = {"name": label, "depends_on": [], "hosts": hosts_here,
                "hosts_unmapped": [], "status": None, "probes": {}, "containers": rows}
        card = existing.get(svc)
        if card is None:
            host_node = next((h for h in hosts_here if h in by_name), None)
            card = {"service": svc, "tiers": [], "hosts": [], "host_node": host_node,
                    "path": path_to_edge(host_node)}
            services.append(card)
            existing[svc] = card
        card["tiers"].append(tier)
        for h in hosts_here:
            if h not in card["hosts"]:
                card["hosts"].append(h)
        if card["host_node"] is None:
            card["host_node"] = next((h for h in card["hosts"] if h in by_name), None)
            card["path"] = path_to_edge(card["host_node"])
    for c in container_rows:
        c.pop("_used", None)
    probe_n = probe_up = 0
    for tier_probes in probes.values():
        for row in tier_probes.values():
            probe_n += 1
            if row.get("up"):
                probe_up += 1
    app_out = {"present": bool(apps) or bool(mda), "services": services, "hosts": hosts,
               "updated_at": apps.get("updated_at"), "collected_at": mda.get("last_collected_at"),
               "score": _ratio(probe_up, probe_n)}

    # ---- syslog buckets per device
    syslog = defaultdict(lambda: defaultdict(int))
    addr_map = {str(k): v for k, v in (mds.get("hosts") or {}).items()}
    for r in mds.get("current") or []:
        dev = r.get("name") or r.get("subject")
        dev = resolve(dev) or resolve(addr_map.get(str(r.get("source_ip")))) or dev
        if not dev or r.get("kind") in (None, "visit"):
            continue
        syslog[dev][r.get("kind")] += int(r.get("count") or 0)
    syslog_out = {k: dict(v) for k, v in syslog.items()}

    # ---- flows
    flows = []
    for r in mdn.get("current") or []:
        if r.get("kind") != "conversation":
            continue
        flows.append({"exp": r.get("exporter") or r.get("exporter_name"), "src": r.get("src_device") or r.get("src"),
                      "dst": r.get("dst_device") or r.get("dst"), "port": r.get("dst_port"), "proto": r.get("protocol"),
                      "bytes": r.get("bytes") or 0, "state": r.get("state")})
    flows.sort(key=lambda f: -(f["bytes"] or 0))
    flows = flows[:25]
    exporters = [{"name": e.get("name") or e.get("exporter_name"), "state": e.get("state")} for e in mdn.get("exporters") or [] if isinstance(e, dict)]

    edges_out = [{k: e.get(k) for k in ("from", "to", "rel", "basis", "status", "sources", "last_seen")} for e in edges]

    bundle = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lab": inv.get("lab_title") or (inv.get("source") or {}).get("name") or "network",
        "environment": inv.get("environment"),
        "sources": sources,
        "missing": missing,
        "layout": layout_mode,
        "link_source": link_source,
        "nodes": nodes,
        "links": links,
        "edges": edges_out,
        "rel_head": rel.get("headline"),
        "rel_updated": rel.get("compiled_at") or rel.get("updated_at"),
        "drift": rel.get("drift") or [],
        "health": health_out,
        "compliance": comp_out,
        "netops": netops_out,
        "snow": snow_out,
        "sync": {"headline": sync.get("headline"), "updated_at": sync.get("updated_at"),
                 "coverage": ((sync.get("inventories") or {}).get("prod") or {}).get("current_snapshot", {}).get("coverage") if sync else None,
                 "device_count": len(nodes), "collected_at": inv.get("collected_at"),
                 "status": inv.get("status")},
        "app": app_out,
        "syslog": syslog_out,
        "flows": flows,
        "exporters": exporters,
    }
    with open(template_path, encoding="utf-8") as fh:
        tpl = fh.read()
    if "__DATA__" not in tpl:
        raise SystemExit("error: template has no __DATA__ placeholder")
    data = json.dumps(bundle, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return tpl.replace("__DATA__", data, 1), bundle


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workspace", default=".", help="workspace root (default: cwd)")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--out", default="reports/network-map.html", help="output path, relative to workspace")
    ap.add_argument("--json", action="store_true", help="also write the data bundle next to --out as .json")
    a = ap.parse_args()
    if not os.path.isfile(a.template):
        print("error: template not found: %s" % a.template)
        sys.exit(1)
    try:
        html, bundle = build(a.workspace, a.template)
        out = os.path.join(a.workspace, a.out)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html)
        if a.json:
            with open(os.path.splitext(out)[0] + ".json", "w", encoding="utf-8") as fh:
                json.dump(bundle, fh, indent=1, ensure_ascii=False)
    except SystemExit as e:
        print(str(e))
        sys.exit(1)
    except Exception as e:  # one line, no traceback for the agent
        print("error: %s: %s" % (type(e).__name__, e))
        sys.exit(1)
    summary = {
        "result": "ok",
        "wrote": a.out,
        "bytes": len(html.encode("utf-8")),
        "generated": bundle["generated"],
        "nodes": len(bundle["nodes"]),
        "links": len(bundle["links"]),
        "link_source": bundle["link_source"],
        "layout": bundle["layout"],
        "edges": len(bundle["edges"]),
        "problems": len(bundle["health"]["problems"]),
        "findings": len(bundle["compliance"]["findings"]),
        "review_rows": len(bundle["netops"]["review"]),
        "services": [s["service"] for s in bundle["app"]["services"]],
        "hosts_mapped": [s["host_node"] for s in bundle["app"]["services"] if s["host_node"]],
        "missing_boards": bundle["missing"],
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
