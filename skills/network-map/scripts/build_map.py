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
    "layout": "inventory/map-layout.json",
}

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
    override = load(ws, BOARDS["layout"])
    if mda:
        sources["md_application"] = mda.get("last_collected_at")
    if mdn:
        sources["md_netflow"] = mdn.get("last_collected_at")
    if mds:
        sources["md_splunk"] = mds.get("last_collected_at")

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
    }

    # ---- compliance + testing
    results = testing.get("results") or {}
    counts = results.get("counts_ran") or {}
    comp_out = {
        "present": bool(comp) or bool(testing),
        "headline": comp.get("headline") or testing.get("headline"),
        "updated_at": comp.get("updated_at"),
        "test_updated": testing.get("updated_at"),
        "scores": comp.get("scores") or {},
        "findings": [{k: f.get(k) for k in ("kind", "severity", "summary", "keys", "next_owner")} for f in comp.get("findings") or []],
        "counts": {k: counts.get(k, 0) for k in ("pass", "fail", "error", "skip")},
        "risk": testing.get("risk") or {},
        "run": testing.get("run") or {},
        "failing_devices": [resolve(x) or x for x in testing.get("failing_devices") or []],
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
    containers = defaultdict(list)  # tier -> rows
    hosts = {}
    for r in mda.get("current") or []:
        kind = r.get("kind")
        if kind == "probe" and r.get("application"):
            probes[r["application"]][r.get("site") or r.get("vantage_site") or "site"] = {
                "up": r.get("state") == "up", "state": r.get("state"), "http": r.get("http_code"),
                "ms": r.get("duration_ms"), "target": r.get("target"), "pct": r.get("success_pct_window")}
        elif kind == "container":
            tier = r.get("application") or (r.get("name") or "").replace("dc-", "", 1)
            containers[tier].append({
                "name": r.get("name"), "host": r.get("host"), "device": r.get("device") or resolve(r.get("host")),
                "label": r.get("application"), "state": r.get("state"), "cpu": r.get("cpu_pct"),
                "mem": round((r.get("mem_bytes") or 0) / 1048576) if r.get("mem_bytes") else None,
                "start": r.get("started_epoch"), "image": r.get("image")})
        elif kind == "host":
            hn = r.get("device") or resolve(r.get("host")) or r.get("host")
            if hn:
                hosts[hn] = {"device": r.get("device") or resolve(r.get("host")), "instance": r.get("instance"),
                             "state": r.get("state"), "boot": r.get("boot_epoch"), "mem": r.get("mem_available_pct"),
                             "fs": r.get("fs_root_avail_pct"), "ifdown": r.get("interfaces_down"), "role": r.get("role"), "site": r.get("site")}

    services = []
    app_rows = apps.get("applications") or []
    by_service = defaultdict(list)
    for a in app_rows:
        by_service[a.get("service") or "(no service)"].append(a)
    if not by_service and (probes or containers):
        by_service["(from telemetry)"] = [{"name": t} for t in sorted(set(list(probes) + list(containers)))]

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

    for svc, rows in sorted(by_service.items()):
        tiers, host_devices = [], []
        for a in rows:
            name = a.get("name")
            tier_hosts = [resolve(h) or h for h in a.get("hosts") or []]
            for c in containers.get(name, []):
                if c.get("device") and c["device"] not in tier_hosts:
                    tier_hosts.append(c["device"])
            for h in tier_hosts:
                if h not in host_devices:
                    host_devices.append(h)
            tiers.append({"name": name, "depends_on": a.get("depends_on") or [], "hosts": tier_hosts,
                          "hosts_unmapped": a.get("hosts_unmapped") or [], "status": a.get("operational_status"),
                          "probes": probes.get(name, {}), "containers": containers.get(name, [])})
        host_node = next((h for h in host_devices if h in by_name), None)
        services.append({"service": svc, "tiers": tiers, "hosts": host_devices, "host_node": host_node,
                         "path": path_to_edge(host_node)})
    app_out = {"present": bool(apps) or bool(mda), "services": services, "hosts": hosts,
               "updated_at": apps.get("updated_at"), "collected_at": mda.get("last_collected_at")}

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
