#!/usr/bin/env python3
"""Validate testing/YYYY-MM-DDTHH-MM-SSZ.json, state/testing.json, and compliance copies. Never contacts GitHub."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from typing import Any

STATE_SCHEMA = "testing-state/v1"
SOURCE_AGENT = "compliance-test"
RUN_STATUSES = {"PASS", "FAIL", "MIXED", "UNKNOWN"}
STATE_STATUSES = {"PASS", "FAIL", "MIXED", "UNKNOWN", "running"}
RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
PUSH = {"proceed", "proceed_with_caution", "do_not_push", "unknown"}
CHECK_STATUSES = {"PASS", "FAIL", "ERROR", "SKIP"}
UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"
)
HOST_ABS_RE = re.compile(r"^([A-Za-z]:[\\/]|/Users/|/home/|/tmp/|/var/|/etc/)")
RUN_PATH_RE = re.compile(
    r"^(testing|compliance)/("
    r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z"  # 2026-08-21T19-56-18Z
    r"|\d{8}T\d{6}Z"  # legacy 20260825T172855Z
    r")\.json$"
)

RUN_REQUIRED = [
    "version",
    "updated_at",
    "source_agent",
    "status",
    "headline",
    "next_action",
    "github_run_id",
    "environment",
    "scope",
    "results",
    "risk",
]
STATE_REQUIRED = [
    "schema",
    "updated_at",
    "source_agent",
    "status",
    "headline",
    "run",
    "risk",
    "latest",
]


class Errors:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, message: str) -> None:
        self.items.append(message)

    def ok(self) -> bool:
        return not self.items


def load_json(path: str, errors: Errors) -> Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        errors.add(f"file not found: {path}")
    except json.JSONDecodeError as exc:
        errors.add(f"invalid JSON: {exc}")
    return None


def require_object(value: Any, name: str, errors: Errors) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.add(f"{name} must be an object")
        return None
    return value


def require_fields(obj: dict[str, Any], fields: list[str], name: str, errors: Errors) -> None:
    for field in fields:
        if field not in obj:
            errors.add(f"{name} missing required field: {field}")


def validate_utc(value: Any, name: str, errors: Errors) -> None:
    if not isinstance(value, str) or not UTC_RE.match(value):
        errors.add(f"{name} must be ISO-8601 UTC: {value}")
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.add(f"{name} is not a valid timestamp: {value}")


def normalize_workspace_path(path: str) -> str:
    value = path.strip()
    if value.startswith("/workspace/"):
        value = value[len("/workspace/") :]
    elif value.startswith("workspace/"):
        value = value[len("workspace/") :]
    return value


def validate_run_path(value: Any, name: str, errors: Errors) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.add(f"{name} must be a non-empty workspace-relative path")
        return
    path = normalize_workspace_path(value)
    if value != path or path == "Internal directory":
        errors.add(f"{name} must be workspace-relative, not {value}")
        return
    if path.startswith("/") or HOST_ABS_RE.match(path):
        errors.add(f"{name} must not be an absolute path: {path}")
        return
    if not RUN_PATH_RE.match(path):
        errors.add(
            f"{name} must match testing/YYYY-MM-DDTHH-MM-SSZ.json "
            f"or compliance/YYYY-MM-DDTHH-MM-SSZ.json (e.g. 2026-08-21T19-56-18Z.json)"
        )


def validate_risk_block(risk: dict[str, Any], errors: Errors, require_why: bool) -> None:
    if risk.get("level") not in RISK_LEVELS:
        errors.add(f"risk.level must be one of {sorted(RISK_LEVELS)}")
    push = risk.get("push_to_prod")
    if not isinstance(push, str) or not push.strip():
        errors.add("risk.push_to_prod must be a non-empty string")
    elif push not in PUSH:
        errors.add(f"risk.push_to_prod must be one of {sorted(PUSH)}")
    if require_why:
        if not isinstance(risk.get("verdict"), str) or not risk.get("verdict", "").strip():
            errors.add("risk.verdict must be a non-empty string")
        why = risk.get("why")
        if not isinstance(why, list) or not why:
            errors.add("risk.why must be a non-empty array of evidence strings")


def validate_run(data: Any, errors: Errors) -> None:
    obj = require_object(data, "run", errors)
    if obj is None:
        return
    require_fields(obj, RUN_REQUIRED, "run", errors)
    if obj.get("version") != 1:
        errors.add("version must be 1")
    if obj.get("source_agent") != SOURCE_AGENT:
        errors.add(f"source_agent must be {SOURCE_AGENT}")
    if obj.get("status") not in RUN_STATUSES:
        errors.add(f"status must be one of {sorted(RUN_STATUSES)}")
    if "updated_at" in obj:
        validate_utc(obj.get("updated_at"), "updated_at", errors)
    if not isinstance(obj.get("headline"), str) or not obj.get("headline", "").strip():
        errors.add("headline must be a non-empty string")
    env = require_object(obj.get("environment"), "environment", errors) if "environment" in obj else None
    if env is not None and env.get("live_lab") not in {"dev", "prod"}:
        errors.add("environment.live_lab must be dev or prod")
    scope = require_object(obj.get("scope"), "scope", errors) if "scope" in obj else None
    if scope is not None and not isinstance(scope.get("suites"), list):
        errors.add("scope.suites must be an array")
    results = require_object(obj.get("results"), "results", errors) if "results" in obj else None
    if results is not None:
        counts = require_object(results.get("counts_ran"), "results.counts_ran", errors)
        if counts is not None:
            for field in ("pass", "fail", "error", "skip"):
                if not isinstance(counts.get(field), int):
                    errors.add(f"results.counts_ran.{field} must be an integer")
        for item in results.get("ran") or []:
            if not isinstance(item, dict):
                errors.add("results.ran entries must be objects")
                continue
            if item.get("status") not in CHECK_STATUSES:
                errors.add(f"results.ran.status must be one of {sorted(CHECK_STATUSES)}")
    if obj.get("status") == "PASS" and (results or {}).get("gaps"):
        errors.add("status PASS cannot have a non-empty results.gaps list")
    risk = require_object(obj.get("risk"), "risk", errors) if "risk" in obj else None
    if risk is not None:
        validate_risk_block(risk, errors, require_why=True)
    if "local_path" in obj:
        validate_run_path(obj.get("local_path"), "local_path", errors)
        local = normalize_workspace_path(str(obj.get("local_path") or ""))
        suites = (scope or {}).get("suites") if isinstance(scope, dict) else None
        suite_list = suites if isinstance(suites, list) else []
        if local.startswith("compliance/") and "compliance" not in suite_list:
            errors.add("compliance/<UTC>.json requires scope.suites to include compliance")


def _suites(obj: dict[str, Any]) -> list[Any]:
    run = obj.get("run")
    if not isinstance(run, dict):
        return []
    suites = run.get("suites")
    return suites if isinstance(suites, list) else []


def validate_state(data: Any, errors: Errors, file_path: str = "") -> None:
    obj = require_object(data, "state", errors)
    if obj is None:
        return
    require_fields(obj, STATE_REQUIRED, "state", errors)
    if obj.get("schema") != STATE_SCHEMA:
        errors.add(f"schema must be {STATE_SCHEMA}")
    if obj.get("source_agent") != SOURCE_AGENT:
        errors.add(f"source_agent must be {SOURCE_AGENT}")
    if obj.get("status") not in STATE_STATUSES:
        errors.add(f"status must be one of {sorted(STATE_STATUSES)}")
    if "updated_at" in obj:
        validate_utc(obj.get("updated_at"), "updated_at", errors)
    if not isinstance(obj.get("headline"), str) or not obj.get("headline", "").strip():
        errors.add("headline must be a non-empty string")
    if "latest" in obj:
        validate_run_path(obj.get("latest"), "latest", errors)
    risk = require_object(obj.get("risk"), "risk", errors) if "risk" in obj else None
    if risk is not None:
        validate_risk_block(risk, errors, require_why=False)
    suites = _suites(obj)
    latest = normalize_workspace_path(str(obj.get("latest") or ""))
    path_norm = file_path.replace("\\", "/")
    is_compliance_state = path_norm.endswith("state/compliance.json")
    is_testing_state = path_norm.endswith("state/testing.json")
    if is_compliance_state and "compliance" not in suites:
        errors.add("state/compliance.json requires run.suites to include compliance")
    if latest.startswith("compliance/") and "compliance" not in suites:
        errors.add("latest under compliance/ requires run.suites to include compliance")
    if is_compliance_state and latest and not latest.startswith("compliance/"):
        errors.add("state/compliance.json latest must be compliance/<UTC>.json")
    if is_testing_state and latest.startswith("compliance/"):
        errors.add("state/testing.json latest must be testing/<UTC>.json")


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in {"run", "state"}:
        print("usage: validate_testing.py run|state <file>", file=sys.stderr)
        return 2
    kind, path = argv[1], argv[2]
    errors = Errors()
    data = load_json(path, errors)
    if data is not None:
        if kind == "run":
            validate_run(data, errors)
        else:
            validate_state(data, errors, file_path=path)
    if errors.ok():
        print(f"ok: {kind} {path}")
        return 0
    print(f"invalid {kind}: {path}", file=sys.stderr)
    for item in errors.items:
        print(f"- {item}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
