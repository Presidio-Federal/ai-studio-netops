#!/usr/bin/env python3
"""Deterministic SHA-256 fingerprints for Compliance Intel inputs.

Hashes the pinned OSCAL index, an estate projection of inventory/prod.json,
and the git job-catalog JSON. Compares to prior compliance/metadata.json.
Stdout JSON. Never writes the workspace. Never copies the catalog to disk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
REF = SKILL_ROOT / "references"
HASH_PREFIX = "sha256:"
FRAMEWORK_NAME = "NIST-800-53"
SOURCE_AGENT = "compliance"
SCHEMA = "compliance-intel-metadata/v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{HASH_PREFIX}{digest}"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_optional(path: Path | None) -> Any | None:
    if path is None:
        return None
    if not path.is_file():
        return None
    return load_json(path)


def project_framework_controls(index: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for control in index.get("controls") or []:
        if not isinstance(control, dict):
            continue
        related = control.get("related") or []
        if not isinstance(related, list):
            related = []
        rows.append(
            {
                "id": control.get("id"),
                "title": control.get("title"),
                "family_id": control.get("family_id"),
                "related": sorted(str(item) for item in related),
            }
        )
    rows.sort(key=lambda row: str(row.get("id") or ""))
    return rows


def framework_record(index: dict[str, Any], pin: dict[str, Any]) -> dict[str, Any]:
    controls = project_framework_controls(index)
    release = str(pin.get("release") or index.get("oscal_release") or "")
    catalog_version = str(
        pin.get("catalog_version") or index.get("catalog_version") or ""
    )
    version = "/".join(part for part in (release, catalog_version) if part)
    source = str(
        pin.get("html_url")
        or pin.get("catalog_url")
        or pin.get("catalog_path")
        or ""
    )
    return {
        "name": FRAMEWORK_NAME,
        "version": version,
        "control_count": len(controls),
        "source": source,
        "hash": sha256_hex(controls),
    }


def project_estate(doc: dict[str, Any]) -> dict[str, Any]:
    devices: list[dict[str, Any]] = []
    for device in doc.get("devices") or []:
        if not isinstance(device, dict):
            continue
        tags = device.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        devices.append(
            {
                "agent_access": device.get("agent_access"),
                "name": device.get("name"),
                "platform": device.get("platform"),
                "role": device.get("role"),
                "tags": sorted(str(tag) for tag in tags),
            }
        )
    devices.sort(key=lambda row: str(row.get("name") or ""))
    links: list[dict[str, Any]] = []
    for link in doc.get("links") or []:
        if not isinstance(link, dict):
            continue
        links.append(
            {
                "a_device": link.get("a_device"),
                "a_interface": link.get("a_interface"),
                "b_device": link.get("b_device"),
                "b_interface": link.get("b_interface"),
            }
        )
    links.sort(
        key=lambda row: (
            str(row.get("a_device") or ""),
            str(row.get("a_interface") or ""),
            str(row.get("b_device") or ""),
            str(row.get("b_interface") or ""),
        )
    )
    return {
        "devices": devices,
        "environment": doc.get("environment"),
        "links": links,
    }


def estate_record(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(doc, dict):
        return None
    return {"hash": sha256_hex(project_estate(doc))}


def catalog_record(doc: Any | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    return {"hash": sha256_hex(doc)}


def work_flags(
    changed: list[str],
    *,
    missing_prior: bool,
    missing_coverage: bool,
) -> dict[str, bool]:
    framework_rescan = (
        missing_prior or missing_coverage or "framework" in changed
    )
    estate_rejudge = framework_rescan or "estate" in changed
    coverage_from_catalog = (not framework_rescan) and "catalog" in changed
    return {
        "reconcile_candidates": True,
        "framework_rescan": framework_rescan,
        "estate_rejudge": estate_rejudge,
        "coverage_from_catalog": coverage_from_catalog,
    }


def compare_hashes(
    current: dict[str, str | None],
    prior_last: dict[str, Any] | None,
) -> list[str]:
    changed: list[str] = []
    mapping = {
        "framework": "framework_hash",
        "estate": "estate_hash",
        "catalog": "catalog_hash",
    }
    if not isinstance(prior_last, dict):
        for name, value in current.items():
            if value:
                changed.append(name)
        return changed
    for name, key in mapping.items():
        now = current.get(name)
        then = prior_last.get(key)
        if not now:
            changed.append(name)
            continue
        if then != now:
            changed.append(name)
    return changed


def persist_payload(
    framework: dict[str, Any],
    estate: dict[str, Any] | None,
    catalog: dict[str, Any] | None,
) -> dict[str, Any]:
    last_evaluated = {
        "framework_hash": framework.get("hash"),
        "estate_hash": (estate or {}).get("hash"),
        "catalog_hash": (catalog or {}).get("hash"),
    }
    return {
        "schema": SCHEMA,
        "updated_at": utc_now(),
        "source_agent": SOURCE_AGENT,
        "framework": framework,
        "estate": estate or {"hash": None},
        "catalog": catalog or {"hash": None},
        "last_evaluated": last_evaluated,
    }


def read_catalog_arg(raw: str | None) -> Any | None:
    if raw is None:
        return None
    if raw == "-":
        text = sys.stdin.read()
        if not text.strip():
            return None
        return json.loads(text)
    path = Path(raw)
    if not path.is_file():
        return None
    return load_json(path)


def evaluate(
    *,
    index: dict[str, Any],
    pin: dict[str, Any],
    estate_doc: dict[str, Any] | None,
    catalog_doc: Any | None,
    prior: dict[str, Any] | None,
    missing_coverage: bool,
) -> dict[str, Any]:
    framework = framework_record(index, pin)
    estate = estate_record(estate_doc)
    catalog = catalog_record(catalog_doc)
    missing_prior = not isinstance(prior, dict)
    prior_last = None if missing_prior else prior.get("last_evaluated")
    current_hashes = {
        "framework": framework.get("hash"),
        "estate": None if estate is None else estate.get("hash"),
        "catalog": None if catalog is None else catalog.get("hash"),
    }
    if missing_prior:
        changed = [name for name, value in current_hashes.items() if value]
        if not current_hashes["estate"]:
            changed.append("estate")
        if not current_hashes["catalog"]:
            changed.append("catalog")
        # keep order stable and unique
        ordered = []
        for name in ("framework", "estate", "catalog"):
            if name in changed and name not in ordered:
                ordered.append(name)
        changed = ordered
    else:
        changed = compare_hashes(current_hashes, prior_last)
    work = work_flags(
        changed,
        missing_prior=missing_prior,
        missing_coverage=missing_coverage,
    )
    persist = persist_payload(framework, estate, catalog)
    return {
        "ok": True,
        "changed": changed,
        "missing_prior": missing_prior,
        "missing_coverage": missing_coverage,
        "work": work,
        "framework": framework,
        "estate": estate or {"hash": None},
        "catalog": catalog or {"hash": None},
        "last_evaluated": prior_last,
        "persist": persist,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--estate",
        type=Path,
        default=None,
        help="inventory/prod.json (workspace path). Omitted or missing → no estate hash.",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help="job-catalog JSON path, or '-' for stdin. Never a workspace catalog copy.",
    )
    parser.add_argument(
        "--prior",
        type=Path,
        default=None,
        help="compliance/metadata.json from the last successful evaluation",
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        default=None,
        help="compliance/coverage.json; missing file triggers framework_rescan",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="OSCAL title index JSON (default: skill references pin local_index)",
    )
    parser.add_argument(
        "--pin",
        type=Path,
        default=None,
        help="oscal-pin.json (default: skill references)",
    )
    args = parser.parse_args(argv)

    pin_path = args.pin or (REF / "oscal-pin.json")
    try:
        pin = load_json(pin_path)
    except (OSError, json.JSONDecodeError) as exc:
        json.dump({"ok": False, "error": f"pin: {exc}"}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1
    index_path = args.index or (REF / str(pin.get("local_index") or "oscal-800-53-rev5-index.json"))
    try:
        index = load_json(index_path)
    except (OSError, json.JSONDecodeError) as cli_exc:
        json.dump({"ok": False, "error": f"index: {cli_exc}"}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1

    estate_doc = load_json_optional(args.estate)
    try:
        catalog_doc = read_catalog_arg(args.catalog)
    except json.JSONDecodeError as exc:
        json.dump({"ok": False, "error": f"catalog: {exc}"}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1
    prior = load_json_optional(args.prior)
    missing_coverage = bool(args.coverage is not None and not args.coverage.is_file())

    payload = evaluate(
        index=index,
        pin=pin,
        estate_doc=estate_doc if isinstance(estate_doc, dict) else None,
        catalog_doc=catalog_doc,
        prior=prior if isinstance(prior, dict) else None,
        missing_coverage=missing_coverage,
    )
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
