#!/usr/bin/env python3
"""Build state/health.json from the nurse boards already on disk.

assess runs under execution_type standard. It does not call MCP. It
folds freshness, series references, consult ids, the problem list,
and the impact walk, then writes the chart. Opinion fields are
placeholders.

annotate replaces the verdict: headline, opinion, impressions,
hypotheses, the trend narrative, and asserted relations. It does
not recompute impact, freshness, or problem status.

  python3 <skill>/scripts/assess_health.py assess --workspace <file_explorer>
  python3 <skill>/scripts/assess_health.py annotate --workspace <file_explorer> \\
      --headline "..." --opinion "..." --narrative "..." \\
      --impression application="..." --hypothesis P-20261009-01="..."
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

SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "health-state.schema.json"
PLANES = ("application", "netflow", "splunk", "iosxe", "servicenow")
VITALS = ("application", "netflow", "splunk", "iosxe")
KEY_RE = re.compile(r"^(device|interface|site|service|test|control|incident|change|application):[^ ].*$")
TTL = timedelta(hours=26)
TASKS = {
    "application": ("Health Application", "Run the application health check only."),
    "netflow": ("Health Monitor", "Run the NetFlow health check only."),
    "splunk": ("Health Monitor", "Run the Splunk health check only."),
    "iosxe": ("Health Device", "Run the network device health check only."),
    "servicenow": ("Health ServiceNow", "Run the ServiceNow health check only."),
}


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


def plane_block(board, name):
    if not isinstance(board, dict):
        return {}
    nested = board.get(name)
    if isinstance(nested, dict) and any(key in nested for key in ("current", "last_collected_at", "series", "visits")):
        return nested
    if any(key in board for key in ("current", "last_collected_at")):
        return board
    return nested if isinstance(nested, dict) else {}


KEY_RANK = ("incident:", "change:", "service:", "application:", "device:", "interface:", "test:", "site:", "control:")


def rank_key(key):
    for index, prefix in enumerate(KEY_RANK):
        if key.startswith(prefix):
            return index
    return len(KEY_RANK)


def good_keys(values):
    found = []
    for key in values or []:
        if isinstance(key, str) and KEY_RE.match(key) and key not in found:
            found.append(key)
    found.sort(key=rank_key)
    return found[:8]


def prefix_name(key, prefix):
    if isinstance(key, str) and key.startswith(prefix):
        return key.split(":", 1)[1]
    return None


def rows_of(block):
    return [row for row in (block.get("current") or []) if isinstance(row, dict)]


def latest_visit(block):
    visits = [row for row in (block.get("visits") or []) if isinstance(row, dict)]
    return visits[-1] if visits else {}


def freshness_row(block, moment, iosxe=False):
    observed = parse_time(block.get("last_collected_at")) if block else None
    if observed is None:
        return {"state": "missing", "observed_at": None, "ttl_hours": 26, "stale_devices": [] if iosxe else None}
    state = "stale" if moment >= observed + TTL else "current"
    stale_devices = None
    if iosxe:
        stale_devices = []
        if state == "current":
            visits = [row for row in (block.get("visits") or []) if isinstance(row, dict)]
            covered_all = False
            named = set()
            for visit in visits:
                seen = parse_time(visit.get("checked_at"))
                if seen is None or moment >= seen + TTL:
                    continue
                scope = visit.get("scope")
                if scope in (None, "all", ["all"]):
                    covered_all = True
                elif isinstance(scope, list):
                    named.update(item for item in scope if isinstance(item, str) and item.startswith("device:"))
                elif isinstance(scope, str) and scope.startswith("device:"):
                    named.add(scope)
            if not covered_all:
                for row in rows_of(block):
                    if row.get("kind") != "device":
                        continue
                    for key in good_keys(row.get("keys")):
                        if key.startswith("device:") and key not in named and key not in stale_devices:
                            stale_devices.append(key)
    return {"state": state, "observed_at": stamp_text(observed), "ttl_hours": 26, "stale_devices": stale_devices}


def series_ref(name, block):
    if not block:
        return {"series_ref": None, "rows": 0, "from": None, "to": None}
    series = [row for row in (block.get("series") or []) if isinstance(row, dict)]
    moments = [row.get("at") for row in series if blank(row.get("at"))]
    return {
        "series_ref": "health/metadata-%s.json" % name,
        "rows": len(series),
        "from": moments[0] if moments else None,
        "to": moments[-1] if moments else None,
    }


def coverage_of(block):
    if not block:
        return "not_requested"
    visit = latest_visit(block)
    state = visit.get("coverage")
    if state in ("complete", "partial", "unavailable", "not_requested"):
        return state
    if block.get("last_collected_at"):
        return "complete"
    return "unavailable"


def consult_status(name, visit):
    status = visit.get("status")
    if name == "servicenow":
        return status if status in ("ok", "unknown") else "unknown"
    return status if status in ("ok", "degraded", "unknown") else "unknown"


def symptom_label(plane, row):
    kind = row.get("kind") or row.get("type") or "row"
    state = row.get("state")
    name = row.get("scope") or row.get("name") or row.get("number") or kind
    return "%s %s %s %s" % (plane, kind, name, state)


def application_symptoms(rows):
    found = []
    targets = []
    other = False
    for row in rows:
        kind = row.get("kind")
        state = row.get("state")
        keys = good_keys(row.get("keys"))
        item = {"plane": "application", "keys": keys, "at": row.get("at"), "ref": row.get("scope") or kind, "label": symptom_label("application", row)}
        if kind == "probe" and state == "down":
            found.append(item)
            other = True
        elif kind == "container" and state == "gone":
            found.append(item)
            other = True
        elif kind == "host" and (state == "unreachable" or row.get("interfaces_down")):
            found.append(item)
            other = True
        elif kind == "target" and row.get("health") not in (None, "up", "unknown"):
            targets.append(item)
    if not other:
        found.extend(targets)
    return found


def netflow_symptoms(rows):
    found = []
    for row in rows:
        if row.get("kind") == "exporter" and row.get("state") == "silent":
            found.append({
                "plane": "netflow",
                "keys": good_keys(row.get("keys")),
                "at": row.get("at"),
                "ref": row.get("scope") or "exporter",
                "label": symptom_label("netflow", row),
            })
    return found


def splunk_symptoms(rows):
    found = []
    for row in rows:
        kind = row.get("kind")
        count = row.get("count") if isinstance(row.get("count"), int) else 0
        if kind in ("bgp", "link") and count >= 2:
            hit = True
        elif kind in ("reload", "acl", "auth_failed"):
            hit = True
        else:
            hit = False
        if not hit:
            continue
        found.append({
            "plane": "splunk",
            "keys": good_keys(row.get("keys")),
            "at": row.get("at"),
            "ref": row.get("subject") or kind,
            "label": symptom_label("splunk", row),
        })
    return found


def iosxe_symptoms(rows):
    found = []
    for row in rows:
        kind = row.get("kind")
        state = row.get("state")
        intent = row.get("intent")
        if kind == "interface" and intent == "failed":
            hit = True
        elif kind == "bgp" and state and state != "fsm-established":
            hit = True
        elif kind == "device" and state and state != "up":
            hit = True
        else:
            hit = False
        if not hit:
            continue
        found.append({
            "plane": "iosxe",
            "keys": good_keys(row.get("keys")),
            "at": row.get("last_changed") or row.get("at"),
            "ref": row.get("name") or kind,
            "label": symptom_label("iosxe", row),
        })
    return found


def ticket_rows(rows):
    found = []
    for row in rows:
        if row.get("type") not in ("incident", "change") or not row.get("active"):
            continue
        keys = good_keys(row.get("keys"))
        if blank(row.get("service")):
            keys.append("service:%s" % row["service"])
        if blank(row.get("device")):
            keys.append("device:%s" % row["device"])
        if blank(row.get("device")) and blank(row.get("interface")):
            keys.append("interface:%s/%s" % (row["device"], row["interface"]))
        keys = good_keys(keys)
        if not keys:
            continue
        found.append({
            "plane": "servicenow",
            "keys": keys,
            "at": row.get("opened_at"),
            "ref": row.get("scope") or row.get("number"),
            "label": "%s %s %s" % (row.get("number"), row.get("state"), (row.get("issue") or "")[:60]),
            "number": row.get("number"),
        })
    return found


def share(left, right):
    return bool(set(left) & set(right))


def cluster_symptoms(symptoms):
    groups = []
    for symptom in symptoms:
        placed = None
        for group in groups:
            if any(share(symptom["keys"], item["keys"]) for item in group):
                placed = group
                break
        if placed is None:
            groups.append([symptom])
        else:
            placed.append(symptom)
    merged = True
    while merged:
        merged = False
        for index, group in enumerate(groups):
            keys = set()
            for item in group:
                keys.update(item["keys"])
            for other in groups[index + 1:]:
                if any(share(keys, item["keys"]) for item in other):
                    group.extend(other)
                    groups.remove(other)
                    merged = True
                    break
            if merged:
                break
    return groups


def next_id(opened_at, used):
    moment = parse_time(opened_at) or now_utc()
    day = moment.strftime("%Y%m%d")
    number = 1
    while True:
        ident = "P-%s-%02d" % (day, number)
        if ident not in used:
            used.add(ident)
            return ident
        number += 1
        if number > 99:
            return "P-%s-99" % day


def walk_impact(keys, edges):
    start_devices = []
    start_apps = []
    for key in keys:
        if key.startswith("interface:"):
            device = key.split(":", 1)[1].split("/", 1)[0]
            if device and "device:" + device not in start_devices:
                start_devices.append("device:" + device)
        elif key.startswith("device:") and key not in start_devices:
            start_devices.append(key)
        elif key.startswith("application:") and key not in start_apps:
            start_apps.append(key)
    current = [edge for edge in edges if isinstance(edge, dict) and edge.get("status") == "current"]
    hosts = list(start_devices)
    bases = []
    for edge in current:
        if edge.get("rel") == "flows_to" and edge.get("to") in start_devices and edge.get("from") not in hosts:
            hosts.append(edge["from"])
            bases.append(edge.get("basis"))
        if edge.get("rel") == "traverses" and edge.get("to") in start_devices and str(edge.get("from") or "").startswith("device:"):
            if edge["from"] not in hosts:
                hosts.append(edge["from"])
                bases.append(edge.get("basis"))
    apps = list(start_apps)
    grew = True
    while grew:
        grew = False
        for edge in current:
            if edge.get("rel") != "depends_on":
                continue
            source = edge.get("from")
            target = edge.get("to")
            if not str(source).startswith("application:"):
                continue
            if target in hosts or target in apps:
                if source not in apps:
                    apps.append(source)
                    bases.append(edge.get("basis"))
                    grew = True
    services = []
    for edge in current:
        if edge.get("rel") == "depends_on" and str(edge.get("from") or "").startswith("service:") and edge.get("to") in apps:
            name = prefix_name(edge["from"], "service:")
            if name and name not in services:
                services.append(name)
                bases.append(edge.get("basis"))
    added = len(hosts) > len(start_devices) or len(apps) > len(start_apps) or services
    if not edges or not added:
        return {
            "applications": [prefix_name(key, "application:") for key in start_apps],
            "services": [],
            "hosts": [prefix_name(key, "device:") for key in start_devices],
            "basis": "none",
        }
    used = {item for item in bases if item in ("intended", "observed")}
    if used == {"intended"}:
        basis = "intended"
    elif used == {"observed"}:
        basis = "observed"
    elif used:
        basis = "both"
    else:
        basis = "none"
    return {
        "applications": [prefix_name(key, "application:") for key in apps if prefix_name(key, "application:")][:24],
        "services": services[:12],
        "hosts": [prefix_name(key, "device:") for key in hosts if prefix_name(key, "device:")][:24],
        "basis": basis,
    }


def hypothesis_for(group, keys):
    labels = [item["label"] for item in group[:3]]
    return "Symptom on %s. " % ", ".join(keys[:4]) + " ".join(labels)[:240]


def symptom_still(problem_keys, symptoms):
    return [item for item in symptoms if share(problem_keys, item["keys"])]


def ticket_still(problem_keys, tickets):
    return [item for item in tickets if share(problem_keys, item["keys"])]


def build_problems(prior, symptoms, tickets, edges, moment, read):
    used = {problem.get("id") for problem in prior if problem.get("id")}
    kept = []
    covered = []
    for problem in prior:
        if problem.get("status") == "resolved":
            continue
        keys = good_keys(problem.get("keys"))
        live = symptom_still(keys, symptoms)
        joined = ticket_still(keys, tickets)
        if live:
            status = "active"
            opened = problem.get("opened_at") or stamp_text(moment)
            closed = None
        elif problem.get("status") == "watching" and not joined and not live:
            status = "resolved"
            opened = problem.get("opened_at") or stamp_text(moment)
            closed = stamp_text(moment)
        elif not live:
            status = "watching" if joined or problem.get("status") == "watching" else "watching"
            opened = problem.get("opened_at") or stamp_text(moment)
            closed = None
            if not joined and problem.get("status") == "active":
                status = "watching"
        else:
            status = problem.get("status") or "watching"
            opened = problem.get("opened_at") or stamp_text(moment)
            closed = None
        if status == "resolved" and problem.get("status") == "watching":
            closed = stamp_text(moment)
        merged = list(keys)
        for item in live + joined:
            for key in item["keys"]:
                if key not in merged:
                    merged.append(key)
        merged = good_keys(merged)
        covered.extend(live)
        refs = list(problem.get("symptom_refs") or [])
        for item in live[:4]:
            ref = "health/metadata-%s.json#%s" % (item["plane"], item["ref"])
            if ref not in refs:
                refs.append(ref)
        if not refs:
            refs = ["health/metadata-%s.json" % (live[0]["plane"] if live else "servicenow")]
        kept.append({
            "id": problem.get("id") or next_id(opened, used),
            "status": status,
            "opened_at": opened,
            "closed_at": closed if status == "resolved" else None,
            "keys": merged,
            "symptom_refs": refs[:6],
            "evidence_refs": list(problem.get("evidence_refs") or [])[:6],
            "hypothesis": problem.get("hypothesis") or hypothesis_for(live or joined, merged),
            "impact": walk_impact(merged, edges),
            "order": None,
            "treatment_ref": None,
            "outcome": {"state": "too_early", "checked_at": stamp_text(moment)},
            "_live": live,
            "_evidence_moved": bool(live) and problem.get("status") != "active",
        })
    grouped = cluster_symptoms([item for item in symptoms if item not in covered])
    for group in grouped:
        keys = []
        for item in group:
            for key in item["keys"]:
                if key not in keys:
                    keys.append(key)
        joined = ticket_still(keys, tickets)
        for item in joined:
            for key in item["keys"]:
                if key not in keys:
                    keys.append(key)
        keys = good_keys(keys)
        if not keys:
            continue
        opened = next((item.get("at") for item in group if item.get("at")), stamp_text(moment))
        ident = next_id(opened, used)
        refs = ["health/metadata-%s.json#%s" % (item["plane"], item["ref"]) for item in group[:6]]
        kept.append({
            "id": ident,
            "status": "active",
            "opened_at": opened if isinstance(opened, str) else stamp_text(moment),
            "closed_at": None,
            "keys": keys,
            "symptom_refs": refs or ["health/metadata-%s.json" % group[0]["plane"]],
            "evidence_refs": [],
            "hypothesis": hypothesis_for(group, keys),
            "impact": walk_impact(keys, edges),
            "order": None,
            "treatment_ref": None,
            "outcome": {"state": "too_early", "checked_at": stamp_text(moment)},
            "_live": group,
            "_evidence_moved": True,
            "_new": True,
        })
    claimed = {key for problem in kept for key in problem["keys"]}
    for ticket in tickets:
        if share(ticket["keys"], claimed):
            continue
        opened = ticket.get("at") or stamp_text(moment)
        ident = next_id(opened, used)
        keys = ticket["keys"][:8]
        kept.append({
            "id": ident,
            "status": "watching",
            "opened_at": opened if isinstance(opened, str) else stamp_text(moment),
            "closed_at": None,
            "keys": keys,
            "symptom_refs": ["health/metadata-servicenow.json#%s" % ticket["ref"]],
            "evidence_refs": [],
            "hypothesis": "Ticket only. No vital board shows this symptom.",
            "impact": walk_impact(keys, edges),
            "order": None,
            "treatment_ref": None,
            "outcome": {"state": "too_early", "checked_at": stamp_text(moment)},
            "_live": [],
            "_evidence_moved": True,
            "_new": True,
        })
        claimed.update(keys)
    rank = {"active": 0, "watching": 1, "resolved": 2}
    kept.sort(key=lambda problem: (rank.get(problem["status"], 9), problem.get("opened_at") or ""))
    return kept[:12]


def orders_for(problems, freshness, iosxe_block, prior_ids):
    orders = []
    for plane, (agent, task) in TASKS.items():
        if freshness[plane]["state"] in ("stale", "missing") and len(orders) < 6:
            orders.append({"agent": agent, "task": task, "problem_ref": None, "dispatched": False})
    iosxe_at = parse_time((iosxe_block or {}).get("last_collected_at"))
    for problem in problems:
        if problem["status"] != "active" or len(orders) >= 5:
            continue
        devices = [key for key in problem["keys"] if key.startswith("device:")]
        symptom_at = parse_time(problem.get("opened_at"))
        if devices and iosxe_at and symptom_at and iosxe_at < symptom_at:
            orders.append({
                "agent": "Health Device",
                "task": "Run the network device health check only. Scope: %s" % " ".join(devices[:6]),
                "problem_ref": problem["id"],
                "dispatched": False,
            })
            break
    current_ids = {problem["id"] for problem in problems}
    if current_ids != prior_ids and len(orders) < 6:
        orders.append({
            "agent": "Relationship agent",
            "task": "Run the relationship compile only.",
            "problem_ref": None,
            "dispatched": False,
        })
    return orders[:6]


def envelope_status(freshness, consults, coverage):
    vital_fresh = [freshness[plane]["state"] for plane in VITALS]
    if all(state == "missing" for state in vital_fresh):
        return "unknown"
    if any(state in ("stale", "missing") for state in vital_fresh):
        return "stale_chart"
    if any((consults[plane] or {}).get("status") == "degraded" for plane in VITALS):
        return "degraded"
    if any(freshness[plane]["state"] == "missing" or coverage[plane] == "unavailable" for plane in VITALS):
        return "partial"
    return "ok"


def ticket_history(rows, problems):
    open_rows = [row for row in rows if row.get("active")]
    related = []
    problem_keys = {key for problem in problems if problem["status"] in ("active", "watching") for key in problem["keys"]}
    for row in rows:
        for key in good_keys(row.get("keys")):
            if key.startswith(("incident:", "change:")) and (not problem_keys or share(good_keys(row.get("keys")), problem_keys)):
                if key not in related:
                    related.append(key)
    resolution = None
    for row in rows:
        if row.get("active"):
            continue
        if problem_keys and not share(good_keys(row.get("keys")), problem_keys):
            continue
        note = blank(row.get("close_notes"))
        code = blank(row.get("close_code"))
        if code or note:
            resolution = " ".join(part for part in (code, note) if part)[:240]
            break
    return {
        "pattern": "%s board rows, %s open." % (len(rows), len(open_rows)),
        "summary": ", ".join("%s %s" % (row.get("number"), row.get("state")) for row in rows[:6]) or "No in-scope rows.",
        "related_records": related[:10],
        "prior_resolution": resolution,
    }


def public_problem(problem):
    item = dict(problem)
    item.pop("_live", None)
    item.pop("_evidence_moved", None)
    item.pop("_new", None)
    return item


def union_keys(problems, relations):
    found = []
    for problem in problems:
        for key in problem.get("keys") or []:
            if key not in found and KEY_RE.match(key):
                found.append(key)
    for relation in relations:
        for key in (relation.get("from"), relation.get("to")):
            if key and key not in found and KEY_RE.match(key):
                found.append(key)
    return found


def resolve_workspace(given):
    raw = Path(strip_arg(given))
    candidates = [raw]
    if not raw.is_absolute():
        candidates.append(Path.cwd() / raw)
    seen = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_dir():
            continue
        seen.append(resolved)
        print("health workspace=%s" % resolved, file=sys.stderr)
        return resolved
    print('{"error": "workspace directory missing"}', file=sys.stderr)
    return None


def cmd_assess(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    moment = now_utc()
    at = stamp_text(moment)
    mode = args.mode if args.mode in ("assess-now", "refresh-then-assess") else "assess-now"
    read = []
    boards = {}
    blocks = {}
    for plane in PLANES:
        rel = "health/metadata-%s.json" % plane
        boards[plane] = load(ws, rel)
        if boards[plane] is not None:
            read.append(rel)
        blocks[plane] = plane_block(boards[plane], plane) if boards[plane] else {}
    prior = load(ws, "state/health.json") or {}
    if prior:
        read.append("state/health.json")
    relationships = load(ws, "state/relationships.json") or {}
    if relationships:
        read.append("state/relationships.json")
    edges = relationships.get("edges") if isinstance(relationships.get("edges"), list) else []
    prior_consults = prior.get("consults") if isinstance(prior.get("consults"), dict) else {}
    for plane in PLANES:
        watch = blank(blocks[plane].get("last_visit_id"))
        prior_watch = blank((prior_consults.get(plane) or {}).get("watch_id")) if isinstance(prior_consults.get(plane), dict) else None
        if watch and watch != prior_watch and len(read) < 12:
            stamp = load(ws, "health/%s/%s.json" % (plane, watch))
            if stamp is not None:
                read.append("health/%s/%s.json" % (plane, watch))
    freshness = {plane: freshness_row(blocks[plane] if boards[plane] else {}, moment, plane == "iosxe") for plane in PLANES}
    coverage = {plane: coverage_of(blocks[plane] if boards[plane] else {}) for plane in PLANES}
    symptoms = []
    symptoms.extend(application_symptoms(rows_of(blocks["application"])))
    symptoms.extend(netflow_symptoms(rows_of(blocks["netflow"])))
    symptoms.extend(splunk_symptoms(rows_of(blocks["splunk"])))
    symptoms.extend(iosxe_symptoms(rows_of(blocks["iosxe"])))
    tickets = ticket_rows(rows_of(blocks["servicenow"]))
    prior_problems = [row for row in (prior.get("problems") or []) if isinstance(row, dict)]
    problems = build_problems(prior_problems, symptoms, tickets, edges, moment, read)
    prior_ids = {row.get("id") for row in prior_problems}
    orders = orders_for(problems, freshness, blocks["iosxe"], prior_ids)
    consults = {}
    for plane in PLANES:
        block = blocks[plane]
        visit = latest_visit(block)
        if not block or not blank(block.get("last_collected_at")):
            consults[plane] = None
            continue
        watch = blank(block.get("last_visit_id"))
        consult = {
            "watch_id": watch,
            "observed_at": block.get("last_collected_at"),
            "status": consult_status(plane, visit),
            "trend": visit.get("delta") if visit.get("delta") in ("first", "unchanged", "worse", "better", "changed") else "unchanged",
            "trend_note": "%s series rows; latest delta %s." % (len(block.get("series") or []), visit.get("delta") or "none"),
            "impression": "Placeholder. %s is %s." % (plane, consult_status(plane, visit)),
            "evidence_for": [item["label"][:180] for item in symptoms if item["plane"] == plane][:5],
            "evidence_against": [],
            "source_ref": "health/%s/%s.json" % (plane, watch) if watch else None,
            "inspect_when": "Open the stamp when the row notes are needed.",
        }
        if plane == "servicenow":
            state = coverage["servicenow"]
            consult["collection_status"] = state if state in ("complete", "partial", "unavailable") else "complete"
            consult["ticket_history"] = ticket_history(rows_of(block), problems)
        consults[plane] = consult
    status = envelope_status(freshness, consults, coverage)
    unhealthy = [problem["hypothesis"][:240] for problem in problems if problem["status"] == "active"][:8]
    if not unhealthy:
        unhealthy = ["No vital symptom is on the current boards."]
    opinion = unhealthy[0]
    plan = orders[0]["task"] if orders else "none"
    chart = {
        "keys": union_keys(problems, []),
        "schema": "health-state/v7",
        "updated_at": at,
        "source_agent": "health-analyzer",
        "status": status,
        "headline": opinion[:300],
        "next_action": plan,
        "mode": mode,
        "analyzed_at": at,
        "coverage": coverage,
        "freshness": freshness,
        "consults": consults,
        "series": {plane: series_ref(plane, blocks[plane] if boards[plane] else {}) for plane in PLANES},
        "assessment": {
            "unhealthy": unhealthy,
            "healthy": ["%s %s" % (plane, (consults[plane] or {}).get("status")) for plane in VITALS if (consults[plane] or {}).get("status") == "ok"][:8] or ["No vital plane is currently ok."],
            "contradictions": [],
            "opinion": opinion,
        },
        "trend_analysis": {"narrative": "Placeholder. Latest deltas are on the consults.", "flips": []},
        "soap": {
            "subjective": "Scheduled %s." % mode,
            "objective": "Boards read: %s." % ", ".join("%s %s" % (plane, freshness[plane]["state"]) for plane in PLANES),
            "assessment": opinion,
            "plan": plan,
        },
        "problems": [public_problem(problem) for problem in problems],
        "orders": orders,
        "relations": [],
        "dispatched": [],
        "read": read[:12],
    }
    try:
        visit_common.validate(chart, SCHEMA)
    except ValueError as exc:
        print("schema: %s" % exc, file=sys.stderr)
        return 1
    path = Path(ws) / "state" / "health.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chart, indent=2) + "\n", encoding="utf-8")
    needs = []
    for problem in problems:
        if problem["status"] == "resolved":
            continue
        needs.append({
            "id": problem["id"],
            "status": problem["status"],
            "keys": problem["keys"][:6],
            "new": bool(problem.get("_new")),
        })
    print(visit_common.summary({
        "plane": "health",
        "status": status,
        "mode": mode,
        "wrote": "state/health.json",
        "problems": len(problems),
        "active": sum(1 for problem in problems if problem["status"] == "active"),
        "orders": [{"agent": order["agent"], "task": order["task"][:160], "problem_ref": order["problem_ref"]} for order in orders],
        "needs_opinion": needs[:8],
        "read": read,
    }))
    return 0


def cmd_annotate(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    path = Path(ws) / "state" / "health.json"
    if not path.is_file():
        print("state/health.json missing", file=sys.stderr)
        return 1
    chart = json.loads(path.read_text(encoding="utf-8"))
    if args.headline:
        chart["headline"] = strip_arg(args.headline)
    if args.opinion:
        chart["assessment"]["opinion"] = strip_arg(args.opinion)
        chart["soap"]["assessment"] = chart["assessment"]["opinion"]
        if not args.headline:
            chart["headline"] = chart["assessment"]["opinion"][:300]
    if args.narrative:
        chart["trend_analysis"]["narrative"] = strip_arg(args.narrative)
    if args.subjective:
        chart["soap"]["subjective"] = strip_arg(args.subjective)
    if args.objective:
        chart["soap"]["objective"] = strip_arg(args.objective)
    for item in args.impression or []:
        text = strip_arg(item)
        if "=" not in text:
            continue
        plane, sentence = text.split("=", 1)
        plane = strip_arg(plane)
        consult = (chart.get("consults") or {}).get(plane)
        if isinstance(consult, dict) and strip_arg(sentence):
            consult["impression"] = strip_arg(sentence)
    for item in args.trend or []:
        text = strip_arg(item)
        if "=" not in text:
            continue
        plane, sentence = text.split("=", 1)
        consult = (chart.get("consults") or {}).get(strip_arg(plane))
        if isinstance(consult, dict) and strip_arg(sentence):
            consult["trend_note"] = strip_arg(sentence)
    for item in args.hypothesis or []:
        text = strip_arg(item)
        if "=" not in text:
            continue
        ident, sentence = text.split("=", 1)
        ident = strip_arg(ident)
        sentence = strip_arg(sentence)
        if not sentence:
            continue
        for problem in chart.get("problems") or []:
            if problem.get("id") != ident:
                continue
            problem["hypothesis"] = sentence
            if isinstance(problem.get("order"), dict) and str(problem["order"].get("task") or "").startswith("Network Ops:"):
                problem["order"]["task"] = "Network Ops: %s" % sentence[:300]
            for order in chart.get("orders") or []:
                if order.get("problem_ref") == ident and str(order.get("task") or "").startswith("Network Ops:"):
                    order["task"] = "Network Ops: %s" % sentence[:300]
    for item in args.relation or []:
        parts = strip_arg(item).split(">")
        if len(parts) != 4:
            print("relation must be from>to>rel>evidence", file=sys.stderr)
            continue
        source, target, rel, evidence = [strip_arg(part) for part in parts]
        if rel not in ("depends_on", "caused", "impacted", "resolved_by", "changed"):
            print("relation rejected %s" % rel, file=sys.stderr)
            continue
        if not KEY_RE.match(source) or not KEY_RE.match(target) or not evidence:
            print("relation keys rejected", file=sys.stderr)
            continue
        chart.setdefault("relations", []).append({
            "from": source,
            "to": target,
            "rel": rel,
            "basis": "asserted",
            "evidence_ref": evidence,
        })
    chart["relations"] = (chart.get("relations") or [])[:12]
    if args.plan:
        chart["soap"]["plan"] = strip_arg(args.plan)
        chart["next_action"] = chart["soap"]["plan"]
    elif chart.get("orders"):
        chart["soap"]["plan"] = chart["orders"][0]["task"]
        chart["next_action"] = chart["soap"]["plan"]
    for item in args.order or []:
        text = strip_arg(item)
        parts = text.split("|")
        if len(parts) < 2:
            print("order must be agent|task|problem_ref", file=sys.stderr)
            continue
        agent = strip_arg(parts[0])
        task = strip_arg(parts[1])
        problem_ref = strip_arg(parts[2]) if len(parts) > 2 else ""
        if agent not in ("Health Device", "Health Monitor", "Health Application", "Health ServiceNow", "Network Ops", "Relationship agent"):
            print("order agent rejected %s" % agent, file=sys.stderr)
            continue
        if not task:
            continue
        chart.setdefault("orders", []).append({
            "agent": agent,
            "task": task[:400],
            "problem_ref": problem_ref or None,
            "dispatched": False,
        })
        if problem_ref:
            for problem in chart.get("problems") or []:
                if problem.get("id") == problem_ref:
                    problem["order"] = {"agent": agent, "task": task[:400]}
    chart["orders"] = (chart.get("orders") or [])[:6]
    if chart.get("orders") and not args.plan:
        chart["soap"]["plan"] = chart["orders"][0]["task"]
        chart["next_action"] = chart["soap"]["plan"]
    for item in args.sent or []:
        text = strip_arg(item)
        if "|" not in text:
            continue
        agent, task = text.split("|", 1)
        agent = strip_arg(agent)
        task = strip_arg(task)
        for order in chart.get("orders") or []:
            if order.get("agent") == agent and order.get("task") == task:
                order["dispatched"] = True
        plane = "relationships" if agent == "Relationship agent" else "iosxe"
        for name, pair in TASKS.items():
            if pair[0] == agent:
                plane = "topology" if "topology" in task else name
        chart.setdefault("dispatched", []).append({
            "plane": plane if plane in ("application", "netflow", "splunk", "iosxe", "servicenow", "topology", "relationships") else "iosxe",
            "agent": agent,
            "task": task,
            "invoked_at": stamp_text(now_utc()),
        })
    chart["dispatched"] = (chart.get("dispatched") or [])[:8]
    chart["keys"] = union_keys(chart.get("problems") or [], chart.get("relations") or [])
    chart["updated_at"] = stamp_text(now_utc())
    try:
        visit_common.validate(chart, SCHEMA)
    except ValueError as exc:
        print("schema: %s" % exc, file=sys.stderr)
        return 1
    path.write_text(json.dumps(chart, indent=2) + "\n", encoding="utf-8")
    print(visit_common.summary({"plane": "health", "wrote": "state/health.json", "annotated": True}))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="Health Analyzer chart")
    sub = parser.add_subparsers(dest="cmd", required=True)
    assess = sub.add_parser("assess")
    assess.add_argument("--workspace", required=True)
    assess.add_argument("--mode", default="assess-now")
    assess.set_defaults(func=cmd_assess)
    note = sub.add_parser("annotate")
    note.add_argument("--workspace", required=True)
    note.add_argument("--headline", default="")
    note.add_argument("--opinion", default="")
    note.add_argument("--narrative", default="")
    note.add_argument("--subjective", default="")
    note.add_argument("--objective", default="")
    note.add_argument("--plan", default="")
    note.add_argument("--impression", action="append", default=[])
    note.add_argument("--trend", action="append", default=[])
    note.add_argument("--hypothesis", action="append", default=[])
    note.add_argument("--relation", action="append", default=[])
    note.add_argument("--order", action="append", default=[])
    note.add_argument("--sent", action="append", default=[])
    note.set_defaults(func=cmd_annotate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
