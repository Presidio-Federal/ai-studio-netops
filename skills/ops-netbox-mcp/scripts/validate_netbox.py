#!/usr/bin/env python3
"""Validate inventory/infra-sot.json and state/netbox.json. Never contacts NetBox."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from typing import Any

SNAP_SCHEMA = "infra-sot/v1"
STATE_SCHEMA = "netbox-state/v1"
SOURCE_AGENT = "ops-netbox-sot"
STATUSES = {"ok", "gaps", "failed"}
MODES = {"bootstrap", "audit", "reconcile"}
UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"
)
KEY_RE = re.compile(
    r"^(device|interface|site|service|test|control|incident|change):[^ ].*$"
)

SNAP_REQUIRED = [
    "schema",
    "updated_at",
    "source_agent",
    "status",
    "headline",
    "next_action",
    "mode",
    "seed",
    "parents",
    "devices",
    "cables",
    "counts",
    "gaps",
    "netbox_pushed_at",
    "keys",
]
STATE_REQUIRED = [
    "schema",
    "updated_at",
    "source_agent",
    "status",
    "headline",
    "next_action",
    "kind",
    "mode",
    "source",
    "tenant",
    "site",
    "seed_match",
    "counts",
    "links",
    "gaps",
    "details",
    "netbox_pushed_at",
    "keys",
]
COUNT_KEYS = ("devices", "interfaces", "ip_addresses", "cables")


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


def validate_counts(value: Any, name: str, errors: Errors) -> None:
    obj = require_object(value, name, errors)
    if obj is None:
        return
    for key in COUNT_KEYS:
        if key not in obj:
            errors.add(f"{name} missing {key}")
            continue
        if not isinstance(obj[key], int) or obj[key] < 0:
            errors.add(f"{name}.{key} must be an integer >= 0")


def validate_keys(value: Any, name: str, errors: Errors) -> set[str]:
    if not isinstance(value, list):
        errors.add(f"{name} must be an array")
        return set()
    if len(value) != len(set(value)):
        errors.add(f"{name} must not contain duplicates")
    for key in value:
        if not isinstance(key, str) or not KEY_RE.match(key):
            errors.add(f"{name} contains invalid key: {key}")
    return {key for key in value if isinstance(key, str)}


def validate_snap(data: Any, errors: Errors) -> None:
    obj = require_object(data, "snap", errors)
    if obj is None:
        return
    require_fields(obj, SNAP_REQUIRED, "snap", errors)
    if obj.get("schema") != SNAP_SCHEMA:
        errors.add(f"schema must be {SNAP_SCHEMA}")
    if obj.get("source_agent") != SOURCE_AGENT:
        errors.add(f"source_agent must be {SOURCE_AGENT}")
    if obj.get("status") not in STATUSES:
        errors.add(f"status must be one of {sorted(STATUSES)}")
    if obj.get("mode") not in MODES:
        errors.add(f"mode must be one of {sorted(MODES)}")
    if "updated_at" in obj:
        validate_utc(obj.get("updated_at"), "updated_at", errors)
    if obj.get("netbox_pushed_at") is not None:
        validate_utc(obj.get("netbox_pushed_at"), "netbox_pushed_at", errors)
    if "gaps" in obj and not isinstance(obj.get("gaps"), list):
        errors.add("gaps must be an array")
    if "counts" in obj:
        validate_counts(obj.get("counts"), "counts", errors)
    actual_keys = validate_keys(obj.get("keys"), "keys", errors)
    expected_keys: set[str] = set()
    parents = obj.get("parents")
    if isinstance(parents, dict) and isinstance(parents.get("site"), dict):
        site = parents["site"].get("slug")
        if isinstance(site, str):
            expected_keys.add(f"site:{site}")
    for device in obj.get("devices", []) if isinstance(obj.get("devices"), list) else []:
        if not isinstance(device, dict) or not isinstance(device.get("name"), str):
            continue
        device_name = device["name"]
        expected_keys.add(f"device:{device_name}")
        for interface in device.get("interfaces", []) if isinstance(device.get("interfaces"), list) else []:
            if isinstance(interface, dict) and isinstance(interface.get("name"), str):
                expected_keys.add(f"interface:{device_name}/{interface['name']}")
    if actual_keys != expected_keys:
        errors.add("keys must equal the deduplicated union of site, devices, and device-qualified interfaces")


def validate_state(data: Any, errors: Errors) -> None:
    obj = require_object(data, "state", errors)
    if obj is None:
        return
    require_fields(obj, STATE_REQUIRED, "state", errors)
    if obj.get("schema") != STATE_SCHEMA:
        errors.add(f"schema must be {STATE_SCHEMA}")
    if obj.get("source_agent") != SOURCE_AGENT:
        errors.add(f"source_agent must be {SOURCE_AGENT}")
    if obj.get("status") not in STATUSES:
        errors.add(f"status must be one of {sorted(STATUSES)}")
    if obj.get("kind") not in {"netbox", "git"}:
        errors.add("kind must be netbox or git")
    if obj.get("mode") not in MODES:
        errors.add(f"mode must be one of {sorted(MODES)}")
    if obj.get("source") not in {"cml", "api", "document"}:
        errors.add("source must be cml, api, or document")
    if obj.get("seed_match") not in {True, False}:
        errors.add("seed_match must be a boolean")
    if obj.get("details") != "inventory/infra-sot.json":
        errors.add("details must be inventory/infra-sot.json")
    if "updated_at" in obj:
        validate_utc(obj.get("updated_at"), "updated_at", errors)
    if obj.get("netbox_pushed_at") is not None:
        validate_utc(obj.get("netbox_pushed_at"), "netbox_pushed_at", errors)
    if "gaps" in obj and not isinstance(obj.get("gaps"), list):
        errors.add("gaps must be an array")
    if "counts" in obj:
        validate_counts(obj.get("counts"), "counts", errors)
    if "links" not in obj:
        errors.add("state missing required field: links")
    elif not isinstance(obj.get("links"), list):
        errors.add("links must be an array")
    else:
        for i, row in enumerate(obj.get("links", [])):
            block = require_object(row, f"links[{i}]", errors)
            if block is None:
                continue
            for key in ("a_device", "a_interface", "b_device", "b_interface"):
                if not isinstance(block.get(key), str) or not block.get(key, "").strip():
                    errors.add(f"links[{i}].{key} must be a non-empty string")
        cable_count = (obj.get("counts") or {}).get("cables") if isinstance(obj.get("counts"), dict) else None
        if isinstance(cable_count, int) and cable_count != len(obj["links"]):
            errors.add("links length must equal counts.cables")
    if obj.get("next_action") is not None and not isinstance(obj.get("next_action"), str):
        errors.add("next_action must be a string or null")
    actual_keys = validate_keys(obj.get("keys"), "keys", errors)
    expected_keys: set[str] = set()
    if isinstance(obj.get("site"), str):
        expected_keys.add(f"site:{obj['site']}")
    for link in obj.get("links", []) if isinstance(obj.get("links"), list) else []:
        if not isinstance(link, dict):
            continue
        for side in ("a", "b"):
            device = link.get(f"{side}_device")
            interface = link.get(f"{side}_interface")
            if isinstance(device, str):
                expected_keys.add(f"device:{device}")
                if isinstance(interface, str):
                    expected_keys.add(f"interface:{device}/{interface}")
    if actual_keys != expected_keys:
        errors.add("keys must equal the deduplicated union of site and linked devices/interfaces")


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in {"snap", "state"}:
        print("usage: validate_netbox.py snap|state <file>", file=sys.stderr)
        return 2
    kind, path = argv[1], argv[2]
    errors = Errors()
    data = load_json(path, errors)
    if data is not None:
        if kind == "snap":
            validate_snap(data, errors)
        else:
            validate_state(data, errors)
    if errors.ok():
        print(f"ok: {kind} {path}")
        return 0
    print(f"invalid {kind}: {path}", file=sys.stderr)
    for item in errors.items:
        print(f"- {item}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
