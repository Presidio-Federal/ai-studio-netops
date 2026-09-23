#!/usr/bin/env python3
"""Validate testing state/run files and append-only compliance visits. Never contacts GitHub."""

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
KEY_TYPES = {
    "device",
    "interface",
    "site",
    "service",
    "test",
    "control",
    "incident",
    "change",
}
KEY_RE = re.compile(
    r"^(device|interface|site|service|test|control|incident|change):[^ ].*$"
)
UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"
)
HOST_ABS_RE = re.compile(r"^([A-Za-z]:[\\/]|/Users/|/home/|/tmp/|/var/|/etc/)")
RUN_PATH_RE = re.compile(
    r"^operational/testing/("
    r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z"  # 2026-08-21T19-56-18Z
    r"|\d{8}T\d{6}Z"  # legacy 20260825T172855Z
    r")\.json$"
)
VISIT_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")

RUN_REQUIRED = [
    "keys",
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
    "keys",
    "schema",
    "updated_at",
    "source_agent",
    "status",
    "headline",
    "run",
    "risk",
    "latest",
]
COMPLIANCE_REQUIRED = [
    "keys",
    "schema",
    "visit_id",
    "checked_at",
    "source_agent",
    "status",
    "headline",
    "next_action",
    "github_run_id",
    "github_run_url",
    "environment",
    "scope",
    "results",
    "risk",
    "metrics",
    "vs_prior",
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
            f"{name} must match operational/testing/YYYY-MM-DDTHH-MM-SSZ.json "
            f"(e.g. operational/testing/2026-08-21T19-56-18Z.json)"
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


def validate_result_keys(item: dict[str, Any], name: str, errors: Errors) -> None:
    keys = item.get("keys")
    if not isinstance(keys, list) or len(keys) < 2:
        errors.add(f"{name}.keys must contain at least test and device keys")
        return
    if len(keys) != len(set(keys)):
        errors.add(f"{name}.keys must not contain duplicates")
    for key in keys:
        if not isinstance(key, str) or not KEY_RE.match(key):
            errors.add(f"{name}.keys has invalid type:name key: {key}")
    check = item.get("check")
    device = item.get("device")
    check_id = check.rsplit("/", 1)[-1] if isinstance(check, str) else None
    if check_id and f"test:{check_id}" not in keys:
        errors.add(f"{name}.keys missing canonical test:{check_id}")
    if isinstance(device, str) and f"device:{device}" not in keys:
        errors.add(f"{name}.keys missing device:{device}")


def validate_top_level_keys(obj: dict[str, Any], errors: Errors) -> None:
    keys = obj.get("keys")
    if not isinstance(keys, list):
        errors.add("keys must be an array")
        return
    if len(keys) != len(set(keys)):
        errors.add("keys must not contain duplicates")
    for key in keys:
        if not isinstance(key, str) or not KEY_RE.match(key):
            errors.add(f"keys has invalid canonical key: {key}")

    nested: list[str] = []

    def collect(value: Any, top: bool = False) -> None:
        if isinstance(value, dict):
            if not top and isinstance(value.get("keys"), list):
                nested.extend(key for key in value["keys"] if isinstance(key, str))
            entity_type = value.get("type")
            entity_name = value.get("name")
            if entity_type in KEY_TYPES and isinstance(entity_name, str):
                nested.append(f"{entity_type}:{entity_name}")
            device = value.get("device")
            if isinstance(device, str):
                nested.append(f"device:{device}")
            for field in ("devices_requested", "devices_scanned", "failing_devices"):
                entities = value.get(field)
                if isinstance(entities, list):
                    nested.extend(
                        f"device:{name}" for name in entities if isinstance(name, str)
                    )
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(obj, top=True)
    expected = list(dict.fromkeys(nested))
    if set(keys) != set(expected):
        errors.add("keys must be the deduplicated union of nested row keys")


def validate_run(data: Any, errors: Errors) -> None:
    obj = require_object(data, "run", errors)
    if obj is None:
        return
    require_fields(obj, RUN_REQUIRED, "run", errors)
    validate_top_level_keys(obj, errors)
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
            validate_result_keys(item, "results.ran entry", errors)
        for item in results.get("not_applicable") or []:
            if not isinstance(item, dict):
                errors.add("results.not_applicable entries must be objects")
                continue
            validate_result_keys(item, "results.not_applicable entry", errors)
    if obj.get("status") == "PASS" and (results or {}).get("gaps"):
        errors.add("status PASS cannot have a non-empty results.gaps list")
    risk = require_object(obj.get("risk"), "risk", errors) if "risk" in obj else None
    if risk is not None:
        validate_risk_block(risk, errors, require_why=True)
    if "local_path" in obj:
        validate_run_path(obj.get("local_path"), "local_path", errors)
        local = normalize_workspace_path(str(obj.get("local_path") or ""))
        if not local.startswith("operational/testing/"):
            errors.add("general testing run local_path must stay under operational/testing/")


def validate_compliance(data: Any, errors: Errors) -> None:
    obj = require_object(data, "compliance visit", errors)
    if obj is None:
        return
    require_fields(obj, COMPLIANCE_REQUIRED, "compliance visit", errors)
    validate_top_level_keys(obj, errors)
    if obj.get("schema") != "compliance-test-visit/v1":
        errors.add("compliance visit schema must be compliance-test-visit/v1")
    if obj.get("source_agent") != SOURCE_AGENT:
        errors.add(f"source_agent must be {SOURCE_AGENT}")
    visit_id = obj.get("visit_id")
    if not isinstance(visit_id, str) or not VISIT_ID_RE.match(visit_id):
        errors.add("visit_id must be YYYY-MM-DDTHH-MM-SSZ")
    if "checked_at" in obj:
        validate_utc(obj.get("checked_at"), "checked_at", errors)
    if obj.get("status") not in RUN_STATUSES:
        errors.add(f"status must be one of {sorted(RUN_STATUSES)}")
    scope = require_object(obj.get("scope"), "scope", errors) if "scope" in obj else None
    suites = (scope or {}).get("suites")
    if not isinstance(suites, list) or "compliance" not in suites:
        errors.add("compliance visit scope.suites must include compliance")
    results = require_object(obj.get("results"), "results", errors) if "results" in obj else None
    if results is not None:
        counts = require_object(results.get("counts_ran"), "results.counts_ran", errors)
        if counts is not None:
            for field in ("pass", "fail", "error", "skip"):
                if not isinstance(counts.get(field), int):
                    errors.add(f"results.counts_ran.{field} must be an integer")
        for bucket in ("ran", "not_applicable"):
            for item in results.get(bucket) or []:
                if not isinstance(item, dict):
                    errors.add(f"results.{bucket} entries must be objects")
                    continue
                validate_result_keys(item, f"results.{bucket} entry", errors)
    metrics = require_object(obj.get("metrics"), "metrics", errors) if "metrics" in obj else None
    if metrics is not None:
        for field in (
            "pass",
            "fail",
            "error",
            "skip",
            "not_applicable",
            "verified_tests",
            "failing_tests",
            "skipped_tests",
        ):
            if not isinstance(metrics.get(field), int):
                errors.add(f"metrics.{field} must be an integer")
    prior = require_object(obj.get("vs_prior"), "vs_prior", errors) if "vs_prior" in obj else None
    if prior is not None and prior.get("delta") not in {"first", "unchanged", "worse", "better", "mixed"}:
        errors.add("vs_prior.delta is invalid")
    risk = require_object(obj.get("risk"), "risk", errors) if "risk" in obj else None
    if risk is not None:
        validate_risk_block(risk, errors, require_why=True)


def validate_state(data: Any, errors: Errors, file_path: str = "") -> None:
    obj = require_object(data, "state", errors)
    if obj is None:
        return
    require_fields(obj, STATE_REQUIRED, "state", errors)
    validate_top_level_keys(obj, errors)
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
    latest = normalize_workspace_path(str(obj.get("latest") or ""))
    path_norm = file_path.replace("\\", "/")
    is_testing_state = path_norm.endswith("state/testing.json")
    if is_testing_state and not latest.startswith("operational/testing/"):
        errors.add("state/testing.json latest must be operational/testing/<UTC>.json")


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in {"run", "state", "compliance"}:
        print("usage: validate_testing.py run|state|compliance <file>", file=sys.stderr)
        return 2
    kind, path = argv[1], argv[2]
    errors = Errors()
    data = load_json(path, errors)
    if data is not None:
        if kind == "run":
            validate_run(data, errors)
        elif kind == "compliance":
            validate_compliance(data, errors)
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
