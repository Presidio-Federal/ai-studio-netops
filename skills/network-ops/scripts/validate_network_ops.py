#!/usr/bin/env python3
"""Validate state/network-ops.json. Never contacts GitHub."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

SCHEMA = "network-ops-state/v3.3"
SOURCE_AGENT = "network-ops"
STATUSES = {
    "recommended",
    "committed",
    "ci_failed",
    "merged",
    "no_change",
    "unknown",
    "blocked",
    "failed",
}
MODES = {"recommend", "implement"}
KINDS = {"missing_config", "wrong_config", "test_bug", "other"}
VERIFIED_KINDS = {"missing_config", "wrong_config"}
RELS = {"depends_on", "caused", "resolved_by", "impacted"}
REL_ENDS = {
    "depends_on": (("service", "test", "application"), ("device", "interface")),
    "caused": (("device", "interface"), ("test", "service", "application", "incident")),
    "resolved_by": (("test", "incident"), ("change",)),
    "impacted": (("change",), ("application",)),
}
BLAST_BASIS = {"intended", "observed", "both", "none"}
PROBLEM_RE = re.compile(r"^P-\d{8}-\d{2}$")
INTERFACE_RE = re.compile(r"^[^ /]+/[^ ]+$")
CI_RESULTS = {"pass", "fail", "unknown", "running"}
KEY_RE = re.compile(
    r"^(device|interface|site|service|test|control|incident|change|application):[^ ].*$"
)
OPERATIONAL_REF_RE = re.compile(
    r"^operational/runs/\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z\.json$"
)
UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"
)
REQUIRED = [
    "schema",
    "updated_at",
    "source_agent",
    "status",
    "headline",
    "next_action",
    "mode",
    "problem_ref",
    "finding",
    "change",
    "git",
    "ci",
    "pr",
    "release",
    "relations",
    "keys",
]
OPS = {"ensure_present", "ensure_absent", "replace"}
RELEASE_STATUS = {None, "pending", "waiting", "released"}


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: validate_network_ops.py /workspace/state/network-ops.json")
    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        fail(f"file not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        fail("state must be an object")
    errors: list[str] = []
    for key in REQUIRED:
        if key not in data:
            errors.append(f"missing {key}")
    if data.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if data.get("source_agent") != SOURCE_AGENT:
        errors.append(f"source_agent must be {SOURCE_AGENT}")
    if data.get("status") not in STATUSES:
        errors.append("status is not an allowed word")
    if data.get("mode") not in MODES:
        errors.append("mode must be recommend or implement")
    headline = data.get("headline")
    if not isinstance(headline, str) or not headline.strip():
        errors.append("headline must be a non-empty string")
    nxt = data.get("next_action")
    if nxt is not None and not isinstance(nxt, str):
        errors.append("next_action must be a string or null")
    if nxt == "none":
        errors.append("next_action must not be the string none")
    updated = data.get("updated_at")
    if not isinstance(updated, str) or not UTC_RE.match(updated):
        errors.append("updated_at must be UTC ISO-8601")
    problem_ref = data.get("problem_ref")
    if problem_ref is not None and (
        not isinstance(problem_ref, str) or not PROBLEM_RE.match(problem_ref)
    ):
        errors.append("problem_ref must be P-<yyyymmdd>-<nn> or null")
    finding = data.get("finding")
    verified = False
    kind = None
    if not isinstance(finding, dict):
        errors.append("finding must be an object")
    else:
        kind = finding.get("kind")
        if kind not in KINDS:
            errors.append("finding.kind is not allowed")
        verified = finding.get("verified_in_git")
        if not isinstance(verified, bool):
            errors.append("finding.verified_in_git must be true or false")
            verified = False
        if kind in VERIFIED_KINDS and not verified:
            errors.append(f"finding.kind {kind} requires verified_in_git true")
        source = finding.get("source")
        if problem_ref and source != f"health:{problem_ref}":
            errors.append("finding.source must be health:<problem_ref> when problem_ref is set")
    status = data.get("status")
    change = data.get("change")
    if not isinstance(change, dict):
        errors.append("change must be an object")
    else:
        operational_ref = change.get("operational_ref")
        if operational_ref is not None and (
            not isinstance(operational_ref, str)
            or not OPERATIONAL_REF_RE.match(operational_ref)
        ):
            errors.append("change.operational_ref must be operational/runs/<UTC>.json or null")
        monitoring_ref = change.get("monitoring_ref")
        if monitoring_ref is not None and (
            not isinstance(monitoring_ref, str)
            or not OPERATIONAL_REF_RE.match(monitoring_ref)
        ):
            errors.append("change.monitoring_ref must be operational/runs/<UTC>.json or null")
        if not isinstance(change.get("devices") or [], list):
            errors.append("change.devices must be an array")
        interfaces = change.get("interfaces")
        if not isinstance(interfaces, list):
            errors.append("change.interfaces must be an array")
        else:
            for item in interfaces:
                if not isinstance(item, str) or not INTERFACE_RE.match(item):
                    errors.append(f"change.interfaces entry must be <device>/<interface>: {item}")
        blast = change.get("blast_radius")
        if not isinstance(blast, dict):
            errors.append("change.blast_radius must be an object")
        else:
            for field in ("hosts", "applications", "services"):
                items = blast.get(field)
                if not isinstance(items, list) or any(not isinstance(i, str) or not i for i in items):
                    errors.append(f"change.blast_radius.{field} must be an array of names")
                elif len(items) != len(set(items)):
                    errors.append(f"change.blast_radius.{field} must not contain duplicates")
            if blast.get("basis") not in BLAST_BASIS:
                errors.append("change.blast_radius.basis must be intended, observed, both, or none")
            if blast.get("source_ref") not in (None, "state/relationships.json"):
                errors.append("change.blast_radius.source_ref must be state/relationships.json or null")
        annotation_ref = change.get("annotation_ref", "missing")
        if annotation_ref is not None and not isinstance(annotation_ref, str):
            errors.append("change.annotation_ref must be a string or null")
        if annotation_ref is not None and data.get("status") != "merged":
            errors.append("change.annotation_ref is only set on a merged change")
        prescription = change.get("prescription", "missing")
        if prescription is None:
            pass
        elif not isinstance(prescription, dict):
            errors.append("change.prescription must be an object or null")
        else:
            if prescription.get("operation") not in OPS:
                errors.append("change.prescription.operation is not allowed")
            targets = prescription.get("targets")
            if (
                not isinstance(targets, list)
                or not targets
                or any(not isinstance(item, str) or not item.strip() for item in targets)
            ):
                errors.append("change.prescription.targets must be hostnames")
            elif len(targets) != len(set(targets)):
                errors.append("change.prescription.targets must not contain duplicates")
            for field in ("lines", "old_lines"):
                rows = prescription.get(field)
                if not isinstance(rows, list) or any(not isinstance(item, str) or not item for item in rows):
                    errors.append(f"change.prescription.{field} must be an array of lines")
            if prescription.get("operation") == "replace" and not prescription.get("old_lines"):
                errors.append("change.prescription.old_lines is required for replace")
            if prescription.get("operation") in {"ensure_present", "ensure_absent", "replace"} and not prescription.get("lines"):
                errors.append("change.prescription.lines is required")
            for field in ("scope", "placement", "constraints"):
                value = prescription.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"change.prescription.{field} must be a non-empty string")
    release = data.get("release")
    if not isinstance(release, dict):
        errors.append("release must be an object")
    elif release.get("status") not in RELEASE_STATUS:
        errors.append("release.status must be pending, waiting, released, or null")
    git = data.get("git")
    if isinstance(git, dict) and git.get("ref") == "main" and data.get("status") != "merged":
        errors.append("git.ref must be dev until merged")
    ci = data.get("ci")
    if isinstance(ci, dict):
        result = ci.get("result")
        if result is not None and result not in CI_RESULTS:
            errors.append("ci.result is not allowed")
        if "passed_sha" not in ci:
            errors.append("ci.passed_sha is required")
        elif ci.get("passed_sha") is not None and not isinstance(ci.get("passed_sha"), str):
            errors.append("ci.passed_sha must be a string or null")
    keys = data.get("keys")
    if not isinstance(keys, list):
        errors.append("keys must be an array")
        keys = []
    elif len(keys) != len(set(keys)):
        errors.append("keys must not contain duplicates")
    for key in keys:
        if not isinstance(key, str) or not KEY_RE.match(key):
            errors.append(f"keys contains invalid type:name key: {key}")
    relations = data.get("relations")
    relation_keys: set[str] = set()
    if not isinstance(relations, list):
        errors.append("relations must be an array")
        relations = []
    for index, rel in enumerate(relations):
        label = f"relations[{index}]"
        if not isinstance(rel, dict):
            errors.append(f"{label} must be an object")
            continue
        name = rel.get("rel")
        if name not in RELS:
            errors.append(f"{label}.rel must be depends_on, caused, resolved_by, or impacted")
            continue
        if rel.get("basis") != "asserted":
            errors.append(f"{label}.basis must be asserted")
        evidence = rel.get("evidence_ref")
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"{label}.evidence_ref is required")
        src, dst = rel.get("from"), rel.get("to")
        for end, value, allowed in (("from", src, REL_ENDS[name][0]), ("to", dst, REL_ENDS[name][1])):
            if not isinstance(value, str) or not KEY_RE.match(value):
                errors.append(f"{label}.{end} must be a canonical key")
                continue
            if value.split(":", 1)[0] not in allowed:
                errors.append(f"{label}.{end} for {name} must be one of {list(allowed)}")
            relation_keys.add(value)
        if name == "caused" and not (verified and kind in VERIFIED_KINDS):
            errors.append(f"{label}: caused requires finding.verified_in_git true and kind missing_config or wrong_config")
        if name == "impacted":
            if status != "merged":
                errors.append(f"{label}: impacted is only written on a merged change")
            git_sha = (data.get("git") or {}).get("commit_sha") if isinstance(data.get("git"), dict) else None
            if isinstance(src, str) and git_sha and src != f"change:{git_sha}":
                errors.append(f"{label}.from must be change:<git.commit_sha>")
        if name == "resolved_by":
            if status != "merged":
                errors.append(f"{label}: resolved_by is only written on a merged change")
            git_sha = (data.get("git") or {}).get("commit_sha") if isinstance(data.get("git"), dict) else None
            if isinstance(dst, str) and git_sha and dst != f"change:{git_sha}":
                errors.append(f"{label}.to must be change:<git.commit_sha>")
    if isinstance(change, dict):
        expected_keys = set(relation_keys)
        for device in change.get("devices") or []:
            if isinstance(device, str):
                expected_keys.add(f"device:{device}")
        for interface in change.get("interfaces") or []:
            if isinstance(interface, str):
                expected_keys.add(f"interface:{interface}")
        if set(keys) != expected_keys:
            errors.append(
                "keys must equal the union of change.devices, change.interfaces, and relations ends: "
                + ", ".join(sorted(expected_keys))
            )
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"ok": True, "path": path}))


if __name__ == "__main__":
    main()
