#!/usr/bin/env python3
"""Published catalog check plus unresolved NIST titles.

scan runs under execution_type mcp_orchestration. It lists catalog and
tests/compliance on main, gets the job catalog and the test bridge, and
filters the pinned NIST index. Coverage counts only a check that the
bridge maps to a NET-COMP rule. The agent reads the last stdout line
and decides relevance and live versus static. This script does not
write the workspace and does not rank candidates.
"""
import argparse
import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace-handoff" / "scripts"))

try:
    import query_sources  # noqa: E402
except ImportError:
    print('{"error": "query_sources missing"}', file=sys.stderr)
    sys.exit(1)

try:
    import visit_common  # noqa: E402
except ImportError:
    print(
        '{"error": "visit_common missing; attach the workspace-handoff skill"}',
        file=sys.stderr,
    )
    sys.exit(1)

REF = "main"
CATALOG_DIR = "catalog"
COMPLIANCE_DIR = "tests/compliance"
CATALOG_NAME = "job-catalog.json"
BRIDGE_NAME = "test-bridge.yml"
CROSSWALK_NAME = "banking-framework-crosswalk.v1.json"
ACTIVE = {"proposed", "accepted"}
RULE_RE = re.compile(r"^(NET-COMP-\d+)$")


def emit(payload):
    print(json.dumps(payload, separators=(",", ":"), default=str))


def call(tool, args):
    body, err = visit_common.unwrap_github(visit_common.mcp_call(tool, args, retries=1))
    return body, err


def entry_path(entries, name, kind):
    for item in entries:
        if not isinstance(item, dict):
            continue
        if item.get("name") == name and item.get("type") == kind:
            path = item.get("path")
            if isinstance(path, str) and path:
                return path
    return None


def names_of(entries, kind):
    found = []
    for item in entries:
        if isinstance(item, dict) and item.get("type") == kind and isinstance(item.get("name"), str):
            found.append(item["name"])
    return found


def file_text(body):
    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, str) or content == "":
        return None
    encoding = body.get("encoding") if isinstance(body, dict) else None
    if encoding == "base64":
        try:
            return base64.b64decode(content).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    return content


def parse_bridge(text):
    """Read NET-COMP rules from test-bridge.yml.

    Rules sit under matrix_rules. static_rules and live_checks are the
    only lists that count. Indentation follows the file; comments do not.
    """
    rules = {}
    current = None
    section = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        text_line = line.strip()
        if text_line.endswith(":") and RULE_RE.match(text_line[:-1].strip()):
            current = text_line[:-1].strip()
            rules[current] = {"static": [], "live": []}
            section = None
            continue
        if text_line in {"static_rules:", "live_checks:"} and current:
            section = "static" if text_line.startswith("static") else "live"
            continue
        if text_line.startswith("- ") and current and section:
            rules[current][section].append(text_line[2:].strip().strip("'\""))
            continue
        if text_line.endswith(":") and not text_line.startswith("-"):
            section = None
    return rules


def compliance_checks(catalog):
    suites = catalog.get("suites") if isinstance(catalog, dict) else None
    compliance = suites.get("compliance") if isinstance(suites, dict) else None
    checks = compliance.get("checks") if isinstance(compliance, dict) else None
    if not isinstance(checks, list):
        return []
    return [item for item in checks if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]]


def bridged_ids(rules):
    static_ids = set()
    live_ids = set()
    for rule in rules.values():
        static_ids.update(rule["static"])
        live_ids.update(rule["live"])
    return static_ids, live_ids


def estate_of(inventory):
    devices = []
    rows = inventory.get("devices") if isinstance(inventory, dict) else None
    if not isinstance(rows, list):
        return {"known": False, "source": "inventory/prod.json", "devices": []}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        tags = row.get("tags") if isinstance(row.get("tags"), list) else []
        devices.append(
            {
                "name": name.strip(),
                "platform": row.get("platform") if isinstance(row.get("platform"), str) else "",
                "role": row.get("role") if isinstance(row.get("role"), str) else "",
                "tags": [tag for tag in tags if isinstance(tag, str)][:12],
            }
        )
        if len(devices) >= 48:
            break
    return {"known": bool(devices), "source": "inventory/prod.json", "devices": devices}


def nist_ids_of(candidate):
    ids = []
    source = query_sources.nist_id_from_value(candidate.get("source_control"))
    if source:
        ids.append(source)
    for item in candidate.get("nist_sp_800_53") or []:
        mapped = query_sources.nist_id_from_value(item)
        if mapped and mapped not in ids:
            ids.append(mapped)
    return ids


def prior_of(intel):
    rows = []
    for candidate in (intel or {}).get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        rows.append(
            {
                "id": candidate.get("id"),
                "title": candidate.get("title"),
                "status": candidate.get("status") or "proposed",
                "source_control": candidate.get("source_control"),
                "nist_sp_800_53": candidate.get("nist_sp_800_53") or [],
                "evidence": candidate.get("evidence"),
            }
        )
        if len(rows) >= 10:
            break
    return rows


def now_covered(candidates, covered):
    dropped = []
    for candidate in candidates:
        status = str(candidate.get("status") or "proposed").strip().lower()
        if status not in ACTIVE:
            continue
        ids = nist_ids_of(candidate)
        if ids and all(item in covered for item in ids):
            cid = candidate.get("id")
            if isinstance(cid, str) and cid:
                dropped.append(cid)
    return dropped


def active_remaining(candidates, dropped):
    count = 0
    gone = set(dropped)
    for candidate in candidates:
        status = str(candidate.get("status") or "proposed").strip().lower()
        if status in ACTIVE and candidate.get("id") not in gone:
            count += 1
    return count


def published_index(published, rules):
    by_check = {}
    for rule_id, rule in rules.items():
        for plane, ids in (("static", rule["static"]), ("live", rule["live"])):
            for check_id in ids:
                slot = by_check.setdefault(check_id, {"planes": set(), "rules": []})
                slot["planes"].add(plane)
                if rule_id not in slot["rules"]:
                    slot["rules"].append(rule_id)
    rows = []
    for item in published:
        info = by_check.get(item["id"], {"planes": set(), "rules": []})
        source = item.get("source")
        if source in {"live", "static"}:
            evidence = source
        elif "live" in info["planes"]:
            evidence = "live"
        else:
            evidence = "static"
        nist = []
        for raw in item.get("nist") or []:
            nid = query_sources.nist_id_from_value(raw)
            if nid and nid not in nist:
                nist.append(nid)
        rows.append(
            {
                "id": item["id"],
                "evidence": evidence,
                "nist": nist,
                "rules": info["rules"],
            }
        )
    return rows


def compact_crosswalk(data, path, sha):
    """NIST id to PCI DSS v4.0 and FFIEC ids. The file adds no evidence."""
    raw = data.get("controls") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return None
    controls = {}
    for nist_id, body in raw.items():
        if not isinstance(nist_id, str) or not isinstance(body, dict):
            continue
        row = {}
        for plane in ("pci_dss_v4", "ffiec"):
            ids = []
            for item in body.get(plane) or []:
                if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] not in ids:
                    ids.append(item["id"])
            if ids:
                row[plane] = ids
        if row:
            controls[nist_id] = row
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    return {
        "path": path,
        "sha": sha,
        "version": meta.get("version"),
        "join": meta.get("join"),
        "controls": controls,
    }


def build_packet(catalog, bridge_text, catalog_sha, bridge_sha, catalog_names, compliance_names, matrix_names, inventory, coverage, intel, banking_crosswalk=None):
    pin = query_sources.load_json(query_sources.REF / "oscal-pin.json")
    rules = parse_bridge(bridge_text)
    checks = compliance_checks(catalog)
    static_ids, live_ids = bridged_ids(rules)
    wired = static_ids | live_ids
    published = [item for item in checks if item["id"] in wired]
    unwired = [item["id"] for item in checks if item["id"] not in wired]
    synthetic = {"suites": {"compliance": {"checks": published}}}
    covered = query_sources.catalog_covered_ids(synthetic)
    live = 0
    static = 0
    for item in published:
        source = item.get("source")
        if source == "live" or (source != "static" and item["id"] in live_ids):
            live += 1
        else:
            static += 1
    prior = prior_of(intel)
    dropped = now_covered(prior, covered)
    full = active_remaining(prior, dropped) >= 10
    found = query_sources.list_unresolved(
        catalog=synthetic,
        coverage=coverage if isinstance(coverage, dict) else {},
        intel=intel if isinstance(intel, dict) else {},
        limit=0 if full else 200,
        pin=pin,
    )
    controls = [] if full else found.get("controls") or []
    return {
        "result": "scan",
        "ref": REF,
        "oscal_release": pin.get("release"),
        "catalog": {
            "path": "%s/%s" % (CATALOG_DIR, CATALOG_NAME),
            "sha": catalog_sha,
            "listed": catalog_names,
            "compliance_listed": compliance_names,
            "matrix_listed": matrix_names,
            "checks": len(checks),
            "published": len(published),
            "live": live,
            "static": static,
            "nist_covered": len(covered),
            "unwired": unwired,
            "bridge_path": "%s/matrix/%s" % (COMPLIANCE_DIR, BRIDGE_NAME),
            "bridge_sha": bridge_sha,
            "bridge_rules": len(rules),
            "published_checks": published_index(published, rules),
        },
        "estate": estate_of(inventory),
        "prior_candidates": prior,
        "now_covered": dropped,
        "backlog_full": full,
        "unresolved_total": found.get("unresolved_total") or 0,
        "unresolved": controls,
        "banking_crosswalk": banking_crosswalk,
    }


def degraded(reason, **extra):
    payload = {"result": "sources_degraded", "ref": REF, "error": reason[:200]}
    payload.update(extra)
    return payload


def load_optional(workspace, rel):
    data = visit_common.load_json(workspace, rel)
    return data if isinstance(data, dict) else {}


def scan(workspace):
    listed, err = call("github_list_files", {"path": CATALOG_DIR, "ref": REF})
    if err:
        return degraded(err)
    entries = listed.get("entries") if isinstance(listed, dict) else None
    if not isinstance(entries, list):
        return degraded("catalog entries not a list")
    catalog_path = entry_path(entries, CATALOG_NAME, "file")
    if not catalog_path:
        return degraded("catalog listing has no %s" % CATALOG_NAME)
    catalog_names = names_of(entries, "file")

    listed, err = call("github_list_files", {"path": COMPLIANCE_DIR, "ref": REF})
    if err:
        return degraded(err)
    entries = listed.get("entries") if isinstance(listed, dict) else None
    if not isinstance(entries, list):
        return degraded("compliance entries not a list")
    matrix_path = entry_path(entries, "matrix", "dir")
    if not matrix_path:
        return degraded("compliance listing has no matrix directory")
    compliance_names = names_of(entries, "file") + names_of(entries, "dir")

    listed, err = call("github_list_files", {"path": matrix_path, "ref": REF})
    if err:
        return degraded(err)
    entries = listed.get("entries") if isinstance(listed, dict) else None
    if not isinstance(entries, list):
        return degraded("matrix entries not a list")
    bridge_path = entry_path(entries, BRIDGE_NAME, "file")
    if not bridge_path:
        return degraded("matrix listing has no %s" % BRIDGE_NAME)
    crosswalk_path = entry_path(entries, CROSSWALK_NAME, "file")
    matrix_names = names_of(entries, "file")

    catalog_body, err = call("github_get_file", {"path": catalog_path, "ref": REF})
    if err:
        return degraded(err)
    catalog_text = file_text(catalog_body)
    catalog_sha = catalog_body.get("sha") if isinstance(catalog_body, dict) else None
    if not isinstance(catalog_text, str) or not isinstance(catalog_sha, str):
        return degraded("catalog get had no content or sha")
    try:
        catalog = json.loads(catalog_text)
    except json.JSONDecodeError:
        return degraded("catalog JSON")
    if not isinstance(catalog, dict):
        return degraded("catalog must be an object")

    bridge_body, err = call("github_get_file", {"path": bridge_path, "ref": REF})
    if err:
        return degraded(err)
    bridge_text = file_text(bridge_body)
    bridge_sha = bridge_body.get("sha") if isinstance(bridge_body, dict) else None
    if not isinstance(bridge_text, str) or not isinstance(bridge_sha, str):
        return degraded("bridge get had no content or sha")

    banking = None
    if crosswalk_path:
        crosswalk_body, err = call("github_get_file", {"path": crosswalk_path, "ref": REF})
        if err:
            return degraded(err)
        crosswalk_text = file_text(crosswalk_body)
        crosswalk_sha = crosswalk_body.get("sha") if isinstance(crosswalk_body, dict) else None
        if not isinstance(crosswalk_text, str) or not isinstance(crosswalk_sha, str):
            return degraded("crosswalk get had no content or sha")
        try:
            crosswalk = json.loads(crosswalk_text)
        except json.JSONDecodeError:
            return degraded("crosswalk JSON")
        banking = compact_crosswalk(crosswalk, crosswalk_path, crosswalk_sha)

    packet = build_packet(
        catalog,
        bridge_text,
        catalog_sha,
        bridge_sha,
        catalog_names,
        compliance_names,
        matrix_names,
        load_optional(workspace, "inventory/prod.json"),
        load_optional(workspace, "compliance/coverage.json"),
        load_optional(workspace, "compliance/intel.json"),
        banking_crosswalk=banking,
    )
    if packet.get("result") == "scan":
        packet["coverage_counts"] = apply_catalog_coverage(workspace, packet)
    return packet


KEY_RE = re.compile(r"^(device|interface|site|service|test|control|incident|change):[^ ]+$")
BASE_RE = re.compile(r"^([A-Z]{2}-\d+)")
STATUS_RANK = {"covered": 0, "partial": 1, "unwired": 2, "gap": 3, "not_applicable": 4}


def utc_stamp():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_keys(values):
    found = []
    for item in values or []:
        if isinstance(item, str) and KEY_RE.match(item) and item not in found:
            found.append(item)
        if len(found) >= 32:
            break
    return found


def control_key(nist_id):
    return "control:%s" % nist_id


def recount(rows):
    counts = {name: 0 for name in STATUS_RANK}
    for row in rows:
        status = row.get("status")
        if status in counts:
            counts[status] += 1
    return counts


def union_keys(rows):
    found = []
    for row in rows:
        for key in row.get("keys") or []:
            if key not in found:
                found.append(key)
    return found


def dedupe_rows(rows):
    by_id = {}
    order = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        nist_id = row.get("nist_id")
        if not isinstance(nist_id, str) or not nist_id:
            continue
        keys = clean_keys(row.get("keys"))
        ck = control_key(nist_id)
        if ck not in keys:
            keys.insert(0, ck)
        row = dict(row)
        row["keys"] = keys[:32]
        current = by_id.get(nist_id)
        if current is None:
            by_id[nist_id] = row
            order.append(nist_id)
            continue
        if STATUS_RANK.get(row.get("status"), 9) < STATUS_RANK.get(current.get("status"), 9):
            kept, other = row, current
        else:
            kept, other = current, row
        merged = clean_keys((kept.get("keys") or []) + (other.get("keys") or []))
        kept = dict(kept)
        kept["keys"] = merged
        for field in ("live", "static", "net_comp"):
            values = []
            for source in (kept.get(field) or [], other.get(field) or []):
                for item in source:
                    if isinstance(item, str) and item not in values:
                        values.append(item)
            if values:
                kept[field] = values
        by_id[nist_id] = kept
    return [by_id[nist_id] for nist_id in order]


def covered_row(nist_id, checks):
    keys = [control_key(nist_id)]
    live, static, rules = [], [], []
    for check in checks:
        if nist_id not in (check.get("nist") or []):
            continue
        test_key = "test:%s" % check["id"]
        if test_key not in keys:
            keys.append(test_key)
        if check.get("evidence") == "live":
            if check["id"] not in live:
                live.append(check["id"])
        elif check["id"] not in static:
            static.append(check["id"])
        for rule in check.get("rules") or []:
            rule_key = "test:%s" % rule
            if rule_key not in keys:
                keys.append(rule_key)
            if rule not in rules:
                rules.append(rule)
    return {
        "nist_id": nist_id,
        "status": "covered",
        "keys": clean_keys(keys),
        "live": live,
        "static": static,
        "net_comp": rules,
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def apply_catalog_coverage(workspace, packet):
    """Upsert one covered row per bridged NIST id. Keep prior gap and N/A rows."""
    root = Path(workspace)
    path = root / "compliance" / "coverage.json"
    current = load_optional(workspace, "compliance/coverage.json")
    checks = ((packet.get("catalog") or {}).get("published_checks") or [])
    published = []
    for check in checks:
        for nist_id in check.get("nist") or []:
            if isinstance(nist_id, str) and nist_id not in published:
                published.append(nist_id)
    rows = dedupe_rows(current.get("rows") or [])
    by_id = {row["nist_id"]: row for row in rows}
    for nist_id in published:
        fresh = covered_row(nist_id, checks)
        prior = by_id.get(nist_id)
        if prior:
            for field in ("family_id", "title", "platforms"):
                if prior.get(field) and not fresh.get(field):
                    fresh[field] = prior[field]
            fresh["keys"] = clean_keys((fresh.get("keys") or []) + (prior.get("keys") or []))
        by_id[nist_id] = fresh
    ordered = []
    seen = set()
    for nist_id in published + [row["nist_id"] for row in rows]:
        if nist_id in by_id and nist_id not in seen:
            ordered.append(by_id[nist_id])
            seen.add(nist_id)
    payload = dict(current) if current else {}
    payload.update({
        "version": 1,
        "updated_at": utc_stamp(),
        "source_agent": "compliance-intel",
        "oscal_release": packet.get("oscal_release") or payload.get("oscal_release") or "v1.5.0",
        "git_ref": "main",
        "rows": ordered,
        "counts": recount(ordered),
        "keys": union_keys(ordered),
        "published_nist": published,
    })
    if not payload.get("estate_source"):
        payload["estate_source"] = "inventory/prod.json"
    write_json(path, payload)
    return payload["counts"]


def frameworks_for(nist_id, controls):
    """Exact crosswalk row, otherwise the base control (AC-17(2) uses AC-17)."""
    if not isinstance(controls, dict):
        return None
    row = controls.get(nist_id)
    if not isinstance(row, dict):
        match = BASE_RE.match(nist_id or "")
        base = match.group(1) if match else None
        if base and base != nist_id:
            row = controls.get(base)
    if not isinstance(row, dict):
        return None
    return {
        "pci_dss_v4": [item for item in (row.get("pci_dss_v4") or []) if isinstance(item, str)],
        "ffiec": [item for item in (row.get("ffiec") or []) if isinstance(item, str)],
    }


def candidate_nist_ids(candidate):
    ids = []
    for item in candidate.get("nist_sp_800_53") or []:
        mapped = query_sources.nist_id_from_value(item)
        if mapped and mapped not in ids:
            ids.append(mapped)
    source = query_sources.nist_id_from_value(candidate.get("source_control"))
    if source and source not in ids:
        ids.insert(0, source)
    return ids


def finalize(workspace):
    """Recount coverage from its rows and fill PCI/FFIEC ids from the crosswalk."""
    root = Path(workspace)
    coverage_path = root / "compliance" / "coverage.json"
    intel_path = root / "compliance" / "intel.json"
    coverage = load_optional(workspace, "compliance/coverage.json")
    intel = load_optional(workspace, "compliance/intel.json")
    if not coverage or not intel:
        return {"result": "failed", "error": "coverage.json and intel.json are both required"}
    published = [item for item in (coverage.get("published_nist") or []) if isinstance(item, str)]
    checks = []
    rows = dedupe_rows(coverage.get("rows") or [])
    by_id = {row["nist_id"]: row for row in rows}
    controls = ((intel.get("banking_crosswalk") or {}).get("controls") or {})
    candidates = []
    for candidate in intel.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        nist_ids = candidate_nist_ids(candidate)
        if published and nist_ids and all(item in published for item in nist_ids):
            continue
        mapped = None
        for nist_id in nist_ids:
            mapped = frameworks_for(nist_id, controls)
            if mapped:
                break
        if mapped:
            candidate = dict(candidate)
            candidate["frameworks"] = mapped
        if nist_ids and nist_ids[0] not in published:
            gap = by_id.get(nist_ids[0])
            if gap is None or gap.get("status") == "not_applicable":
                by_id[nist_ids[0]] = {
                    "nist_id": nist_ids[0],
                    "status": "gap",
                    "keys": clean_keys([control_key(nist_ids[0])]),
                }
        candidates.append(candidate)
    ordered_ids = []
    for row in rows:
        if row["nist_id"] not in ordered_ids:
            ordered_ids.append(row["nist_id"])
    for nist_id in by_id:
        if nist_id not in ordered_ids:
            ordered_ids.append(nist_id)
    ordered = [by_id[nist_id] for nist_id in ordered_ids if nist_id in by_id]
    for nist_id in published:
        if nist_id not in by_id:
            ordered.append(covered_row(nist_id, checks))
    ordered = dedupe_rows(ordered)
    counts = recount(ordered)
    coverage = dict(coverage)
    coverage["rows"] = ordered
    coverage["counts"] = counts
    coverage["keys"] = union_keys(ordered)
    coverage["updated_at"] = utc_stamp()
    coverage["source_agent"] = "compliance-intel"
    coverage["version"] = 1
    skipped = intel.get("skipped_non_network") or []
    na_ids = []
    for line in skipped:
        for match in query_sources.SKIPPED_ID_RE.finditer(str(line).upper()):
            mapped = query_sources.nist_id_from_value(match.group(1))
            if mapped and mapped not in na_ids:
                na_ids.append(mapped)
    intel = dict(intel)
    intel["candidates"] = candidates[:10]
    intel["delta"] = {
        "catalog_covered": counts["covered"],
        "relevant_missing": len(intel["candidates"]),
        "not_applicable": counts["not_applicable"],
    }
    intel["updated_at"] = coverage["updated_at"]
    write_json(coverage_path, coverage)
    write_json(intel_path, intel)
    return {
        "result": "finalized",
        "counts": counts,
        "candidates": len(intel["candidates"]),
        "delta": intel["delta"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan_cmd = sub.add_parser("scan", help="Fetch the published catalog and unresolved NIST titles")
    scan_cmd.add_argument("--workspace", required=True, help="file_explorer directory")
    done = sub.add_parser("finalize", help="Recount coverage and fill PCI/FFIEC ids")
    done.add_argument("--workspace", required=True, help="file_explorer directory")
    args = parser.parse_args(argv)
    if args.cmd == "scan":
        emit(scan(args.workspace))
    elif args.cmd == "finalize":
        emit(finalize(args.workspace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
