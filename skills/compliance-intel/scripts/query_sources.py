#!/usr/bin/env python3
"""Query STIG Viewer (public controls) and the pinned OSCAL 800-53 index.

Never prints control statements or guidance. Identifiers, titles, and mappings only.
Overlap with existing tests comes from this run's coverage.json or the git
input JSON — not a skill-bundled test list.

`unresolved` filters the pinned title index against a git job-catalog,
coverage.json, and intel.json. It does not judge estate applicability.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
REF = SKILL_ROOT / "references"
STIGVIEWER = "https://www.stigviewer.com"
UA = "cml-ai-automation-compliance-intel/1.3 (+compliance-intel)"
NETWORK_FAMILIES = {"AC", "AU", "CM", "IA", "SC", "SI"}
URL_RE = re.compile(
    r"stigviewer\.com/controls/(nist-800-53|nist-800-171)/([^/?#]+)",
    re.I,
)
ID_171_RE = re.compile(r"^(?:SP_800_171_)?(\d{1,2})\.(\d{1,2})\.(\d{1,2})$", re.I)
ID_171_OSCAL_RE = re.compile(r"^(?:SP_800_171_)?0?(\d{1,2})\.0?(\d{1,2})\.0?(\d{1,2})$")
ID_53_RE = re.compile(r"^([A-Z]{2})-(\d+)(?:\((\d+)\))?$", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def http_json(url: str, token: str | None = None, timeout: int = 20) -> tuple[int, Any]:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        body: Any
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {"error": str(exc)}
        return exc.code, body
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return 0, {"error": str(exc)}


def public_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop copyrighted statement/guidance before anything is printed."""
    keep = (
        "id",
        "framework",
        "identifier",
        "title",
        "family",
        "baselines",
        "requirementType",
        "version",
    )
    return {k: payload[k] for k in keep if k in payload}


def normalize_171(raw: str) -> str | None:
    text = raw.strip().replace("-", ".")
    text = re.sub(r"^SP_800_171_", "", text, flags=re.I)
    m = ID_171_OSCAL_RE.match(text) or ID_171_RE.match(text)
    if not m:
        return None
    return f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"


def normalize_53(raw: str) -> str | None:
    text = raw.strip().upper().replace(" ", "")
    text = text.replace("NIST-800-53:", "").replace("NIST_800_53:", "")
    m = ID_53_RE.match(text)
    if not m:
        return None
    base = f"{m.group(1).upper()}-{int(m.group(2))}"
    if m.group(3):
        return f"{base}({int(m.group(3))})"
    return base


def parse_query(raw: str) -> dict[str, str]:
    text = raw.strip()
    m = URL_RE.search(text)
    if m:
        framework = m.group(1).lower()
        ident = urllib.parse.unquote(m.group(2))
        if framework == "nist-800-171":
            nid = normalize_171(ident)
            return {
                "raw": text,
                "kind": "nist-800-171",
                "identifier": nid or ident,
                "url": f"{STIGVIEWER}/controls/nist-800-171/{nid or ident}",
            }
        nid = normalize_53(ident)
        return {
            "raw": text,
            "kind": "nist-800-53",
            "identifier": nid or ident.upper(),
            "url": f"{STIGVIEWER}/controls/nist-800-53/{nid or ident}",
        }
    if ":" in text and not text.lower().startswith("http"):
        fw, ident = text.split(":", 1)
        fw = fw.strip().lower().replace("_", "-")
        if fw in {"nist-800-171", "800-171"}:
            nid = normalize_171(ident)
            return {
                "raw": text,
                "kind": "nist-800-171",
                "identifier": nid or ident,
                "url": f"{STIGVIEWER}/controls/nist-800-171/{nid or ident}",
            }
        nid = normalize_53(ident)
        return {
            "raw": text,
            "kind": "nist-800-53",
            "identifier": nid or ident.upper(),
            "url": f"{STIGVIEWER}/controls/nist-800-53/{nid or ident}",
        }
    if normalize_171(text):
        nid = normalize_171(text)
        return {
            "raw": text,
            "kind": "nist-800-171",
            "identifier": nid or text,
            "url": f"{STIGVIEWER}/controls/nist-800-171/{nid}",
        }
    nid = normalize_53(text)
    if nid:
        return {
            "raw": text,
            "kind": "nist-800-53",
            "identifier": nid,
            "url": f"{STIGVIEWER}/controls/nist-800-53/{nid}",
        }
    return {"raw": text, "kind": "unknown", "identifier": text, "url": ""}


def index_by_id(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"].upper(): c for c in index.get("controls") or [] if c.get("id")}


def family_id_of(control_id: str) -> str:
    return control_id.split("-", 1)[0].upper()


def is_network(control_id: str) -> bool:
    return family_id_of(control_id) in NETWORK_FAMILIES


def overlap_from_matrix_catalog(
    matrix: dict[str, Any] | None,
    catalog: dict[str, Any] | None,
    stig: dict[str, Any] | None = None,
) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    if matrix:
        for rule in matrix.get("rules") or []:
            rid = rule.get("id")
            if not rid:
                continue
            nist = (rule.get("compliance") or {}).get("nist_sp_800_53_rev5") or []
            for item in nist:
                cid = (item.get("id") or "").upper()
                if not cid:
                    continue
                bucket = out.setdefault(cid, {"net_comp": [], "stig": []})
                if rid not in bucket["net_comp"]:
                    bucket["net_comp"].append(rid)
    if stig:
        mappings = stig.get("mappings") or {}
        for net_id, refs in mappings.items():
            for ref in refs or []:
                label = ref.get("id") or ref.get("label")
                if not label:
                    continue
                for cid, bucket in out.items():
                    if net_id in bucket["net_comp"] and label not in bucket["stig"]:
                        bucket["stig"].append(label)
    if catalog:
        ids: list[str] = []
        for suite in (catalog.get("suites") or {}).values():
            for check in suite.get("checks") or []:
                cid = check.get("id")
                if cid and cid not in ids:
                    ids.append(cid)
        out.setdefault("_catalog_checks", {"net_comp": ids, "stig": []})
    return out


def overlap_from_coverage(coverage: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    live_ids: list[str] = []
    for row in coverage.get("rows") or []:
        cid = (row.get("nist_id") or "").upper()
        if not cid:
            continue
        nets = list(row.get("net_comp") or [])
        out[cid] = {"net_comp": nets, "stig": []}
        for item in row.get("live") or []:
            if item not in live_ids:
                live_ids.append(item)
    out.setdefault("_catalog_checks", {"net_comp": live_ids, "stig": []})
    return out


def load_overlap(
    repo: Path | None,
    *,
    input_path: Path | None = None,
    coverage_path: Path | None = None,
) -> dict[str, dict[str, list[str]]]:
    if coverage_path and coverage_path.is_file():
        return overlap_from_coverage(load_json(coverage_path))
    if input_path and input_path.is_file():
        data = load_json(input_path)
        return overlap_from_matrix_catalog(
            data.get("matrix") if isinstance(data.get("matrix"), dict) else None,
            data.get("catalog") if isinstance(data.get("catalog"), dict) else None,
        )
    if repo is None:
        return {}
    matrix = None
    catalog = None
    stig = None
    matrix_path = repo / "tests/compliance/matrix/network-compliance-rule-matrix.v1.json"
    if matrix_path.is_file():
        matrix = load_json(matrix_path)
    catalog_path = repo / "catalog/job-catalog.json"
    if catalog_path.is_file():
        catalog = load_json(catalog_path)
    stig_path = repo / "tests/compliance/matrix/stig-rule-map.v1.json"
    if stig_path.is_file():
        stig = load_json(stig_path)
    return overlap_from_matrix_catalog(matrix, catalog, stig)


def maps_to_existing(control_id: str, overlap: dict[str, dict[str, list[str]]]) -> str:
    bucket = overlap.get(control_id.upper())
    if not bucket or not bucket.get("net_comp"):
        return "none"
    return ", ".join(bucket["net_comp"])


def disa_footnote(control_id: str, overlap: dict[str, dict[str, list[str]]]) -> str | None:
    bucket = overlap.get(control_id.upper())
    if not bucket or not bucket.get("stig"):
        return None
    return bucket["stig"][0]


def fetch_stigviewer_control(framework: str, identifier: str) -> tuple[dict[str, Any], dict[str, Any]]:
    url = f"{STIGVIEWER}/api/v1/controls/{framework}/{urllib.parse.quote(identifier)}"
    status, body = http_json(url)
    source = {
        "name": f"STIG Viewer {framework} {identifier}",
        "url": url,
        "checked_at": utc_now(),
        "ok": status == 200,
        "http_status": status,
    }
    if status == 200 and isinstance(body, dict):
        return public_record(body), source
    return {}, source


def fetch_crosswalk(identifier: str, token: str | None) -> tuple[list[str], dict[str, Any], str | None]:
    qs = urllib.parse.urlencode(
        {"from": f"nist-800-171:{identifier}", "to": "nist-800-53", "maxHops": 4}
    )
    url = f"{STIGVIEWER}/api/v1/crosswalk/resolve?{qs}"
    status, body = http_json(url, token=token)
    source = {
        "name": f"STIG Viewer crosswalk {identifier}",
        "url": url,
        "checked_at": utc_now(),
        "ok": status == 200,
        "http_status": status,
    }
    if status == 200 and isinstance(body, dict):
        ids: list[str] = []
        for path in body.get("paths") or []:
            for node in path.get("controls") or []:
                if node.get("framework") == "nist-800-53":
                    nid = normalize_53(str(node.get("identifier") or ""))
                    if nid and nid not in ids:
                        ids.append(nid)
        return ids, source, None
    warning = None
    if status in {401, 403}:
        warning = (
            "STIG Viewer crosswalk requires a SAMS token; "
            "used NIST SP 800-171 Rev 2 Table D-1 locally"
        )
    elif status != 200:
        warning = f"STIG Viewer crosswalk unavailable ({status}); used local Table D-1"
    return [], source, warning


def resolve_171(
    identifier: str,
    table: dict[str, Any],
    token: str | None,
    online: bool,
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    sources: list[dict[str, Any]] = []
    warnings: list[str] = []
    ids: list[str] = []
    if online:
        ids, xw_source, warning = fetch_crosswalk(identifier, token)
        sources.append(xw_source)
        if warning:
            warnings.append(warning)
    if not ids:
        mapped = (table.get("map") or {}).get(identifier) or []
        ids = [normalize_53(x) or x for x in mapped]
        sources.append(
            {
                "name": "NIST SP 800-171 Rev 2 Table D-1 (local)",
                "url": table.get("source_url") or "",
                "checked_at": utc_now(),
                "ok": bool(ids),
            }
        )
        if not ids:
            warnings.append(f"No 800-53 mapping for 800-171 {identifier}")
    return ids, sources, warnings


def record_for_53(
    control_id: str,
    index_map: dict[str, dict[str, Any]],
    overlap: dict[str, dict[str, list[str]]],
    resolved_from: str | None,
    oscal_release: str,
    stig_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    indexed = index_map.get(control_id.upper()) or {}
    title = (stig_meta or {}).get("title") or indexed.get("title") or control_id
    family = (stig_meta or {}).get("family") or indexed.get("family") or ""
    return {
        "source_control": f"nist-800-53:{control_id}",
        "resolved_from": resolved_from,
        "title": title,
        "family": family,
        "family_id": indexed.get("family_id") or family_id_of(control_id),
        "related": indexed.get("related") or [],
        "network_relevant": is_network(control_id),
        "maps_to_existing": maps_to_existing(control_id, overlap),
        "disa_footnote": disa_footnote(control_id, overlap),
        "stigviewer_url": f"{STIGVIEWER}/controls/nist-800-53/{control_id}",
        "oscal_release": oscal_release,
    }


def lookup(
    raw: str,
    repo: Path | None,
    online: bool,
    *,
    input_path: Path | None = None,
    coverage_path: Path | None = None,
) -> dict[str, Any]:
    pin = load_json(REF / "oscal-pin.json")
    index = load_json(REF / pin["local_index"])
    table = load_json(REF / "nist-800-171-rev2-to-800-53.json")
    index_map = index_by_id(index)
    overlap = load_overlap(repo, input_path=input_path, coverage_path=coverage_path)
    query = parse_query(raw)
    token = os.environ.get("STIGVIEWER_TOKEN") or os.environ.get("SAMS_TOKEN")
    sources: list[dict[str, Any]] = [
        {
            "name": f"OSCAL 800-53 index {pin['release']}",
            "url": pin.get("html_url") or pin.get("catalog_url"),
            "checked_at": utc_now(),
            "ok": True,
        }
    ]
    warnings: list[str] = []
    resolved: list[dict[str, Any]] = []
    skipped: list[str] = []

    if query["kind"] == "unknown":
        return {
            "ok": False,
            "oscal_release": pin["release"],
            "query": query,
            "sources": sources,
            "resolved": [],
            "skipped_non_network": [],
            "warnings": [f"Could not parse control id or STIG Viewer URL: {raw}"],
        }

    nist_ids: list[str] = []
    resolved_from = None
    stig_by_id: dict[str, dict[str, Any]] = {}

    if query["kind"] == "nist-800-171":
        resolved_from = f"nist-800-171:{query['identifier']}"
        if online:
            meta, src = fetch_stigviewer_control("nist-800-171", query["identifier"])
            sources.append(src)
            if meta:
                sources[-1]["page"] = query.get("url")
        mapped, extra_sources, extra_warnings = resolve_171(
            query["identifier"], table, token, online
        )
        sources.extend(extra_sources)
        warnings.extend(extra_warnings)
        nist_ids = mapped
        if online:
            for cid in nist_ids:
                meta, src = fetch_stigviewer_control("nist-800-53", cid)
                sources.append(src)
                if meta:
                    stig_by_id[cid] = meta
    else:
        nist_ids = [query["identifier"]]
        if online:
            meta, src = fetch_stigviewer_control("nist-800-53", query["identifier"])
            sources.append(src)
            if meta:
                stig_by_id[query["identifier"]] = meta

    for cid in nist_ids:
        rec = record_for_53(
            cid,
            index_map,
            overlap,
            resolved_from,
            pin["release"],
            stig_by_id.get(cid),
        )
        if rec["network_relevant"]:
            resolved.append(rec)
        else:
            skipped.append(f"{cid} ({rec['family'] or 'non-network family'})")

    ok = bool(resolved) or bool(skipped)
    return {
        "ok": ok,
        "oscal_release": pin["release"],
        "catalog_version": index.get("catalog_version"),
        "query": query,
        "sources": sources,
        "resolved": resolved,
        "skipped_non_network": skipped,
        "warnings": warnings,
        "existing_compliance_checks": (overlap.get("_catalog_checks") or {}).get("net_comp") or [],
    }


def list_family(family: str) -> dict[str, Any]:
    pin = load_json(REF / "oscal-pin.json")
    index = load_json(REF / pin["local_index"])
    key = family.strip().upper()
    rows = [
        {"id": c["id"], "title": c["title"], "family": c["family"]}
        for c in index.get("controls") or []
        if c.get("family_id") == key or (c.get("family") or "").lower() == family.strip().lower()
    ]
    return {
        "ok": bool(rows),
        "oscal_release": pin["release"],
        "family": key,
        "controls": rows,
        "note": "Titles only. Network-relevant families in the local index: AC AU CM IA SC SI.",
    }


DEFAULT_UNRESOLVED_LIMIT = 20
NA_COVERAGE_STATUSES = {"not_applicable", "n/a", "na"}
ACTIVE_CANDIDATE_STATUSES = {"proposed", "accepted"}
SKIPPED_ID_RE = re.compile(r"\b([A-Z]{2}-\d+(?:\(\d+\))?)\b")


def nist_id_from_value(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if ":" in text and not text.lower().startswith("http"):
        text = text.split(":", 1)[1].strip()
    return normalize_53(text)


def catalog_covered_ids(catalog: dict[str, Any] | None) -> set[str]:
    """NIST ids already mapped on a committed git job-catalog check (`nist:`)."""
    data = catalog or {}
    if isinstance(data.get("catalog"), dict):
        data = data["catalog"]
    ids: set[str] = set()
    for suite in (data.get("suites") or {}).values():
        if not isinstance(suite, dict):
            continue
        for check in suite.get("checks") or []:
            if not isinstance(check, dict):
                continue
            for item in check.get("nist") or []:
                nid = nist_id_from_value(item)
                if nid:
                    ids.add(nid)
    return ids


def coverage_row_ids(coverage: dict[str, Any] | None, statuses: set[str]) -> set[str]:
    ids: set[str] = set()
    for row in (coverage or {}).get("rows") or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip().lower().replace(" ", "_")
        if status not in statuses:
            continue
        nid = nist_id_from_value(row.get("nist_id"))
        if nid:
            ids.add(nid)
    return ids


def coverage_not_applicable_ids(coverage: dict[str, Any] | None) -> set[str]:
    """Controls coverage already recorded as not applicable to this estate."""
    return coverage_row_ids(coverage, NA_COVERAGE_STATUSES)


def coverage_covered_ids(coverage: dict[str, Any] | None) -> set[str]:
    """Controls coverage already recorded as covered (catalog reconcile or prior review)."""
    return coverage_row_ids(coverage, {"covered"})


def intel_not_applicable_ids(intel: dict[str, Any] | None) -> set[str]:
    """Control ids Intel already classified N/A on skipped_non_network."""
    ids: set[str] = set()
    for line in (intel or {}).get("skipped_non_network") or []:
        for match in SKIPPED_ID_RE.finditer(str(line).upper()):
            nid = normalize_53(match.group(1))
            if nid:
                ids.add(nid)
    return ids


def intel_candidate_ids(intel: dict[str, Any] | None) -> set[str]:
    """NIST ids already proposed (or accepted) on the current intel result."""
    ids: set[str] = set()
    for cand in (intel or {}).get("candidates") or []:
        if not isinstance(cand, dict):
            continue
        status = str(cand.get("status") or "proposed").strip().lower()
        if status not in ACTIVE_CANDIDATE_STATUSES:
            continue
        nid = nist_id_from_value(cand.get("source_control"))
        if nid:
            ids.add(nid)
        for item in cand.get("nist_sp_800_53") or []:
            mapped = nist_id_from_value(item)
            if mapped:
                ids.add(mapped)
    return ids


def load_json_arg(path: Path | None, *, stdin_ok: bool = False) -> dict[str, Any]:
    if path is None:
        return {}
    if stdin_ok and os.fspath(path) == "-":
        data = json.load(sys.stdin)
        return data if isinstance(data, dict) else {}
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    data = load_json(resolved)
    return data if isinstance(data, dict) else {}


def list_unresolved(
    *,
    catalog: dict[str, Any] | None = None,
    coverage: dict[str, Any] | None = None,
    intel: dict[str, Any] | None = None,
    limit: int = DEFAULT_UNRESOLVED_LIMIT,
    index: dict[str, Any] | None = None,
    pin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic unresolved NIST titles. No applicability ranking."""
    if pin is None:
        pin = load_json(REF / "oscal-pin.json")
    if index is None:
        index = load_json(REF / pin["local_index"])
    if limit < 0:
        return {
            "ok": False,
            "oscal_release": pin.get("release"),
            "error": "--limit must be >= 0",
            "unresolved_total": 0,
            "returned": 0,
            "limit": limit,
            "controls": [],
        }

    covered = catalog_covered_ids(catalog) | coverage_covered_ids(coverage)
    not_applicable = coverage_not_applicable_ids(coverage) | intel_not_applicable_ids(intel)
    candidates = intel_candidate_ids(intel)

    excluded = {"covered": 0, "not_applicable": 0, "intel_candidate": 0}
    unresolved: list[dict[str, str]] = []
    for control in index.get("controls") or []:
        cid = nist_id_from_value(control.get("id"))
        if not cid:
            continue
        if cid in covered:
            excluded["covered"] += 1
            continue
        if cid in not_applicable:
            excluded["not_applicable"] += 1
            continue
        if cid in candidates:
            excluded["intel_candidate"] += 1
            continue
        unresolved.append(
            {
                "id": control.get("id") or cid,
                "title": control.get("title") or cid,
                "family": control.get("family") or "",
            }
        )

    returned = unresolved[:limit]
    return {
        "ok": True,
        "oscal_release": pin.get("release") or index.get("oscal_release"),
        "catalog_version": index.get("catalog_version"),
        "unresolved_total": len(unresolved),
        "returned": len(returned),
        "limit": limit,
        "excluded": excluded,
        "controls": returned,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    look = sub.add_parser("lookup", help="Resolve a 800-53 id, 800-171 id, or STIG Viewer URL")
    look.add_argument("query", help="AC-17, 3.1.7, nist-800-171:3.1.7, or a stigviewer.com URL")
    look.add_argument("--offline", action="store_true", help="Skip STIG Viewer HTTP; local index + Table D-1 only")
    look.add_argument("--repo", type=Path, default=None, help="Local checkout (Cursor only)")
    look.add_argument(
        "--coverage",
        type=Path,
        default=None,
        help="Workspace compliance/coverage.json from this run (preferred overlap)",
    )
    look.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Local JSON with catalog/matrix/bridge (Cursor checkout only; not a workspace catalog path)",
    )

    fam = sub.add_parser("family", help="List pinned OSCAL titles in a network family")
    fam.add_argument("family", help="AC, AU, CM, IA, SC, or SI")

    unres = sub.add_parser(
        "unresolved",
        help="Pinned NIST titles not covered in git, classified N/A, or an active intel candidate",
    )
    unres.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_UNRESOLVED_LIMIT,
        help=f"Max controls to return (default {DEFAULT_UNRESOLVED_LIMIT})",
    )
    unres.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Git catalog/job-catalog.json path, or - for stdin. Never a workspace copy in Studio.",
    )
    unres.add_argument(
        "--coverage",
        type=Path,
        default=None,
        help="Workspace compliance/coverage.json (not-applicable rows)",
    )
    unres.add_argument(
        "--intel",
        type=Path,
        default=None,
        help="Workspace compliance/intel.json (candidates + skipped_non_network)",
    )

    args = parser.parse_args(argv)
    if args.cmd == "family":
        payload = list_family(args.family)
    elif args.cmd == "unresolved":
        try:
            catalog = load_json_arg(args.catalog, stdin_ok=True)
            coverage = load_json_arg(args.coverage)
            intel = load_json_arg(args.intel)
        except FileNotFoundError as exc:
            payload = {"ok": False, "error": str(exc), "controls": []}
        except json.JSONDecodeError as exc:
            payload = {"ok": False, "error": f"Invalid JSON: {exc}", "controls": []}
        else:
            payload = list_unresolved(
                catalog=catalog,
                coverage=coverage,
                intel=intel,
                limit=args.limit,
            )
    else:
        coverage = args.coverage.resolve() if args.coverage else None
        git_input = args.input.resolve() if args.input else None
        repo = args.repo.resolve() if args.repo else (None if (coverage or git_input) else find_repo_root())
        payload = lookup(
            args.query,
            repo,
            online=not args.offline,
            input_path=git_input,
            coverage_path=coverage,
        )
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
