#!/usr/bin/env python3
"""Compile state/relationships.json from columns other writers already filled.

Runs under execution_type standard. It does not call MCP and it does
not infer an edge. The table is references/compile.md.

  python3 <skill>/scripts/compile_graph.py compile --workspace <file_explorer>
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace-handoff" / "scripts"))

try:
    import visit_common  # noqa: E402
except ImportError:
    print(
        '{"error": "visit_common missing; attach the workspace-handoff skill"}',
        file=sys.stderr,
    )
    sys.exit(1)

SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "relationships-state.schema.json"
KEY_RE = re.compile(
    r"^((device|site|service|test|control|incident|change|application):[^ ].*|interface:[^ /]+/[^ ].*)$"
)
SYMMETRIC = {"connected_to", "peers_with"}


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp_text(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0)


def blank(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def strip_arg(value):
    return str(value or "").strip().strip("'\"")


def load(ws, rel):
    path = Path(ws) / rel
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def plane(board, name):
    if not isinstance(board, dict):
        return {}
    nested = board.get(name)
    if isinstance(nested, dict):
        return nested
    return board


def key_ok(value):
    return isinstance(value, str) and KEY_RE.match(value) is not None


def device_key(value):
    text = blank(value)
    if not text:
        return None
    if text.startswith("device:"):
        return text if key_ok(text) else None
    formed = "device:%s" % text
    return formed if key_ok(formed) else None


def interface_key(device, interface):
    if not blank(device) or not blank(interface):
        return None
    if "/" in str(interface):
        formed = "interface:%s" % interface if str(interface).startswith(str(device) + "/") else "interface:%s/%s" % (device, interface)
    else:
        formed = "interface:%s/%s" % (device, interface)
    return formed if key_ok(formed) else None


def order_pair(left, right):
    if left <= right:
        return left, right
    return right, left


def add_edge(bag, source, target, rel, basis, when, path, side=None):
    if not key_ok(source) or not key_ok(target) or source == target or not when:
        return
    if rel in SYMMETRIC and basis == "observed":
        source, target = order_pair(source, target)
    ident = (source, target, rel, basis)
    row = bag.setdefault(ident, {
        "from": source,
        "to": target,
        "rel": rel,
        "basis": basis,
        "when": when,
        "path": path,
        "sides": set(),
    })
    if parse_time(when) and (parse_time(row["when"]) is None or parse_time(when) >= parse_time(row["when"])):
        row["when"] = when
    if side:
        row["sides"].add(side)


def copy_edges(sources):
    bag = {}
    topo = sources.get("inventory/topology-observed.json") or {}
    for device in topo.get("devices") or []:
        if not isinstance(device, dict):
            continue
        when = blank(device.get("probed_at")) or blank(topo.get("mapped_at"))
        name = blank(device.get("name"))
        for neighbor in device.get("neighbors") or []:
            if not isinstance(neighbor, dict) or not key_ok(neighbor.get("far")) or not key_ok(neighbor.get("local")):
                continue
            add_edge(
                bag, neighbor["local"], neighbor["far"], "connected_to", "observed", when,
                "inventory/topology-observed.json", side=name or neighbor["local"],
            )
    ios = plane(sources.get("health/metadata-iosxe.json"), "iosxe")
    when = blank(ios.get("last_collected_at"))
    for row in ios.get("current") or []:
        if isinstance(row, dict) and row.get("kind") == "bgp" and device_key(row.get("name")) and device_key(row.get("peer")):
            add_edge(bag, device_key(row.get("name")), device_key(row.get("peer")), "peers_with", "observed", when, "health/metadata-iosxe.json", side=row.get("name"))
    splunk = plane(sources.get("health/metadata-splunk.json"), "splunk")
    when = blank(splunk.get("last_collected_at"))
    for row in splunk.get("current") or []:
        if isinstance(row, dict) and row.get("kind") == "bgp" and device_key(row.get("name")) and device_key(row.get("peer")):
            add_edge(bag, device_key(row.get("name")), device_key(row.get("peer")), "peers_with", "observed", when, "health/metadata-splunk.json", side=row.get("name"))
    net = plane(sources.get("health/metadata-netflow.json"), "netflow")
    when = blank(net.get("last_collected_at"))
    for row in net.get("current") or []:
        if not isinstance(row, dict) or row.get("kind") != "conversation":
            continue
        src = device_key(row.get("src_device"))
        dst = device_key(row.get("dst_device"))
        exporter = device_key(row.get("exporter")) or device_key(row.get("device"))
        if src and dst and src != dst:
            add_edge(bag, src, dst, "flows_to", "observed", when, "health/metadata-netflow.json")
        if exporter and src and exporter != src:
            add_edge(bag, src, exporter, "traverses", "observed", when, "health/metadata-netflow.json")
        if exporter and dst and exporter != dst:
            add_edge(bag, dst, exporter, "traverses", "observed", when, "health/metadata-netflow.json")
    app = plane(sources.get("health/metadata-application.json"), "application")
    when = blank(app.get("last_collected_at"))
    for row in app.get("current") or []:
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        application = blank(row.get("application"))
        if kind == "probe" and application:
            test = next((key for key in (row.get("keys") or []) if isinstance(key, str) and key.startswith("test:")), None)
            if key_ok(test):
                add_edge(bag, test, "application:%s" % application, "tests", "observed", when, "health/metadata-application.json")
            if blank(row.get("site")) and key_ok("application:%s" % application) and key_ok("site:%s" % row["site"]):
                add_edge(bag, "application:%s" % application, "site:%s" % row["site"], "located_at", "observed", when, "health/metadata-application.json")
        if kind == "container" and application and device_key(row.get("device")) and key_ok("application:%s" % application):
            add_edge(bag, "application:%s" % application, device_key(row.get("device")), "depends_on", "observed", when, "health/metadata-application.json")
        if kind == "host" and device_key(row.get("device")) and blank(row.get("site")) and key_ok("site:%s" % row["site"]):
            add_edge(bag, device_key(row.get("device")), "site:%s" % row["site"], "located_at", "observed", when, "health/metadata-application.json")
    apps = sources.get("inventory/applications.json") or {}
    when = blank(apps.get("updated_at")) or blank(apps.get("source_updated_at"))
    for row in apps.get("applications") or []:
        if not isinstance(row, dict) or not blank(row.get("name")):
            continue
        name = "application:%s" % row["name"]
        if not key_ok(name):
            continue
        if blank(row.get("service")) and key_ok("service:%s" % row["service"]):
            add_edge(bag, "service:%s" % row["service"], name, "depends_on", "intended", when, "inventory/applications.json")
        for host in row.get("hosts") or []:
            if device_key(host):
                add_edge(bag, name, device_key(host), "depends_on", "intended", when, "inventory/applications.json")
        for other in row.get("depends_on") or []:
            target = other if str(other).startswith("application:") else "application:%s" % other
            if key_ok(target):
                add_edge(bag, name, target, "depends_on", "intended", when, "inventory/applications.json")
    snow = plane(sources.get("health/metadata-servicenow.json"), "servicenow")
    when = blank(snow.get("last_collected_at"))
    for row in snow.get("current") or []:
        if not isinstance(row, dict) or not blank(row.get("number")):
            continue
        keys = [key for key in (row.get("keys") or []) if key_ok(key)]
        if row.get("type") == "incident":
            source = "incident:%s" % row["number"]
            if not key_ok(source):
                continue
            if blank(row.get("device")):
                for key in keys:
                    if key.startswith("device:"):
                        add_edge(bag, source, key, "impacted", "observed", when, "health/metadata-servicenow.json")
            if blank(row.get("interface")):
                for key in keys:
                    if key.startswith("interface:"):
                        add_edge(bag, source, key, "impacted", "observed", when, "health/metadata-servicenow.json")
            if blank(row.get("service")):
                for key in keys:
                    if key.startswith("service:"):
                        add_edge(bag, source, key, "impacted", "observed", when, "health/metadata-servicenow.json")
            if blank(row.get("rfc")) and key_ok("change:%s" % row["rfc"]):
                add_edge(bag, source, "change:%s" % row["rfc"], "resolved_by", "observed", when, "health/metadata-servicenow.json")
        if row.get("type") == "change":
            source = "change:%s" % row["number"]
            if not key_ok(source):
                continue
            if blank(row.get("device")):
                for key in keys:
                    if key.startswith("device:"):
                        add_edge(bag, source, key, "changed", "observed", when, "health/metadata-servicenow.json")
            if blank(row.get("interface")):
                for key in keys:
                    if key.startswith("interface:"):
                        add_edge(bag, source, key, "changed", "observed", when, "health/metadata-servicenow.json")
    health = sources.get("state/health.json") or {}
    when = blank(health.get("updated_at"))
    for row in health.get("relations") or []:
        if isinstance(row, dict) and key_ok(row.get("from")) and key_ok(row.get("to")) and row.get("rel"):
            add_edge(bag, row["from"], row["to"], row["rel"], "asserted", when, "state/health.json")
    ops = sources.get("state/network-ops.json") or {}
    when = blank(ops.get("updated_at"))
    for row in ops.get("relations") or []:
        if isinstance(row, dict) and key_ok(row.get("from")) and key_ok(row.get("to")) and row.get("rel"):
            add_edge(bag, row["from"], row["to"], row["rel"], "asserted", when, "state/network-ops.json")
    change = ops.get("change") if isinstance(ops.get("change"), dict) else {}
    sha = blank((ops.get("git") or {}).get("commit_sha")) or blank(change.get("commit_sha")) or blank(ops.get("commit_sha"))
    if ops.get("status") == "merged" and sha and key_ok("change:%s" % sha):
        for device in change.get("devices") or []:
            if device_key(device):
                add_edge(bag, "change:%s" % sha, device_key(device), "changed", "observed", when, "state/network-ops.json")
        for interface in change.get("interfaces") or []:
            formed = interface if str(interface).startswith("interface:") else "interface:%s" % interface
            if key_ok(formed):
                add_edge(bag, "change:%s" % sha, formed, "changed", "observed", when, "state/network-ops.json")
    run = sources.get("_ops_run") or {}
    run_path = sources.get("_ops_run_path")
    run_sha = blank((run.get("git") or {}).get("commit_sha"))
    run_when = blank(run.get("updated_at"))
    if run_path and run_sha and key_ok("change:%s" % run_sha):
        for device in run.get("devices") or []:
            if device_key(device):
                add_edge(bag, "change:%s" % run_sha, device_key(device), "changed", "observed", run_when, run_path)
        for interface in run.get("interfaces") or []:
            formed = interface if str(interface).startswith("interface:") else "interface:%s" % interface
            if key_ok(formed):
                add_edge(bag, "change:%s" % run_sha, formed, "changed", "observed", run_when, run_path)
    prod = sources.get("inventory/prod.json") or {}
    when = blank(prod.get("collected_at")) or blank(prod.get("snapshot_id")) or blank(prod.get("updated_at"))
    for link in prod.get("links") or []:
        if not isinstance(link, dict):
            continue
        left = interface_key(link.get("a_device"), link.get("a_interface"))
        right = interface_key(link.get("b_device"), link.get("b_interface"))
        if left and right:
            add_edge(bag, left, right, "connected_to", "intended", when, "inventory/prod.json")
    test_run = sources.get("_test_run") or {}
    test_path = sources.get("_test_run_path")
    test_when = blank(test_run.get("updated_at"))
    ran = ((test_run.get("results") or {}).get("ran") or []) if test_path else []
    for row in ran:
        if not isinstance(row, dict) or not device_key(row.get("device")):
            continue
        keys = [key for key in (row.get("keys") or []) if key_ok(key)]
        test = next((key for key in keys if key.startswith("test:")), None)
        if test:
            add_edge(bag, test, device_key(row.get("device")), "tests", "observed", test_when, test_path)
        for key in keys:
            if key.startswith("control:"):
                add_edge(bag, key, device_key(row.get("device")), "checks", "observed", test_when, test_path)
    return bag


def upsert(produced, prior_edges, compiled_at):
    prior = {}
    for edge in prior_edges or []:
        if isinstance(edge, dict) and key_ok(edge.get("from")) and key_ok(edge.get("to")):
            prior[(edge["from"], edge["to"], edge.get("rel"), edge.get("basis"))] = edge
    compiled = parse_time(compiled_at) or now_utc()
    rows = []
    fresh = 0
    for ident, item in produced.items():
        old = prior.get(ident)
        sides = len(item["sides"]) if item["rel"] in SYMMETRIC and item["basis"] == "observed" else None
        if sides == 0:
            sides = 1
        if sides is not None:
            sides = 2 if sides >= 2 else 1
        if old:
            last = item["when"]
            if parse_time(old.get("last_seen")) and parse_time(item["when"]) and parse_time(old["last_seen"]) > parse_time(item["when"]):
                last = old["last_seen"]
            sources = list(old.get("sources") or [])
            if item["path"] not in sources:
                sources.append(item["path"])
            row = {
                "from": ident[0],
                "to": ident[1],
                "rel": ident[2],
                "basis": ident[3],
                "sides": sides,
                "first_seen": old.get("first_seen") or item["when"],
                "last_seen": last,
                "seen_count": int(old.get("seen_count") or 1) + 1,
                "sources": sources[-5:],
                "status": "current",
            }
        else:
            fresh += 1
            row = {
                "from": ident[0],
                "to": ident[1],
                "rel": ident[2],
                "basis": ident[3],
                "sides": sides,
                "first_seen": item["when"],
                "last_seen": item["when"],
                "seen_count": 1,
                "sources": [item["path"]],
                "status": "current",
            }
        rows.append(row)
    seen = set(produced)
    for ident, old in prior.items():
        if ident in seen:
            continue
        rows.append({
            "from": old["from"],
            "to": old["to"],
            "rel": old["rel"],
            "basis": old["basis"],
            "sides": old.get("sides"),
            "first_seen": old.get("first_seen") or old.get("last_seen"),
            "last_seen": old.get("last_seen") or old.get("first_seen"),
            "seen_count": int(old.get("seen_count") or 1),
            "sources": list(old.get("sources") or ["prior"])[-5:],
            "status": "current",
        })
    newly_stale = 0
    for row in rows:
        seen_at = parse_time(row.get("last_seen"))
        age = (compiled - seen_at) if seen_at else timedelta(days=999)
        if row["basis"] == "intended":
            row["status"] = "current"
        elif row["basis"] == "asserted" and age > timedelta(days=30):
            row["status"] = "stale"
        elif row["basis"] == "observed" and age > timedelta(days=7):
            row["status"] = "stale"
        else:
            row["status"] = "current"
        old = prior.get((row["from"], row["to"], row["rel"], row["basis"]))
        if row["status"] == "stale" and (not old or old.get("status") != "stale"):
            newly_stale += 1
    if len(rows) > 500:
        stale = sorted((row for row in rows if row["status"] == "stale"), key=lambda row: row.get("last_seen") or "")
        drop = set(id(row) for row in stale[: len(rows) - 500])
        rows = [row for row in rows if id(row) not in drop]
    return rows, fresh, newly_stale


def drift_rows(edges, applications_read, prior_drift, compiled_at):
    current = [edge for edge in edges if edge["status"] == "current"]
    intended_cables = {(edge["from"], edge["to"]) for edge in current if edge["rel"] == "connected_to" and edge["basis"] == "intended"}
    observed_cables = {(edge["from"], edge["to"]) for edge in current if edge["rel"] == "connected_to" and edge["basis"] == "observed"}
    prior = {}
    for row in prior_drift or []:
        if isinstance(row, dict):
            prior[(row.get("from"), row.get("to"), row.get("rel"), row.get("kind"))] = row.get("since")
    found = []
    if intended_cables:
        for pair in sorted(intended_cables - observed_cables):
            found.append(("connected_to", pair[0], pair[1], "intended_not_observed", "inventory/prod.json"))
        for pair in sorted(observed_cables - intended_cables):
            found.append(("connected_to", pair[0], pair[1], "observed_not_intended", "inventory/topology-observed.json"))
    if applications_read:
        declared = {row.get("name") for row in ((applications_read.get("applications") or [])) if isinstance(row, dict)}
        intended_hosts = {(edge["from"], edge["to"]) for edge in current if edge["rel"] == "depends_on" and edge["basis"] == "intended" and str(edge["to"]).startswith("device:") and str(edge["from"]).startswith("application:")}
        observed_hosts = {(edge["from"], edge["to"]) for edge in current if edge["rel"] == "depends_on" and edge["basis"] == "observed" and str(edge["to"]).startswith("device:") and str(edge["from"]).startswith("application:")}
        for pair in sorted(intended_hosts - observed_hosts):
            found.append(("depends_on", pair[0], pair[1], "intended_not_observed", "inventory/applications.json"))
        for pair in sorted(observed_hosts - intended_hosts):
            name = pair[0].split(":", 1)[1]
            if name in declared:
                found.append(("depends_on", pair[0], pair[1], "observed_not_intended", "health/metadata-application.json"))
    rows = []
    for rel, source, target, kind, evidence in found[:100]:
        if not key_ok(source) or not key_ok(target):
            continue
        rows.append({
            "from": source,
            "to": target,
            "rel": rel,
            "kind": kind,
            "evidence_ref": evidence,
            "since": prior.get((source, target, rel, kind)) or compiled_at,
        })
    return rows


def union_keys(edges):
    found = []
    for edge in edges:
        for key in (edge["from"], edge["to"]):
            if key not in found and key_ok(key):
                found.append(key)
    return found


def resolve_workspace(given):
    raw = Path(strip_arg(given))
    candidates = [raw] if raw.is_absolute() else [raw, Path.cwd() / raw]
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.is_dir():
            print("relationships workspace=%s" % resolved, file=sys.stderr)
            return resolved
    print('{"error": "workspace directory missing"}', file=sys.stderr)
    return None


def cmd_compile(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    prior = load(ws, "state/relationships.json") or {}
    sources = {}
    read = []
    missing = []
    fixed = [
        "inventory/topology-observed.json",
        "health/metadata-iosxe.json",
        "health/metadata-splunk.json",
        "health/metadata-netflow.json",
        "health/metadata-application.json",
        "inventory/applications.json",
        "health/metadata-servicenow.json",
        "state/health.json",
        "state/network-ops.json",
        "inventory/prod.json",
        "state/testing.json",
    ]
    if prior:
        read.append("state/relationships.json")
    for rel in fixed:
        doc = load(ws, rel)
        if doc is None:
            missing.append(rel)
            continue
        sources[rel] = doc
        read.append(rel)
    ops = sources.get("state/network-ops.json") or {}
    change = ops.get("change") if isinstance(ops.get("change"), dict) else {}
    ops_run = blank(change.get("operational_ref"))
    if ops_run:
        doc = load(ws, ops_run)
        if doc is None:
            missing.append(ops_run)
        else:
            sources["_ops_run"] = doc
            sources["_ops_run_path"] = ops_run
            read.append(ops_run)
    testing = sources.get("state/testing.json") or {}
    latest = blank(testing.get("latest"))
    if isinstance(testing.get("latest"), dict):
        latest = blank(testing["latest"].get("path") or testing["latest"].get("source_ref"))
    if latest:
        doc = load(ws, latest)
        if doc is None:
            missing.append(latest)
        else:
            sources["_test_run"] = doc
            sources["_test_run_path"] = latest
            read.append(latest)
    watermarks = {}
    marks = {
        "inventory/topology-observed.json": lambda doc: blank(doc.get("mapped_at")),
        "health/metadata-iosxe.json": lambda doc: blank(plane(doc, "iosxe").get("last_collected_at")),
        "health/metadata-splunk.json": lambda doc: blank(plane(doc, "splunk").get("last_collected_at")),
        "health/metadata-netflow.json": lambda doc: blank(plane(doc, "netflow").get("last_collected_at")),
        "health/metadata-application.json": lambda doc: blank(plane(doc, "application").get("last_collected_at")),
        "inventory/applications.json": lambda doc: blank(doc.get("updated_at")) or blank(doc.get("source_updated_at")),
        "health/metadata-servicenow.json": lambda doc: blank(plane(doc, "servicenow").get("last_collected_at")),
        "state/health.json": lambda doc: blank(doc.get("updated_at")),
        "state/network-ops.json": lambda doc: blank(doc.get("updated_at")),
        "inventory/prod.json": lambda doc: blank(doc.get("collected_at")) or blank(doc.get("snapshot_id")),
        "state/testing.json": lambda doc: blank(doc.get("updated_at")),
    }
    for rel, getter in marks.items():
        watermarks[rel] = getter(sources[rel]) if rel in sources else None
    if ops_run:
        watermarks[ops_run] = blank((sources.get("_ops_run") or {}).get("updated_at"))
    if latest:
        watermarks[latest] = blank((sources.get("_test_run") or {}).get("updated_at"))
    prior_marks = prior.get("watermarks") if isinstance(prior.get("watermarks"), dict) else {}
    if prior and prior_marks and all(prior_marks.get(key) == value for key, value in watermarks.items()) and set(prior_marks) == set(watermarks):
        print(visit_common.summary({
            "result": "ok",
            "wrote": None,
            "compiled_at": prior.get("compiled_at"),
            "edges": len(prior.get("edges") or []),
            "noop": True,
        }))
        return 0
    compiled_at = stamp_text(now_utc())
    produced = copy_edges(sources)
    edges, fresh, newly_stale = upsert(produced, prior.get("edges") or [], compiled_at)
    drift = drift_rows(edges, sources.get("inventory/applications.json"), prior.get("drift") or [], compiled_at)
    current = sum(1 for edge in edges if edge["status"] == "current")
    stale = sum(1 for edge in edges if edge["status"] == "stale")
    headline = "%s edges (%s current, %s stale) from %s sources; %s new, %s newly stale; drift %s." % (
        len(edges), current, stale, len(read), fresh, newly_stale, len(drift)
    )
    chart = {
        "schema": "relationships-state/v1",
        "updated_at": compiled_at,
        "source_agent": "relationship-agent",
        "status": "unknown" if not sources else "ok",
        "headline": headline,
        "next_action": "Review drift[]: %s rows" % len(drift) if drift else "none",
        "compiled_at": compiled_at,
        "coverage": {"read": read[:15], "missing": missing},
        "watermarks": watermarks,
        "edges": edges[:500],
        "drift": drift[:100],
        "keys": union_keys(edges),
    }
    try:
        visit_common.validate(chart, SCHEMA)
    except ValueError as exc:
        print("schema: %s" % exc, file=sys.stderr)
        return 1
    path = Path(ws) / "state" / "relationships.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chart, indent=2) + "\n", encoding="utf-8")
    print(visit_common.summary({
        "result": chart["status"],
        "wrote": "state/relationships.json",
        "edges": len(edges),
        "current": current,
        "stale": stale,
        "new": fresh,
        "newly_stale": newly_stale,
        "drift": len(drift),
        "read": len(read),
        "absent": missing,
    }))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="Relationship compile")
    sub = parser.add_subparsers(dest="cmd", required=True)
    compile_cmd = sub.add_parser("compile")
    compile_cmd.add_argument("--workspace", required=True)
    compile_cmd.set_defaults(func=cmd_compile)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
