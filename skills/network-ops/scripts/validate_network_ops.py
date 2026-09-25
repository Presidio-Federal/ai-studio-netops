#!/usr/bin/env python3
"""Validate state/network-ops.json. Never contacts GitHub."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

SCHEMA = "network-ops-state/v3"
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
RELS = {"depends_on", "caused", "resolved_by"}
REL_ENDS = {
    "depends_on": (("service", "test"), ("device", "interface")),
    "caused": (("device", "interface"), ("test", "service", "incident")),
    "resolved_by": (("test", "incident"), ("change",)),
}
PROBLEM_RE = re.compile(r"^P-\d{8}-\d{2}$")
INTERFACE_RE = re.compile(r"^[^ /]+/[^ ]+$")
CI_RESULTS = {"pass", "fail", "unknown", "running"}
KEY_RE = re.compile(
    r"^(device|interface|site|service|test|control|incident|change):[^ ].*$"
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
    "relations",
    "keys",
]


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
    git = data.get("git")
    if isinstance(git, dict) and git.get("ref") == "main" and data.get("status") != "merged":
        errors.append("git.ref must be dev until merged")
    ci = data.get("ci")
    if isinstance(ci, dict):
        result = ci.get("result")
        if result is not None and result not in CI_RESULTS:
            errors.append("ci.result is not allowed")
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
            errors.append(f"{label}.rel must be depends_on, caused, or resolved_by")
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
