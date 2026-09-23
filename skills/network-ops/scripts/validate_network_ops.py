#!/usr/bin/env python3
"""Validate state/network-ops.json. Never contacts GitHub."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

SCHEMA = "network-ops-state/v2"
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
KINDS = {"missing_config", "test_bug", "other"}
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
    "change",
    "git",
    "ci",
    "pr",
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
    finding = data.get("finding")
    if finding is not None:
        if not isinstance(finding, dict):
            errors.append("finding must be an object")
        elif finding.get("kind") not in KINDS:
            errors.append("finding.kind is not allowed")
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
    if isinstance(change, dict):
        expected_keys = set()
        for device in change.get("devices") or []:
            if isinstance(device, str):
                expected_keys.add(f"device:{device}")
        if set(keys) != expected_keys:
            errors.append("keys must equal the deduplicated union of change.devices")
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"ok": True, "path": path}))


if __name__ == "__main__":
    main()
