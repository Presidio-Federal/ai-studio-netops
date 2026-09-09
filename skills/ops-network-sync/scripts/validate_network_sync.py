#!/usr/bin/env python3
"""Validate Ops Network Sync inventory and state. Never contacts CML or GitHub."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any

INVENTORY_SCHEMA = "network-access-inventory/v3"
STATE_SCHEMA = "network-sync-state/v2"
SOURCE_AGENT = "ops-network-sync"
ENVIRONMENTS = {"prod", "dev"}
INVENTORY_STATUSES = {"complete", "partial"}
COVERAGE_PUBLISHED = {"complete", "partial"}
COVERAGE_ATTEMPT = {"complete", "partial", "unavailable"}
ATTEMPT_STATUSES = {"complete", "partial", "failed", "unavailable"}
STATE_STATUSES = {"ok", "gaps", "failed", "partial", "unknown"}
OPERATIONS = {
    "onboard",
    "collect-prod",
    "collect-dev",
    "sync-prod",
    "sync-dev",
    "detect-drift-prod",
    "detect-drift-dev",
    "deploy-twin",
    "reconcile-dev",
    "author-check-wait",
    "status-read",
}
SOURCE_TYPES = {"cml", "document", "api", "netbox", "excel", "other"}
INFRA_SOT = {"git", "netbox"}
WORKFLOW_RESULTS: dict[str, tuple[str, str | None, set[str]]] = {
    "sync_prod": ("sync-prod.yml", "prod", {"ok", "gaps", "failed"}),
    "sync_dev": ("sync-dev.yml", "dev", {"ok", "gaps", "failed"}),
    "drift_prod": ("detect-drift.yml", "prod", {"in_sync", "drift", "failed"}),
    "drift_dev": ("detect-drift.yml", "dev", {"in_sync", "drift", "failed"}),
    "deploy_twin": ("deploy-twin.yml", None, {"deployed", "gaps", "failed"}),
    "reconcile_dev": ("reconcile-dev.yml", "dev", {"in_sync", "synced", "partial", "failed"}),
}
SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential)$",
    re.I,
)
UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"
)
SNAPSHOT_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")
HOST_ABS_RE = re.compile(r"^([A-Za-z]:[\\/]|/Users/|/home/|/tmp/|/var/|/etc/)")
INVENTORY_PATH_RE = re.compile(r"^inventory/(prod|dev)\.json$")

INVENTORY_REQUIRED = [
    "schema",
    "snapshot_id",
    "environment",
    "collected_at",
    "published_at",
    "expires_at",
    "status",
    "coverage",
    "source",
    "infra_sot",
    "lab_title",
    "netbox",
    "device_count",
    "devices",
    "links",
]
STATE_REQUIRED = [
    "schema",
    "updated_at",
    "source_agent",
    "status",
    "headline",
    "operation_id",
    "operation",
    "started_at",
    "completed_at",
    "inventories",
    "gaps",
    "next_action",
]
DEVICE_REQUIRED = [
    "name",
    "platform",
    "role",
    "tags",
    "operational_state",
    "agent_access",
    "access",
    "source_metadata",
]
COVERAGE_REQUIRED = [
    "state",
    "devices_discovered",
    "devices_inspected",
    "accessible_devices",
    "missing_device_info",
    "missing_restconf",
    "missing_ssh",
]
ATTEMPT_REQUIRED = [
    "operation_id",
    "attempted_at",
    "completed_at",
    "status",
    "headline",
]
SNAPSHOT_REQUIRED = [
    "snapshot_id",
    "path",
    "status",
    "collected_at",
    "expires_at",
    "device_count",
    "accessible_count",
    "coverage",
]
COMPLETED_RUN_REQUIRED = [
    "workflow",
    "environment",
    "result",
    "run_id",
    "html_url",
    "updated_at",
]


class Errors:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.notes: list[str] = []

    def add(self, message: str) -> None:
        self.items.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

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


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not UTC_RE.match(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_utc(value: Any, name: str, errors: Errors) -> datetime | None:
    if not isinstance(value, str) or not value:
        errors.add(f"{name} must be a non-empty ISO-8601 UTC timestamp")
        return None
    parsed = parse_utc(value)
    if parsed is None:
        errors.add(f"{name} must be ISO-8601 UTC (Z or +00:00): {value}")
        return None
    return parsed


def reject_secrets(value: Any, path: str, errors: Errors) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SECRET_KEY_RE.search(str(key)) and key != "credential_ref":
                errors.add(f"must not store credentials: {path}.{key}")
            reject_secrets(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            reject_secrets(child, f"{path}[{i}]", errors)


def validate_endpoint(value: Any, name: str, errors: Errors) -> bool:
    if value is None:
        return False
    obj = require_object(value, name, errors)
    if obj is None:
        return False
    host = obj.get("host")
    port = obj.get("port")
    if not isinstance(host, str) or not host.strip():
        errors.add(f"{name}.host must be a non-empty string")
        return False
    if not isinstance(port, int) or port < 1 or port > 65535:
        errors.add(f"{name}.port must be an integer 1-65535")
        return False
    return True


def validate_string_list(value: Any, name: str, errors: Errors) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.add(f"{name} must be a string array")


def validate_published_coverage(value: Any, name: str, errors: Errors) -> None:
    obj = require_object(value, name, errors)
    if obj is None:
        return
    require_fields(obj, COVERAGE_REQUIRED, name, errors)
    if obj.get("state") not in COVERAGE_PUBLISHED:
        errors.add(f"{name}.state must be complete or partial")
    for field in ("devices_discovered", "devices_inspected", "accessible_devices"):
        if field in obj and not isinstance(obj.get(field), int):
            errors.add(f"{name}.{field} must be an integer")
    for field in ("missing_device_info", "missing_restconf", "missing_ssh"):
        if field in obj:
            validate_string_list(obj.get(field), f"{name}.{field}", errors)


def validate_attempt_coverage(value: Any, name: str, errors: Errors) -> None:
    obj = require_object(value, name, errors)
    if obj is None:
        return
    if obj.get("state") not in COVERAGE_ATTEMPT:
        errors.add(f"{name}.state must be complete, partial, or unavailable")
        return
    if obj["state"] == "unavailable":
        for field in ("devices_discovered", "devices_inspected", "accessible_devices"):
            if field in obj and obj.get(field) is not None:
                errors.add(
                    f"{name}.{field} must be null when coverage is unavailable "
                    "(do not represent failed collection as zero discovered devices)"
                )
        return
    for field in ("devices_discovered", "devices_inspected", "accessible_devices"):
        if field in obj and not isinstance(obj.get(field), int):
            errors.add(f"{name}.{field} must be an integer when coverage is {obj['state']}")


def freshness(expires_at: datetime | None, as_of: datetime) -> str:
    if expires_at is None:
        return "unknown"
    if as_of < expires_at:
        return "current"
    return "stale"


def validate_inventory(
    data: Any, errors: Errors, as_of: datetime, require_current: bool
) -> None:
    obj = require_object(data, "inventory", errors)
    if obj is None:
        return
    require_fields(obj, INVENTORY_REQUIRED, "inventory", errors)
    reject_secrets(obj, "inventory", errors)
    if obj.get("schema") != INVENTORY_SCHEMA:
        errors.add(f"schema must be {INVENTORY_SCHEMA}")
    snapshot_id = obj.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_RE.match(snapshot_id):
        errors.add("snapshot_id must match YYYY-MM-DDTHH-MM-SSZ")
    if obj.get("environment") not in ENVIRONMENTS:
        errors.add(f"environment must be one of {sorted(ENVIRONMENTS)}")
    if obj.get("status") not in INVENTORY_STATUSES:
        errors.add("status must be complete or partial (failed collects are not published)")
    collected = (
        validate_utc(obj.get("collected_at"), "collected_at", errors)
        if "collected_at" in obj
        else None
    )
    if "published_at" in obj:
        validate_utc(obj.get("published_at"), "published_at", errors)
    expires = (
        validate_utc(obj.get("expires_at"), "expires_at", errors)
        if "expires_at" in obj
        else None
    )
    kind = freshness(expires, as_of)
    if kind == "stale":
        errors.note(
            "inventory is stale: inspect allowed; do not treat PAT/access as current"
        )
        if require_current:
            errors.add("inventory expires_at is not after --as-of; access is stale")
    elif kind == "current":
        errors.note("inventory access is current (as_of < expires_at)")
    if "coverage" in obj:
        validate_published_coverage(obj.get("coverage"), "coverage", errors)
        cov = obj.get("coverage")
        if isinstance(cov, dict) and obj.get("status") != cov.get("state"):
            errors.add("inventory status must match coverage.state")
    source = require_object(obj.get("source"), "source", errors) if "source" in obj else None
    if source is not None:
        if source.get("type") not in SOURCE_TYPES:
            errors.add(f"source.type must be one of {sorted(SOURCE_TYPES)}")
        if not isinstance(source.get("name"), str) or not source.get("name", "").strip():
            errors.add("source.name must be a non-empty string")
    if obj.get("infra_sot") not in INFRA_SOT:
        errors.add(f"infra_sot must be one of {sorted(INFRA_SOT)}")
    if not isinstance(obj.get("lab_title"), str) or not obj.get("lab_title", "").strip():
        errors.add("lab_title must be a non-empty string")
    netbox = require_object(obj.get("netbox"), "netbox", errors) if "netbox" in obj else None
    if netbox is not None:
        if not isinstance(netbox.get("tenant"), str) or not netbox.get("tenant", "").strip():
            errors.add("netbox.tenant must be a non-empty string")
        if not isinstance(netbox.get("site"), str) or not netbox.get("site", "").strip():
            errors.add("netbox.site must be a non-empty string")
    devices = obj.get("devices")
    if not isinstance(devices, list):
        errors.add("devices must be an array")
        return
    if obj.get("device_count") != len(devices):
        errors.add(f"device_count must equal len(devices) ({len(devices)})")
    links = obj.get("links")
    if not isinstance(links, list):
        errors.add("links must be an array")
    else:
        for i, link in enumerate(links):
            row = require_object(link, f"links[{i}]", errors)
            if row is None:
                continue
            for field in ("a_device", "a_interface", "b_device", "b_interface"):
                if not isinstance(row.get(field), str) or not row.get(field, "").strip():
                    errors.add(f"links[{i}].{field} must be a non-empty string")
    for i, device in enumerate(devices):
        validate_device(device, i, errors)
    if collected is not None and expires is not None and expires < collected:
        errors.add("expires_at must not be before collected_at")


def validate_device(device: Any, index: int, errors: Errors) -> None:
    name = f"devices[{index}]"
    obj = require_object(device, name, errors)
    if obj is None:
        return
    require_fields(obj, DEVICE_REQUIRED, name, errors)
    if not isinstance(obj.get("name"), str) or not obj.get("name", "").strip():
        errors.add(f"{name}.name must be a non-empty string")
    if not isinstance(obj.get("tags"), list) or not all(
        isinstance(tag, str) for tag in obj.get("tags", [])
    ):
        errors.add(f"{name}.tags must be a string array")
    if obj.get("agent_access") not in {True, False}:
        errors.add(f"{name}.agent_access must be a boolean")
    access = require_object(obj.get("access"), f"{name}.access", errors) if "access" in obj else None
    usable = False
    if access is not None:
        if "restconf" not in access or "ssh" not in access:
            errors.add(f"{name}.access must include restconf and ssh")
        else:
            usable = validate_endpoint(
                access.get("restconf"), f"{name}.access.restconf", errors
            ) or usable
            usable = validate_endpoint(access.get("ssh"), f"{name}.access.ssh", errors) or usable
            if access.get("restconf") is not None and isinstance(access.get("restconf"), dict):
                proto = access["restconf"].get("protocol")
                if proto is not None and not isinstance(proto, str):
                    errors.add(f"{name}.access.restconf.protocol must be a string")
    if obj.get("agent_access") is True and not usable:
        errors.add(f"{name}.agent_access is true but neither restconf nor ssh has host+port")
    if obj.get("agent_access") is False and usable:
        errors.add(f"{name}.agent_access is false but an endpoint is present")
    if "source_metadata" in obj and not isinstance(obj.get("source_metadata"), dict):
        errors.add(f"{name}.source_metadata must be an object")


def normalize_workspace_path(path: str) -> str:
    value = path.strip()
    if value.startswith("/workspace/"):
        value = value[len("/workspace/") :]
    elif value.startswith("workspace/"):
        value = value[len("workspace/") :]
    return value


def validate_inventory_path(value: Any, name: str, expected: str | None, errors: Errors) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.add(f"{name} must be a non-empty workspace-relative path")
        return
    path = normalize_workspace_path(value)
    if value != path:
        errors.add(f"{name} must not include a workspace/ or /workspace/ prefix: {value}")
        return
    if path.startswith("/") or HOST_ABS_RE.match(path):
        errors.add(f"{name} must be workspace-relative: {path}")
        return
    if not INVENTORY_PATH_RE.match(path):
        errors.add(f"{name} must be inventory/prod.json or inventory/dev.json")
        return
    if expected and path != expected:
        errors.add(f"{name} must be {expected}")


def validate_latest_attempt(value: Any, name: str, errors: Errors) -> None:
    if value is None:
        return
    obj = require_object(value, name, errors)
    if obj is None:
        return
    require_fields(obj, ATTEMPT_REQUIRED, name, errors)
    extra = set(obj) - set(ATTEMPT_REQUIRED) - {"coverage"}
    if extra:
        errors.add(f"{name} has unknown fields: {sorted(extra)}")
    if obj.get("status") not in ATTEMPT_STATUSES:
        errors.add(f"{name}.status must be one of {sorted(ATTEMPT_STATUSES)}")
    for field in ("attempted_at", "completed_at"):
        if field in obj:
            validate_utc(obj.get(field), f"{name}.{field}", errors)
    if not isinstance(obj.get("headline"), str) or not str(obj.get("headline", "")).strip():
        errors.add(f"{name}.headline must be a non-empty string")
    if obj.get("status") in {"failed", "unavailable"} and "coverage" not in obj:
        errors.add(f"{name}.coverage is required when the attempt failed")
    if "coverage" in obj and obj.get("coverage") is not None:
        validate_attempt_coverage(obj.get("coverage"), f"{name}.coverage", errors)
        cov = obj.get("coverage")
        if (
            isinstance(cov, dict)
            and obj.get("status") in {"failed", "unavailable"}
            and cov.get("state") != "unavailable"
        ):
            errors.add(f"{name}.coverage.state must be unavailable when the attempt failed")


def validate_current_snapshot(
    value: Any, name: str, expected_path: str, errors: Errors, as_of: datetime
) -> None:
    if value is None:
        return
    obj = require_object(value, name, errors)
    if obj is None:
        return
    require_fields(obj, SNAPSHOT_REQUIRED, name, errors)
    extra = set(obj) - set(SNAPSHOT_REQUIRED)
    if extra:
        errors.add(f"{name} has unknown fields: {sorted(extra)}")
    if "path" in obj:
        validate_inventory_path(obj.get("path"), f"{name}.path", expected_path, errors)
    if obj.get("status") not in INVENTORY_STATUSES:
        errors.add(f"{name}.status must be complete or partial")
    snapshot_id = obj.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_RE.match(snapshot_id):
        errors.add(f"{name}.snapshot_id must match YYYY-MM-DDTHH-MM-SSZ")
    if "collected_at" in obj:
        validate_utc(obj.get("collected_at"), f"{name}.collected_at", errors)
    expires = (
        validate_utc(obj.get("expires_at"), f"{name}.expires_at", errors)
        if "expires_at" in obj
        else None
    )
    kind = freshness(expires, as_of)
    if kind == "stale":
        errors.note(f"{name} is stale; do not treat PAT/access as current")
    if "coverage" in obj:
        validate_published_coverage(obj.get("coverage"), f"{name}.coverage", errors)


def validate_action_result(value: Any, name: str, errors: Errors) -> None:
    if value is None:
        return
    obj = require_object(value, name, errors)
    if obj is None:
        return
    require_fields(obj, COMPLETED_RUN_REQUIRED, name, errors)
    extra = set(obj) - set(COMPLETED_RUN_REQUIRED)
    if extra:
        errors.add(f"{name} has unknown fields: {sorted(extra)}")
    expected_workflow, expected_env, allowed = WORKFLOW_RESULTS[name]
    if obj.get("workflow") != expected_workflow:
        errors.add(f"{name}.workflow must be {expected_workflow}")
    if expected_env is not None and obj.get("environment") != expected_env:
        errors.add(f"{name}.environment must be {expected_env}")
    if name == "deploy_twin" and obj.get("environment") not in {"dev", None}:
        errors.add(f"{name}.environment must be dev or null")
    result = obj.get("result")
    if result not in allowed:
        errors.add(f"{name}.result must be one of {sorted(allowed)} (marker-derived, not the GitHub check)")
    for field in ("run_id", "html_url"):
        if not isinstance(obj.get(field), str) or not str(obj.get(field, "")).strip():
            errors.add(f"{name}.{field} is required for a completed run")
    if "updated_at" in obj:
        validate_utc(obj.get("updated_at"), f"{name}.updated_at", errors)


def validate_state(data: Any, errors: Errors, as_of: datetime) -> None:
    obj = require_object(data, "state", errors)
    if obj is None:
        return
    require_fields(obj, STATE_REQUIRED, "state", errors)
    reject_secrets(obj, "state", errors)
    extra_top = set(obj) - set(STATE_REQUIRED) - set(WORKFLOW_RESULTS)
    if extra_top:
        errors.add(f"state has unknown fields: {sorted(extra_top)}")
    if obj.get("schema") != STATE_SCHEMA:
        errors.add(f"schema must be {STATE_SCHEMA}")
    if obj.get("source_agent") != SOURCE_AGENT:
        errors.add(f"source_agent must be {SOURCE_AGENT}")
    if obj.get("status") not in STATE_STATUSES:
        errors.add(f"status must be one of {sorted(STATE_STATUSES)}")
    if not isinstance(obj.get("headline"), str) or not obj.get("headline", "").strip():
        errors.add("headline must be a non-empty string")
    if obj.get("operation") not in OPERATIONS:
        errors.add(f"operation must be one of {sorted(OPERATIONS)}")
    for field in ("updated_at", "started_at", "completed_at"):
        if field in obj:
            validate_utc(obj.get(field), field, errors)
    if not isinstance(obj.get("operation_id"), str) or not obj.get("operation_id", "").strip():
        errors.add("operation_id must be a non-empty string")
    if "gaps" in obj and not isinstance(obj.get("gaps"), list):
        errors.add("gaps must be an array")
    if obj.get("next_action") == "none":
        errors.add('next_action must be JSON null, never the string "none"')
    if obj.get("next_action") is not None and not isinstance(obj.get("next_action"), str):
        errors.add("next_action must be a string or null")
    elif isinstance(obj.get("next_action"), str) and not obj.get("next_action").strip():
        errors.add("next_action must be a non-empty string or null")
    inventories = (
        require_object(obj.get("inventories"), "inventories", errors)
        if "inventories" in obj
        else None
    )
    if inventories is not None:
        extra = set(inventories) - {"prod", "dev"}
        if extra:
            errors.add(f"inventories has unknown fields: {sorted(extra)}")
        if "prod" not in inventories or "dev" not in inventories:
            errors.add("inventories must include prod and dev")
        for env in ("prod", "dev"):
            slot = inventories.get(env)
            slot_obj = require_object(slot, f"inventories.{env}", errors)
            if slot_obj is None:
                continue
            if set(slot_obj) - {"latest_attempt", "current_snapshot"}:
                errors.add(f"inventories.{env} must only have latest_attempt and current_snapshot")
            if "latest_attempt" not in slot_obj or "current_snapshot" not in slot_obj:
                errors.add(f"inventories.{env} missing latest_attempt or current_snapshot")
            validate_latest_attempt(
                slot_obj.get("latest_attempt"), f"inventories.{env}.latest_attempt", errors
            )
            validate_current_snapshot(
                slot_obj.get("current_snapshot"),
                f"inventories.{env}.current_snapshot",
                f"inventory/{env}.json",
                errors,
                as_of,
            )
    for field in WORKFLOW_RESULTS:
        if field in obj:
            validate_action_result(obj.get(field), field, errors)
    if "infra_sot" in obj:
        errors.add("infra_sot belongs in state/netbox.json, not state/network-sync.json")


def pair_slot(
    slot: Any,
    inventory: Any,
    env: str,
    errors: Errors,
) -> None:
    if not isinstance(slot, dict):
        return
    snapshot = slot.get("current_snapshot")
    attempt = slot.get("latest_attempt")
    if snapshot is None:
        if inventory is not None:
            errors.add(
                f"inventories.{env}.current_snapshot is null but inventory/{env}.json was supplied"
            )
        return
    if not isinstance(snapshot, dict):
        return
    if inventory is None:
        return
    inv_id = inventory.get("snapshot_id")
    state_id = snapshot.get("snapshot_id")
    if inv_id != state_id:
        errors.add(
            f"inventories.{env}.current_snapshot.snapshot_id ({state_id}) "
            f"must match inventory/{env}.json snapshot_id ({inv_id})"
        )
    if snapshot.get("status") != inventory.get("status"):
        errors.add(f"inventories.{env}.current_snapshot.status must match the inventory file")
    if isinstance(attempt, dict) and attempt.get("status") in {"failed", "unavailable"}:
        if inv_id != state_id:
            errors.add(
                f"failed collect must preserve last-known-good inventory/{env}.json "
                "(snapshot_id changed)"
            )


def validate_pair(
    state: Any,
    prod: Any | None,
    dev: Any | None,
    errors: Errors,
    as_of: datetime,
    require_current: bool,
) -> None:
    validate_state(state, errors, as_of)
    if prod is not None:
        validate_inventory(prod, errors, as_of, require_current)
    if dev is not None:
        validate_inventory(dev, errors, as_of, require_current)
    inventories = state.get("inventories") if isinstance(state, dict) else None
    if isinstance(inventories, dict):
        pair_slot(inventories.get("prod"), prod, "prod", errors)
        pair_slot(inventories.get("dev"), dev, "dev", errors)


def walk_preserve(prior: Any, merged: Any, path: str, errors: Errors) -> None:
    if isinstance(prior, dict):
        if not isinstance(merged, dict):
            errors.add(f"merge dropped object at {path}")
            return
        for key, value in prior.items():
            if key not in merged:
                errors.add(f"merge discarded field: {path}.{key}")
            else:
                walk_preserve(value, merged[key], f"{path}.{key}", errors)
    elif isinstance(prior, list):
        if not isinstance(merged, list):
            errors.add(f"merge dropped array at {path}")


def validate_merge(prior: Any, merged: Any, errors: Errors, as_of: datetime) -> None:
    validate_inventory(merged, errors, as_of, require_current=False)
    if not isinstance(prior, dict) or not isinstance(merged, dict):
        errors.add("merge prior and result must be objects")
        return
    walk_preserve(prior, merged, "inventory", errors)
    prior_devices = {
        d.get("name"): d
        for d in prior.get("devices", [])
        if isinstance(d, dict) and d.get("name")
    }
    merged_devices = {
        d.get("name"): d
        for d in merged.get("devices", [])
        if isinstance(d, dict) and d.get("name")
    }
    for name, device in prior_devices.items():
        if name not in merged_devices:
            errors.add(f"merge discarded device {name}")
            continue
        walk_preserve(device, merged_devices[name], f"devices.{name}", errors)


def report(kind: str, path: str, errors: Errors) -> int:
    for note in errors.notes:
        print(f"note: {note}")
    if errors.ok():
        print(f"ok: {kind} {path}")
        return 0
    print(f"invalid {kind}: {path}", file=sys.stderr)
    for item in errors.items:
        print(f"- {item}", file=sys.stderr)
    return 1


def parse_as_of(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = parse_utc(value)
    if parsed is None:
        raise SystemExit(f"invalid --as-of timestamp: {value}")
    return parsed


def selftest() -> int:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    examples = root / "examples"
    as_of = parse_utc("2026-08-14T21:30:00Z")
    assert as_of is not None
    errors = Errors()
    prod = load_json(str(examples / "inventory-prod.example.json"), errors)
    dev = load_json(str(examples / "inventory-dev.example.json"), errors)
    state = load_json(str(examples / "network-sync-state.example.json"), errors)
    failed = load_json(str(examples / "network-sync-state-failed-collect.example.json"), errors)
    if not errors.ok():
        return report("selftest-load", str(examples), errors)
    validate_pair(state, prod, dev, errors, as_of, require_current=True)
    if not errors.ok():
        return report("selftest-pair", "examples", errors)

    failed_errors = Errors()
    validate_pair(failed, prod, None, failed_errors, as_of, require_current=True)
    if not failed_errors.ok():
        return report("selftest-failed-collect", "failed-collect example", failed_errors)

    mismatch = copy.deepcopy(state)
    mismatch["inventories"]["prod"]["current_snapshot"]["snapshot_id"] = "1999-01-01T00-00-00Z"
    mismatch_errors = Errors()
    validate_pair(mismatch, prod, dev, mismatch_errors, as_of, False)
    if mismatch_errors.ok():
        print("selftest failed: expected snapshot_id mismatch", file=sys.stderr)
        return 1

    none_errors = Errors()
    bad_none = copy.deepcopy(state)
    bad_none["next_action"] = "none"
    validate_state(bad_none, none_errors, as_of)
    if none_errors.ok():
        print("selftest failed: expected next_action none rejection", file=sys.stderr)
        return 1

    secret_errors = Errors()
    secret = copy.deepcopy(prod)
    secret["devices"][0]["password"] = "nope"
    validate_inventory(secret, secret_errors, as_of, False)
    if secret_errors.ok():
        print("selftest failed: expected secret rejection", file=sys.stderr)
        return 1

    result_errors = Errors()
    bad_result = copy.deepcopy(state)
    bad_result["sync_prod"]["result"] = "in_sync"
    validate_state(bad_result, result_errors, as_of)
    if result_errors.ok():
        print("selftest failed: expected workflow result rejection", file=sys.stderr)
        return 1

    stale_errors = Errors()
    later = parse_utc("2026-08-16T00:00:00Z")
    assert later is not None
    validate_inventory(prod, stale_errors, later, require_current=True)
    if stale_errors.ok():
        print("selftest failed: expected stale rejection with --require-current", file=sys.stderr)
        return 1

    merge_errors = Errors()
    prior = copy.deepcopy(prod)
    prior["operator_note"] = "keep me"
    prior["devices"][0]["rack"] = "R1"
    merged = copy.deepcopy(prod)
    merged["operator_note"] = "keep me"
    merged["devices"][0]["rack"] = "R1"
    merged["snapshot_id"] = "2026-08-14T21-30-00Z"
    merged["published_at"] = "2026-08-14T21:30:00Z"
    validate_merge(prior, merged, merge_errors, as_of)
    if not merge_errors.ok():
        return report("selftest-merge", "preserve", merge_errors)
    dropped = copy.deepcopy(merged)
    del dropped["operator_note"]
    drop_errors = Errors()
    validate_merge(prior, dropped, drop_errors, as_of)
    if drop_errors.ok():
        print("selftest failed: expected dropped-field rejection", file=sys.stderr)
        return 1

    zero_errors = Errors()
    zeros = copy.deepcopy(failed)
    zeros["inventories"]["prod"]["latest_attempt"]["coverage"] = {
        "state": "unavailable",
        "devices_discovered": 0,
        "devices_inspected": 0,
        "accessible_devices": 0,
    }
    validate_state(zeros, zero_errors, as_of)
    if zero_errors.ok():
        print("selftest failed: expected zero-discovered rejection", file=sys.stderr)
        return 1

    print("ok: selftest")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Network Sync inventory and state files."
    )
    parser.add_argument(
        "--as-of",
        help="UTC instant for freshness (default: now). Examples: use the collect window.",
    )
    parser.add_argument(
        "--require-current",
        action="store_true",
        help="Fail if expires_at <= --as-of (stale access).",
    )
    parser.add_argument("kind", nargs="?", help="inventory | state | pair | merge | selftest")
    parser.add_argument("paths", nargs="*", help="files")
    args = parser.parse_args(argv[1:])
    if args.kind == "selftest":
        return selftest()
    try:
        as_of = parse_as_of(args.as_of)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.kind == "inventory" and len(args.paths) == 1:
        errors = Errors()
        data = load_json(args.paths[0], errors)
        if data is not None:
            validate_inventory(data, errors, as_of, args.require_current)
        return report("inventory", args.paths[0], errors)
    if args.kind == "state" and len(args.paths) == 1:
        errors = Errors()
        data = load_json(args.paths[0], errors)
        if data is not None:
            validate_state(data, errors, as_of)
        return report("state", args.paths[0], errors)
    if args.kind == "pair" and 2 <= len(args.paths) <= 3:
        errors = Errors()
        state = load_json(args.paths[0], errors)
        prod = load_json(args.paths[1], errors)
        dev = load_json(args.paths[2], errors) if len(args.paths) == 3 else None
        if state is not None and prod is not None:
            validate_pair(state, prod, dev, errors, as_of, args.require_current)
        return report("pair", " ".join(args.paths), errors)
    if args.kind == "merge" and len(args.paths) == 2:
        errors = Errors()
        prior = load_json(args.paths[0], errors)
        merged = load_json(args.paths[1], errors)
        if prior is not None and merged is not None:
            validate_merge(prior, merged, errors, as_of)
        return report("merge", args.paths[1], errors)
    print(
        "usage:\n"
        "  validate_network_sync.py inventory <file>\n"
        "  validate_network_sync.py state <file>\n"
        "  validate_network_sync.py pair <state> <prod.json> [dev.json]\n"
        "  validate_network_sync.py merge <prior.json> <merged.json>\n"
        "  validate_network_sync.py selftest",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
