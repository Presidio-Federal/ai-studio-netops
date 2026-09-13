#!/usr/bin/env python3
"""Validate state/network-ops.json. Never contacts GitHub."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

SCHEMA = "network-ops-state/v1"
SOURCE_AGENT = "network-ops"
STATUSES = {
    "recommended",
    "committed",
    "ci_failed",
    "merged",
    "blocked",
    "failed",
}
MODES = {"recommend", "implement"}
KINDS = {"missing_config", "test_bug", "other"}
CI_RESULTS = {"pass", "fail", "unknown", "running"}
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
    git = data.get("git")
    if isinstance(git, dict) and git.get("ref") == "main" and data.get("status") != "merged":
        errors.append("git.ref must be dev until merged")
    ci = data.get("ci")
    if isinstance(ci, dict):
        result = ci.get("result")
        if result is not None and result not in CI_RESULTS:
            errors.append("ci.result is not allowed")
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"ok": True, "path": path}))


if __name__ == "__main__":
    main()
