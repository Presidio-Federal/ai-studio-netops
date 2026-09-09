#!/usr/bin/env python3
"""Join published 800-53 ids to live/static tests from a local git checkout.

Studio must not run this script. Studio writes coverage.json from
github_get_file catalog + query_sources.py, and never dumps git into the
workspace.

Writes JSON to stdout. Never prints control statements.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
REF = SKILL_ROOT / "references"

GIT_PATHS = [
    "catalog/job-catalog.json",
    "tests/compliance/matrix/network-compliance-rule-matrix.v1.json",
    "tests/compliance/matrix/test-bridge.yml",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def find_repo_root(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "catalog" / "job-catalog.json").is_file() and (
            candidate / "tests" / "compliance" / "matrix"
        ).is_dir():
            return candidate
    skill_repo = SKILL_ROOT.parents[1]
    if (skill_repo / "catalog" / "job-catalog.json").is_file():
        return skill_repo
    return None


def parse_bridge(text: str) -> dict[str, dict[str, list[str]]]:
    rules: dict[str, dict[str, list[str]]] = {}
    current: str | None = None
    section: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        m = re.match(r"^  (NET-COMP-\d+):", line)
        if m:
            current = m.group(1)
            rules[current] = {"static_rules": [], "live_checks": []}
            section = None
            continue
        if current and "static_rules:" in line:
            section = "static_rules"
            continue
        if current and "live_checks:" in line:
            section = "live_checks"
            continue
        if current and section and line.strip().startswith("- "):
            rules[current][section].append(line.strip()[2:].strip())
    return rules


def parse_simple_yaml_map(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {"id": None, "nist": [], "platforms": []}
    section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if re.match(r"^id:\s*", line):
            data["id"] = line.split(":", 1)[1].strip().strip("'\"")
            section = None
        elif re.match(r"^nist:\s*$", line):
            section = "nist"
        elif re.match(r"^platforms:\s*$", line):
            section = "platforms"
        elif re.match(r"^platforms:\s*\[", line):
            inner = line.split("[", 1)[1].rsplit("]", 1)[0]
            data["platforms"] = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
            section = None
        elif section and line.strip().startswith("- "):
            data[section].append(line.strip()[2:].strip().strip("'\""))
        elif line and not line.startswith(" ") and not line.startswith("\t") and ":" in line:
            section = None
    return data


def parse_static_rules(text: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if re.match(r"^  - id:", line):
            if current:
                rules.append(current)
            current = {
                "id": line.split(":", 1)[1].strip().strip("'\""),
                "nist": [],
                "platforms": [],
            }
            section = None
            continue
        if current is None:
            continue
        if re.match(r"^    nist:", line):
            rest = line.split(":", 1)[1].strip()
            if rest.startswith("["):
                inner = rest.strip("[]")
                current["nist"] = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
                section = None
            else:
                section = "nist"
            continue
        if re.match(r"^    platforms:", line):
            rest = line.split(":", 1)[1].strip()
            if rest.startswith("["):
                inner = rest.strip("[]")
                current["platforms"] = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
                section = None
            else:
                section = "platforms"
            continue
        if section and line.strip().startswith("- "):
            current[section].append(line.strip()[2:].strip().strip("'\""))
        elif line.startswith("    ") and ":" in line and not line.strip().startswith("- "):
            section = None
    if current:
        rules.append(current)
    return rules


def nist_to_net_from_matrix(matrix: dict[str, Any]) -> dict[str, list[str]]:
    nist_to_net: dict[str, list[str]] = defaultdict(list)
    for rule in matrix.get("rules") or []:
        rid = rule.get("id")
        if not rid:
            continue
        for item in (rule.get("compliance") or {}).get("nist_sp_800_53_rev5") or []:
            cid = (item.get("id") or "").upper()
            if cid and rid not in nist_to_net[cid]:
                nist_to_net[cid].append(rid)
    return dict(nist_to_net)


def live_from_catalog(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    live: dict[str, dict[str, Any]] = {}
    for suite in (catalog.get("suites") or {}).values():
        for check in suite.get("checks") or []:
            cid = check.get("id")
            if not cid:
                continue
            nist = [str(n).upper() for n in (check.get("nist") or []) if n]
            live[cid] = {
                "nist": nist,
                "platforms": check.get("platforms") or ["iosxe", "cat9kv"],
            }
    return live


def static_from_bridge(bridge: dict[str, dict[str, list[str]]]) -> dict[str, dict[str, Any]]:
    static: dict[str, dict[str, Any]] = {}
    for mapped in bridge.values():
        for rid in mapped.get("static_rules") or []:
            static.setdefault(rid, {"nist": [], "platforms": []})
    return static


def estate_from_git_files(
    catalog: dict[str, Any],
    matrix: dict[str, Any],
    bridge_text: str,
    git_ref: str,
) -> dict[str, Any]:
    bridge = parse_bridge(bridge_text)
    return {
        "updated_at": utc_now(),
        "source": "git",
        "git_ref": git_ref,
        "git_paths": list(GIT_PATHS),
        "catalog_version": catalog.get("version"),
        "nist_to_net": nist_to_net_from_matrix(matrix),
        "bridge": bridge,
        "live": live_from_catalog(catalog),
        "static": static_from_bridge(bridge),
    }


def collect_from_repo(repo: Path) -> dict[str, Any]:
    catalog = json.loads((repo / "catalog/job-catalog.json").read_text(encoding="utf-8"))
    matrix = json.loads(
        (repo / "tests/compliance/matrix/network-compliance-rule-matrix.v1.json").read_text(
            encoding="utf-8"
        )
    )
    bridge_text = (repo / "tests/compliance/matrix/test-bridge.yml").read_text(encoding="utf-8")
    estate = estate_from_git_files(catalog, matrix, bridge_text, git_ref="local")
    live = dict(estate["live"])
    for yml in (repo / "tests/live/checks").rglob("*.yml"):
        if yml.parts[-2] == "_template":
            continue
        parsed = parse_simple_yaml_map(yml.read_text(encoding="utf-8"))
        cid = parsed.get("id")
        if not cid:
            continue
        nist = [n.upper() for n in (parsed.get("nist") or [])]
        if cid in live:
            merged = list(dict.fromkeys(live[cid]["nist"] + nist))
            plats = live[cid]["platforms"] or parsed.get("platforms") or []
            live[cid] = {"nist": merged, "platforms": plats or live[cid]["platforms"]}
        else:
            live[cid] = {
                "nist": nist,
                "platforms": parsed.get("platforms") or [],
            }
    static = dict(estate["static"])
    for yml in (repo / "tests/static/schemas").glob("*/rules.yml"):
        if yml.parent.name.startswith("_"):
            continue
        for rule in parse_static_rules(yml.read_text(encoding="utf-8")):
            rid = rule.get("id")
            if rid:
                static[rid] = {
                    "nist": [n.upper() for n in (rule.get("nist") or [])],
                    "platforms": rule.get("platforms") or [],
                }
    estate["live"] = live
    estate["static"] = static
    estate["source"] = "repo"
    return estate


def classify(live: list[str], static: list[str], net_comp: list[str]) -> tuple[str, str | None]:
    if live and static:
        return "covered", None
    if live and not static:
        return "partial", "live-only"
    if static and not live:
        return "partial", "static-only"
    if net_comp:
        return "gap", "no-tests"
    return "unwired", "tests-or-nist-without-net-comp"


def suggested_assert(status: str, why: str | None, nist_id: str, plats: list[str]) -> str | None:
    if status not in {"partial", "gap"}:
        return None
    where = ", ".join(plats) if plats else "iosxe"
    if why == "static-only":
        return f"Add a live check tagged nist: [{nist_id}] for {where}"
    if why == "live-only":
        return f"Add a static rule tagged nist: [{nist_id}] for {where}"
    return f"Add a live or static check tagged nist: [{nist_id}] for {where}"


def build_from_estate(estate: dict[str, Any], platforms: list[str]) -> dict[str, Any]:
    pin = json.loads((REF / "oscal-pin.json").read_text(encoding="utf-8"))
    index = json.loads((REF / pin["local_index"]).read_text(encoding="utf-8"))
    titles = {c["id"].upper(): c.get("title") for c in index.get("controls") or []}

    nist_to_net: dict[str, list[str]] = defaultdict(list, estate.get("nist_to_net") or {})
    bridge = estate.get("bridge") or {}
    live_by_id = estate.get("live") or {}
    static_by_id = estate.get("static") or {}

    nist_to_live: dict[str, list[str]] = defaultdict(list)
    for cid, meta in live_by_id.items():
        for nist in meta.get("nist") or []:
            nist_to_live[nist.upper()].append(cid)

    nist_to_static: dict[str, list[str]] = defaultdict(list)
    for rid, meta in static_by_id.items():
        for nist in meta.get("nist") or []:
            nist_to_static[nist.upper()].append(rid)

    net_to_live: dict[str, list[str]] = defaultdict(list)
    net_to_static: dict[str, list[str]] = defaultdict(list)
    for net_id, mapped in bridge.items():
        net_to_live[net_id].extend(mapped.get("live_checks") or [])
        net_to_static[net_id].extend(mapped.get("static_rules") or [])

    nist_ids = set(nist_to_net) | set(nist_to_live) | set(nist_to_static)
    rows = []
    for nist_id in sorted(nist_ids):
        nets = list(nist_to_net.get(nist_id, []))
        live = list(dict.fromkeys(nist_to_live.get(nist_id, [])))
        static = list(dict.fromkeys(nist_to_static.get(nist_id, [])))
        for net_id in nets:
            for item in net_to_live.get(net_id, []):
                if item in live_by_id and item not in live:
                    live.append(item)
            for item in net_to_static.get(net_id, []):
                if item in static_by_id and item not in static:
                    static.append(item)
        status, why = classify(live, static, nets)
        plats: list[str] = []
        for lid in live:
            plats.extend(live_by_id.get(lid, {}).get("platforms") or [])
        for sid in static:
            plats.extend(static_by_id.get(sid, {}).get("platforms") or [])
        plats = list(dict.fromkeys(plats)) or list(platforms)
        rows.append(
            {
                "nist_id": nist_id,
                "family_id": nist_id.split("-", 1)[0],
                "title": titles.get(nist_id) or nist_id,
                "net_comp": nets,
                "live": live,
                "static": static,
                "platforms": plats,
                "status": status,
                "partial_why": why,
                "suggested_assert": suggested_assert(status, why, nist_id, plats),
            }
        )

    counts = {"covered": 0, "partial": 0, "gap": 0, "unwired": 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    return {
        "version": 1,
        "updated_at": utc_now(),
        "source_agent": "compliance",
        "oscal_release": pin.get("release"),
        "estate_source": estate.get("source", "git"),
        "git_ref": estate.get("git_ref", "main"),
        "git_paths": estate.get("git_paths") or list(GIT_PATHS),
        "catalog_version": estate.get("catalog_version"),
        "platforms": platforms,
        "counts": counts,
        "rows": rows,
    }


def load_input(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    catalog = data.get("catalog")
    matrix = data.get("matrix")
    bridge = data.get("bridge")
    if not isinstance(catalog, dict) or not isinstance(matrix, dict) or not isinstance(bridge, str):
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "input must be JSON with catalog (object), matrix (object), bridge (yaml string)",
                }
            )
        )
        raise SystemExit(1)
    git_ref = str(data.get("git_ref") or "main")
    return estate_from_git_files(catalog, matrix, bridge, git_ref)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Local checkout JSON (Cursor only; not a Studio workspace file)",
    )
    parser.add_argument("--repo", type=Path, default=None, help="Local checkout (Cursor only)")
    parser.add_argument(
        "--platforms",
        default="iosxe,cat9kv",
        help="Comma-separated inventory platforms for this estate",
    )
    args = parser.parse_args(argv)
    if args.input:
        estate = load_input(args.input.resolve())
    elif args.repo:
        estate = collect_from_repo(args.repo.resolve())
    else:
        repo = find_repo_root()
        if repo is None:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "No git catalog. Fetch github_get_file and pass --input. Do not use a skill snapshot.",
                    }
                )
            )
            return 1
        estate = collect_from_repo(repo)
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    payload = build_from_estate(estate, platforms)
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
