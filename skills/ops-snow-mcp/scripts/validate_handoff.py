#!/usr/bin/env python3
"""Validate ServiceNow workspace request and result JSON. Never contacts ServiceNow."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from typing import Any

REQUEST_SCHEMA = "servicenow-request/v1"
RESULT_SCHEMA = "servicenow-result/v1"

OPERATIONS = {
    "find_incident",
    "get_incident",
    "upsert_incident",
    "append_incident_work_notes",
    "resolve_incident",
    "find_change",
    "get_change",
    "upsert_change",
    "append_change_validation",
    "append_change_deployment",
    "close_change",
}

MUTATION_OPS = {
    "upsert_incident",
    "append_incident_work_notes",
    "resolve_incident",
    "upsert_change",
    "append_change_validation",
    "append_change_deployment",
    "close_change",
}

INCIDENT_OPS = {
    "find_incident",
    "get_incident",
    "upsert_incident",
    "append_incident_work_notes",
    "resolve_incident",
}

CHANGE_OPS = {
    "find_change",
    "get_change",
    "upsert_change",
    "append_change_validation",
    "append_change_deployment",
    "close_change",
}

AUTH_MODES = {"human", "policy", "conversation"}
POLICIES = {
    "confirmed-network-incident-v1": {"upsert_incident", "append_incident_work_notes"},
    "append-validation-result-v1": {"append_change_validation"},
    "append-deployment-result-v1": {"append_change_deployment"},
    "close-resolved-incident-v1": {"resolve_incident"},
}
POLICY_FORBIDDEN_OPS = {"upsert_change", "close_change"}

REQUEST_REQUIRED = [
    "schema",
    "request_id",
    "created_at",
    "requested_by",
    "operation",
    "correlation_id",
    "idempotency_key",
    "source_refs",
    "authorization",
    "record",
]
RESULT_REQUIRED = [
    "schema",
    "request_id",
    "correlation_id",
    "completed_at",
    "status",
    "action",
    "record",
    "verification",
    "source_refs",
    "error",
]
RESULT_STATUSES = {"succeeded", "failed", "needs_approval"}
RESULT_ACTIONS = {"found", "created", "updated", "assigned", "drafted", "recommended", "noop", "failed"}
RECORD_TYPES = {"incident", "change"}
AUTH_FIELDS = ("mode", "policy", "authorized_by", "authorized_at")
RESULT_RECORD_FIELDS = ("type", "number", "sys_id", "state", "updated_at", "url")
VERIFY_FIELDS = ("read_back", "matched_request", "verified_fields")

UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"
)
HOST_ABS_RE = re.compile(r"^([A-Za-z]:[\\/]|/Users/|/home/|/tmp/|/var/|/etc/)")


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
    if not isinstance(value, str) or not value:
        errors.add(f"{name} must be a non-empty ISO-8601 UTC timestamp")
        return
    if not UTC_RE.match(value):
        errors.add(f"{name} must be ISO-8601 UTC (Z or +00:00): {value}")
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.add(f"{name} is not a valid timestamp: {value}")


def normalize_workspace_path(path: str) -> str:
    """Strip sandbox prefixes other agents often add. Remainder must be relative."""
    value = path.strip()
    if value.startswith("/workspace/"):
        value = value[len("/workspace/") :]
    elif value.startswith("workspace/"):
        value = value[len("workspace/") :]
    return value


def validate_workspace_path(value: Any, name: str, errors: Errors) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.add(f"{name} must be a non-empty workspace-relative path")
        return
    path = normalize_workspace_path(value)
    if path == "Internal directory":
        errors.add(f"{name} must not be 'Internal directory'")
        return
    if path.startswith("/") or HOST_ABS_RE.match(path):
        errors.add(f"{name} must be workspace-relative, not an absolute path: {path}")
        return
    if not path or path != path.lstrip("/"):
        errors.add(f"{name} must be workspace-relative: {value}")


def validate_source_refs(value: Any, errors: Errors) -> None:
    if not isinstance(value, list):
        errors.add("source_refs must be an array")
        return
    for index, item in enumerate(value):
        validate_workspace_path(item, f"source_refs[{index}]", errors)


def validate_authorization(auth: Any, operation: str, errors: Errors) -> None:
    obj = require_object(auth, "authorization", errors)
    if obj is None:
        return
    for field in AUTH_FIELDS:
        if field not in obj:
            errors.add(f"authorization missing field: {field}")
    mode = obj.get("mode")
    if mode not in AUTH_MODES:
        errors.add(f"authorization.mode must be one of {sorted(AUTH_MODES)}")
        return
    policy = obj.get("policy")
    authorized_by = obj.get("authorized_by")
    authorized_at = obj.get("authorized_at")
    if authorized_at is not None:
        validate_utc(authorized_at, "authorization.authorized_at", errors)
    if operation not in MUTATION_OPS:
        return
    if mode == "human":
        if not authorized_by:
            errors.add("human authorization requires authorized_by")
        if not authorized_at:
            errors.add("human authorization requires authorized_at")
    elif mode == "policy":
        if not isinstance(policy, str) or policy not in POLICIES:
            errors.add("policy authorization requires a recognized policy")
            return
        if operation in POLICY_FORBIDDEN_OPS:
            errors.add(f"policy authorization cannot authorize {operation}")
        elif operation not in POLICIES[policy]:
            errors.add(f"policy {policy} does not authorize {operation}")
    elif mode == "conversation":
        if policy not in (None,):
            errors.add("conversation authorization must set policy to null")


def validate_request_record(record: Any, operation: str, errors: Errors) -> None:
    obj = require_object(record, "record", errors)
    if obj is None:
        return
    if obj.get("type") not in RECORD_TYPES:
        errors.add("record.type must be incident or change")
    expected = "incident" if operation in INCIDENT_OPS else "change"
    if obj.get("type") not in (None, expected) and operation in OPERATIONS:
        errors.add(f"record.type must be {expected} for {operation}")
    if operation in {"get_incident", "get_change"}:
        if not obj.get("number") and not obj.get("sys_id"):
            errors.add(f"{operation} requires record.number or record.sys_id")
    if operation == "resolve_incident" and not obj.get("close_notes"):
        errors.add("resolve_incident requires record.close_notes")
    if operation == "close_change" and not obj.get("work_notes") and not obj.get("close_notes"):
        errors.add("close_change requires close notes in record.work_notes")
    if operation in {"upsert_incident", "append_incident_work_notes", "resolve_incident"}:
        for field in ("short_description", "urgency", "impact", "category"):
            if operation == "append_incident_work_notes" and field != "short_description":
                continue
            if operation == "upsert_incident" and not obj.get(field):
                errors.add(f"upsert_incident requires record.{field}")
        if operation == "upsert_incident" and not (obj.get("description") or obj.get("summary")):
            errors.add("upsert_incident requires record.summary or record.description")
        if operation == "append_incident_work_notes" and not obj.get("work_notes"):
            errors.add("append_incident_work_notes requires record.work_notes")
    if operation == "upsert_change":
        for field in (
            "short_description",
            "objective",
            "justification",
            "implementation_plan",
            "risk_impact_analysis",
            "test_plan",
            "backout_plan",
        ):
            if not obj.get(field):
                errors.add(f"upsert_change requires record.{field}")


def validate_request(data: Any, errors: Errors) -> None:
    obj = require_object(data, "request", errors)
    if obj is None:
        return
    require_fields(obj, REQUEST_REQUIRED, "request", errors)
    if obj.get("schema") != REQUEST_SCHEMA:
        errors.add(f"schema must be {REQUEST_SCHEMA}")
    for field in ("request_id", "requested_by", "correlation_id", "idempotency_key"):
        if field in obj and (not isinstance(obj[field], str) or not obj[field].strip()):
            errors.add(f"{field} must be a non-empty string")
    if "created_at" in obj:
        validate_utc(obj.get("created_at"), "created_at", errors)
    operation = obj.get("operation")
    if operation not in OPERATIONS:
        errors.add(f"unsupported operation: {operation}")
        operation = ""
    if "source_refs" in obj:
        validate_source_refs(obj.get("source_refs"), errors)
    if "authorization" in obj:
        validate_authorization(obj.get("authorization"), operation, errors)
    if "record" in obj and operation:
        validate_request_record(obj.get("record"), operation, errors)


def validate_result_url(value: Any, errors: Errors) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        errors.add("record.url must be null or a non-empty string")
        return
    if value.startswith("/") or value.startswith("workspace/") or "/workspace/" in value:
        errors.add("record.url must not be a workspace or filesystem path")
        return
    if not value.startswith("https://"):
        errors.add("record.url must be an https URL when present")


def validate_result(data: Any, errors: Errors) -> None:
    obj = require_object(data, "result", errors)
    if obj is None:
        return
    require_fields(obj, RESULT_REQUIRED, "result", errors)
    if obj.get("schema") != RESULT_SCHEMA:
        errors.add(f"schema must be {RESULT_SCHEMA}")
    for field in ("request_id", "correlation_id"):
        if field in obj and (not isinstance(obj[field], str) or not obj[field].strip()):
            errors.add(f"{field} must be a non-empty string")
    if "completed_at" in obj:
        validate_utc(obj.get("completed_at"), "completed_at", errors)
    status = obj.get("status")
    action = obj.get("action")
    if status not in RESULT_STATUSES:
        errors.add(f"status must be one of {sorted(RESULT_STATUSES)}")
    if action not in RESULT_ACTIONS:
        errors.add(f"action must be one of {sorted(RESULT_ACTIONS)}")
    if status == "needs_approval" and action != "noop":
        errors.add("needs_approval results must use action=noop")
    if status == "failed":
        if action not in {"failed", "noop"}:
            errors.add("failed results must use action=failed or action=noop")
        err = obj.get("error")
        if not err:
            errors.add("failed results must include an error object or message")
        elif isinstance(err, dict) and not err.get("message") and not err.get("code"):
            errors.add("error object must include code or message")
    if "source_refs" in obj:
        validate_source_refs(obj.get("source_refs"), errors)
    record = require_object(obj.get("record"), "record", errors) if "record" in obj else None
    if record is not None:
        require_fields(record, list(RESULT_RECORD_FIELDS), "record", errors)
        if record.get("type") not in RECORD_TYPES:
            errors.add("record.type must be incident or change")
        validate_result_url(record.get("url"), errors)
    verification = (
        require_object(obj.get("verification"), "verification", errors)
        if "verification" in obj
        else None
    )
    if verification is not None:
        require_fields(verification, list(VERIFY_FIELDS), "verification", errors)
        if not isinstance(verification.get("read_back"), bool):
            errors.add("verification.read_back must be a boolean")
        if not isinstance(verification.get("matched_request"), bool):
            errors.add("verification.matched_request must be a boolean")
        if not isinstance(verification.get("verified_fields"), list):
            errors.add("verification.verified_fields must be an array")
    mutation = status == "succeeded" and action in {"created", "updated"}
    if mutation:
        if not verification or verification.get("read_back") is not True:
            errors.add("successful mutation requires verification.read_back=true")
        if record is None or not record.get("number") or not record.get("sys_id"):
            errors.add("successful mutation requires record.number and record.sys_id")


STATE_SCHEMA = "servicenow-state/v1"
ACTIVE_SCHEMA = "servicenow-cases-active/v1"
INDEX_SCHEMA = "servicenow-cases-index/v1"
BOARD_STATUSES = {"clear", "open", "unknown"}
BOARD_ACTIONS = {"created", "updated", "assigned", "drafted", "recommended", "noop", "needs_approval", "failed", "board"}
TRENDS = {"first", "unchanged", "worse", "better"}
STATE_REQUIRED = [
    "schema",
    "updated_at",
    "source_agent",
    "status",
    "headline",
    "run_count",
    "first_run_at",
    "last_run_at",
    "last_action",
    "open",
    "trend",
    "history",
    "cases",
]
OPEN_REQUIRED = ["incidents", "changes", "devices"]
HISTORY_REQUIRED = ["at", "action", "status", "headline", "open_incidents", "open_changes"]
ACTIVE_CASE_REQUIRED = ["number", "type", "state", "headline", "devices", "source_refs", "updated_at"]
INDEX_CASE_REQUIRED = ["number", "type", "state", "headline", "updated_at"]


def validate_device_list(value: Any, name: str, errors: Errors) -> None:
    if not isinstance(value, list) or not all(isinstance(i, str) and i.strip() for i in value):
        errors.add(f"{name} must be an array of strings")


def validate_state(data: Any, errors: Errors) -> None:
    obj = require_object(data, "state", errors)
    if obj is None:
        return
    require_fields(obj, STATE_REQUIRED, "state", errors)
    if obj.get("schema") != STATE_SCHEMA:
        errors.add(f"schema must be {STATE_SCHEMA}")
    if obj.get("source_agent") != "servicenow":
        errors.add("source_agent must be servicenow")
    if obj.get("status") not in BOARD_STATUSES:
        errors.add(f"status must be one of {sorted(BOARD_STATUSES)}")
    if obj.get("last_action") not in BOARD_ACTIONS:
        errors.add(f"last_action must be one of {sorted(BOARD_ACTIONS)}")
    if not isinstance(obj.get("headline"), str) or not obj.get("headline", "").strip():
        errors.add("headline must be a non-empty string")
    for field in ("updated_at", "first_run_at", "last_run_at"):
        if field in obj:
            validate_utc(obj.get(field), field, errors)
    if "run_count" in obj and (not isinstance(obj.get("run_count"), int) or obj["run_count"] < 1):
        errors.add("run_count must be an integer >= 1")
    opened = require_object(obj.get("open"), "open", errors) if "open" in obj else None
    if opened is not None:
        require_fields(opened, OPEN_REQUIRED, "open", errors)
        for field in ("incidents", "changes"):
            if field in opened and (not isinstance(opened[field], int) or opened[field] < 0):
                errors.add(f"open.{field} must be an integer >= 0")
        if "devices" in opened:
            validate_device_list(opened.get("devices"), "open.devices", errors)
    trend = require_object(obj.get("trend"), "trend", errors) if "trend" in obj else None
    if trend is not None:
        if trend.get("vs_prior") not in TRENDS:
            errors.add(f"trend.vs_prior must be one of {sorted(TRENDS)}")
        if not isinstance(trend.get("note"), str) or not trend.get("note", "").strip():
            errors.add("trend.note must be a non-empty string")
    history = obj.get("history")
    if not isinstance(history, list) or not history or len(history) > 20:
        errors.add("history must be an array of 1–20 rows, newest first")
    elif isinstance(history, list):
        for i, row in enumerate(history):
            name = f"history[{i}]"
            rec = require_object(row, name, errors)
            if rec is None:
                continue
            require_fields(rec, HISTORY_REQUIRED, name, errors)
            if rec.get("action") not in BOARD_ACTIONS:
                errors.add(f"{name}.action must be one of {sorted(BOARD_ACTIONS)}")
            if rec.get("status") not in BOARD_STATUSES:
                errors.add(f"{name}.status must be one of {sorted(BOARD_STATUSES)}")
            if "at" in rec:
                validate_utc(rec.get("at"), f"{name}.at", errors)
    cases = require_object(obj.get("cases"), "cases", errors) if "cases" in obj else None
    if cases is not None:
        if cases.get("active") != "servicenow/cases/active.json":
            errors.add("cases.active must be servicenow/cases/active.json")
        if cases.get("index") != "servicenow/cases/index.json":
            errors.add("cases.index must be servicenow/cases/index.json")


def validate_active(data: Any, errors: Errors) -> None:
    obj = require_object(data, "active", errors)
    if obj is None:
        return
    require_fields(
        obj, ["schema", "updated_at", "source_agent", "status", "headline", "cases"], "active", errors
    )
    if obj.get("schema") != ACTIVE_SCHEMA:
        errors.add(f"schema must be {ACTIVE_SCHEMA}")
    if obj.get("status") not in BOARD_STATUSES:
        errors.add(f"status must be one of {sorted(BOARD_STATUSES)}")
    if "updated_at" in obj:
        validate_utc(obj.get("updated_at"), "updated_at", errors)
    cases = obj.get("cases")
    if not isinstance(cases, list) or len(cases) > 5:
        errors.add("cases must be an array of at most 5")
        return
    for i, row in enumerate(cases):
        name = f"cases[{i}]"
        rec = require_object(row, name, errors)
        if rec is None:
            continue
        require_fields(rec, ACTIVE_CASE_REQUIRED, name, errors)
        if rec.get("type") not in RECORD_TYPES:
            errors.add(f"{name}.type must be incident or change")
        validate_device_list(rec.get("devices"), f"{name}.devices", errors)
        if not isinstance(rec.get("source_refs"), list):
            errors.add(f"{name}.source_refs must be an array")
        if "updated_at" in rec:
            validate_utc(rec.get("updated_at"), f"{name}.updated_at", errors)


def validate_index(data: Any, errors: Errors) -> None:
    obj = require_object(data, "index", errors)
    if obj is None:
        return
    require_fields(obj, ["schema", "updated_at", "source_agent", "cases"], "index", errors)
    if obj.get("schema") != INDEX_SCHEMA:
        errors.add(f"schema must be {INDEX_SCHEMA}")
    if "updated_at" in obj:
        validate_utc(obj.get("updated_at"), "updated_at", errors)
    cases = obj.get("cases")
    if not isinstance(cases, list):
        errors.add("cases must be an array")
        return
    for i, row in enumerate(cases):
        name = f"cases[{i}]"
        rec = require_object(row, name, errors)
        if rec is None:
            continue
        require_fields(rec, INDEX_CASE_REQUIRED, name, errors)
        if rec.get("type") not in RECORD_TYPES:
            errors.add(f"{name}.type must be incident or change")
        if "updated_at" in rec:
            validate_utc(rec.get("updated_at"), f"{name}.updated_at", errors)


def main(argv: list[str]) -> int:
    allowed = {"request", "result", "state", "active", "index"}
    if len(argv) != 3 or argv[1] not in allowed:
        print("usage: validate_handoff.py request|result|state|active|index <file>", file=sys.stderr)
        return 2
    kind, path = argv[1], argv[2]
    errors = Errors()
    data = load_json(path, errors)
    if data is not None:
        if kind == "request":
            validate_request(data, errors)
        elif kind == "result":
            validate_result(data, errors)
        elif kind == "state":
            validate_state(data, errors)
        elif kind == "active":
            validate_active(data, errors)
        else:
            validate_index(data, errors)
    if errors.ok():
        print(f"ok: {kind} {path}")
        return 0
    print(f"invalid {kind}: {path}", file=sys.stderr)
    for item in errors.items:
        print(f"- {item}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
