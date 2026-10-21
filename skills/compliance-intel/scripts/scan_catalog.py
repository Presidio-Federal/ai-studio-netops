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


def build_packet(catalog, bridge_text, catalog_sha, bridge_sha, catalog_names, compliance_names, matrix_names, inventory, coverage, intel):
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

    return build_packet(
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
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan_cmd = sub.add_parser("scan", help="Fetch the published catalog and unresolved NIST titles")
    scan_cmd.add_argument("--workspace", required=True, help="file_explorer directory")
    args = parser.parse_args(argv)
    if args.cmd == "scan":
        emit(scan(args.workspace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
