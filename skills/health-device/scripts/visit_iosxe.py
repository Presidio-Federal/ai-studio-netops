#!/usr/bin/env python3
"""IOS-XE health visit. One command collects, diffs, and writes the board.

collect runs under execution_type mcp_orchestration. annotate runs under
standard and only edits headline and notes. Material rules are the ones
in references/iosxe.md. Topology mode is not this script.

The agent copies the path Studio shows for this file. Do not hardcode it.

  python3 <skill>/scripts/visit_iosxe.py collect --workspace <file_explorer>
  python3 <skill>/scripts/visit_iosxe.py annotate --workspace <file_explorer> \\
      --stamp health/iosxe/<stamp>.json --headline "..." --note "device:NAME=..."
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace-handoff" / "scripts"))

try:
    import visit_common  # noqa: E402
except ImportError:
    print(
        '{"error": "visit_common missing; attach the workspace-handoff skill"}',
        file=sys.stderr,
    )
    sys.exit(1)

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
CHECK_SCHEMA = SCHEMA_DIR / "health-iosxe-check.schema.json"
BOARD_SCHEMA = SCHEMA_DIR / "health-metadata-iosxe.schema.json"

CALLS = (
    (
        "system",
        "Cisco-IOS-XE-device-hardware-oper:device-hardware-data/device-hardware/device-system-data",
        {"fields": "boot-time;software-version;last-reboot-reason;reason-severity;unsaved-config"},
    ),
    (
        "cpu",
        "Cisco-IOS-XE-process-cpu-oper:cpu-usage/cpu-utilization",
        {"fields": "five-seconds;one-minute;five-minutes"},
    ),
    (
        "memory",
        "Cisco-IOS-XE-memory-oper:memory-statistics/memory-statistic=Processor",
        None,
    ),
    (
        "interfaces",
        "Cisco-IOS-XE-interfaces-oper:interfaces",
        {
            "fields": "interface(name;admin-status;oper-status;last-change;ipv4;input-security-acl;output-security-acl;statistics(num-flaps;in-crc-errors;in-errors;in-discards))"
        },
    ),
    (
        "bgp",
        "Cisco-IOS-XE-bgp-oper:bgp-state-data/address-families",
        {
            "fields": "address-family(afi-safi;vrf-name;bgp-neighbor-summaries/bgp-neighbor-summary(id;as;state;up-time;prefixes-received))"
        },
    ),
)

SKIP_PREFIXES = ("Loopback", "Vlan", "Null")
CPU_LINE = 80
MEM_LINE = 85
BOOT_SKEW_SECONDS = 5
MAX_BGP_DETAIL = 3
MAX_CALLS = 50
CHANGED_CAP = 24
READINGS_CAP = 64


def coerce_int(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() == "true":
            return True
        if value.strip().lower() == "false":
            return False
    return None


def blank_to_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace("\r", " ").replace("\n", " ").strip()
        if value == "":
            return None
    return value


def unwrap_body(body):
    if isinstance(body, dict) and len(body) == 1:
        only = next(iter(body.values()))
        if isinstance(only, (dict, list)):
            return only
    return body


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def top_keys(body):
    if isinstance(body, dict):
        return ",".join(list(body.keys())[:8])
    return type(body).__name__


def version_token(raw):
    if not isinstance(raw, str):
        return None
    match = re.search(r"Version\s+([^,]+)", raw)
    if match:
        return match.group(1).strip() or None
    text = raw.strip()
    return text or None


def ipv4s(value):
    found = []
    if isinstance(value, str):
        found.extend(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", value))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(ipv4s(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(ipv4s(item))
    out = []
    for addr in found:
        if addr != "0.0.0.0" and addr not in out:
            out.append(addr)
    return out


def duration_seconds(text):
    """IOS up-time to seconds. None when the string is not a duration."""
    if not isinstance(text, str):
        return None
    raw = text.strip().lower()
    if raw == "" or raw == "never":
        return 0
    if re.fullmatch(r"\d+:\d{2}:\d{2}", raw):
        hours, minutes, seconds = (int(p) for p in raw.split(":"))
        return hours * 3600 + minutes * 60 + seconds
    weeks = days = hours = minutes = seconds = 0
    for number, unit in re.findall(r"(\d+)\s*([wdhms])", raw):
        number = int(number)
        if unit == "w":
            weeks = number
        elif unit == "d":
            days = number
        elif unit == "h":
            hours = number
        elif unit == "m":
            minutes = number
        elif unit == "s":
            seconds = number
    if re.search(r"[wdhms]", raw):
        return weeks * 604800 + days * 86400 + hours * 3600 + minutes * 60 + seconds
    return None


def up_time_shorter(prior, current):
    left = duration_seconds(prior)
    right = duration_seconds(current)
    if left is None or right is None:
        return False
    return right < left


def crossed(prior, current, line):
    if current is None or prior is None:
        return prior is None and current is not None and current >= line
    return (prior < line <= current) or (current < line <= prior)


def oper_not_ready_state(state):
    text = state or ""
    if text == "if-oper-state-ready":
        return False
    if "idle" in text.lower():
        return False
    return text != ""


def oper_not_ready(row):
    if row.get("admin_status") and row.get("admin_status") != "if-state-up":
        return False
    return oper_not_ready_state(row.get("state") or "")


def required_interface_failed(row, intended):
    if row.get("kind") != "interface":
        return False
    if row.get("intent") == "failed" or oper_not_ready(row):
        return True
    return bool(intended) and row.get("admin_status") != "if-state-up"


def stamp_name(moment):
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


def checked_at(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def canon_time(value):
    """UTC second stamp. Z and +00:00 of the same instant compare equal."""
    if not isinstance(value, str) or not value.strip():
        return value
    text = value.strip()
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc).replace(microsecond=0)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def same_instant(left, right):
    return canon_time(left) == canon_time(right)


def instant_epoch(value):
    text = canon_time(value)
    if not isinstance(text, str):
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def boot_shift_seconds(prior, current):
    left = instant_epoch(prior)
    right = instant_epoch(current)
    if left is None or right is None:
        return None
    return right - left


def interval_seconds(prior_at, current_at):
    seconds = boot_shift_seconds(prior_at, current_at)
    if seconds is None or seconds <= 0:
        return None
    return int(seconds)


def intended_interfaces(prod, name):
    found = set()
    for link in (prod or {}).get("links") or []:
        if link.get("a_device") == name and link.get("a_interface"):
            found.add(str(link["a_interface"]))
        if link.get("b_device") == name and link.get("b_interface"):
            found.add(str(link["b_interface"]))
    return found


def classify_interface(admin, oper, prior_row, intended):
    if admin != "if-state-up":
        if prior_row is None:
            return "provisioning"
        return "admin_disabled"
    if oper_not_ready_state(oper):
        return "failed"
    if intended:
        return "ok"
    return "ok" if oper else "unknown"


def row_id(row):
    return (row.get("name"), row.get("kind"), row.get("subject"))


def union_keys(rows):
    seen = []
    for row in rows:
        for key in row.get("keys") or []:
            if key not in seen:
                seen.append(key)
    return seen


def rank_key(device):
    role = (device.get("role") or "").lower()
    name = device.get("name") or ""
    upper = name.upper()
    if role == "wan":
        group = 0
    elif role == "edge" or any(token in upper for token in ("HQ", "CLOUD", "DC")):
        group = 1
    else:
        group = 2
    return (group, name)


def restconf_devices(prod):
    chosen = []
    for device in prod.get("devices") or []:
        access = (device.get("access") or {}).get("restconf") or {}
        host = access.get("host")
        port = access.get("port")
        platform = str(device.get("platform") or "").lower()
        if platform == "iosxe" and host and port and device.get("name"):
            chosen.append(device)
    chosen.sort(key=rank_key)
    return chosen


def address_index(payloads_by_device, topology, prod_names):
    """Map an interface address to a prod.json device name. Peer resolution only."""
    index = {}

    def put(addr, name):
        if addr and name in prod_names and addr not in index:
            index[addr] = name

    for name, payloads in payloads_by_device.items():
        for iface in interface_rows(payloads.get("interfaces")):
            for addr in ipv4s(iface.get("ipv4")):
                put(addr, name)
    for device in (topology or {}).get("devices") or []:
        name = device.get("name")
        if name not in prod_names:
            continue
        for iface in device.get("interfaces") or []:
            cidr = iface.get("cidr") or ""
            put(str(cidr).split("/")[0], name)
    return index


def far_of(topology, device, interface):
    for row in (topology or {}).get("devices") or []:
        if row.get("name") != device:
            continue
        for neighbor in row.get("neighbors") or []:
            if neighbor.get("local") == interface and neighbor.get("far"):
                return neighbor.get("far")
    return None


def get_call(host, port, name, path, params):
    args = {"host": host, "port": int(port), "path": path}
    if params:
        args["params"] = params
    started = time.monotonic()
    envelope = visit_common.mcp_call("iosxe_restconf_get", args, retries=1)
    elapsed = time.monotonic() - started
    payload, error = visit_common.unwrap_iosxe(envelope)
    shown = "ok" if error is None else str(error)[:120]
    print(
        f"iosxe device={name} call={path.split(':')[-1].split('/')[-1]} elapsed_s={elapsed:.3f} result={shown}",
        file=sys.stderr,
    )
    return payload, error


def bgp_reset_reason(body):
    node = unwrap_body(body)
    rows = []
    if isinstance(node, dict):
        if "neighbor" in node:
            rows = as_list(node.get("neighbor"))
        else:
            rows = [node]
    elif isinstance(node, list):
        rows = node
    for row in rows:
        if not isinstance(row, dict):
            continue
        conn = row.get("connection")
        if isinstance(conn, dict):
            reason = blank_to_none(conn.get("reset-reason"))
            if reason:
                return reason
        reason = blank_to_none(row.get("reset-reason"))
        if reason:
            return reason
    return None


def collect_bgp_resets(host, port, name, bgp_body, budget, calls_used):
    reasons = {}
    extra = 0
    for neighbor in bgp_rows(bgp_body):
        if extra >= MAX_BGP_DETAIL:
            break
        if blank_to_none(neighbor.get("state")) == "fsm-established":
            continue
        peer_id = blank_to_none(neighbor.get("id"))
        afi = neighbor.get("_afi_safi")
        vrf = neighbor.get("_vrf") or "default"
        if not peer_id or not afi:
            continue
        if budget.exhausted() or calls_used[0] >= MAX_CALLS:
            break
        path = (
            "Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors/"
            f"neighbor={afi},{vrf},{peer_id}"
        )
        calls_used[0] += 1
        extra += 1
        payload, error = get_call(
            host,
            port,
            name,
            path,
            {"fields": "connection;session-state"},
        )
        if error is None:
            reasons[peer_id] = bgp_reset_reason(payload)
    return reasons


def collect_device(device, budget, calls_used):
    name = device["name"]
    access = device["access"]["restconf"]
    host = access["host"]
    port = access["port"]
    started = time.monotonic()
    payloads = {}
    errors = {}
    for label, path, params in CALLS:
        if budget.exhausted() or calls_used[0] >= MAX_CALLS:
            errors[label] = "budget"
            payloads[label] = None
            continue
        calls_used[0] += 1
        payload, error = get_call(host, port, name, path, params)
        if label == "bgp" and error in ("status 204", "status 404"):
            payloads[label] = {"address-family": []}
            errors[label] = None
            continue
        payloads[label] = payload
        errors[label] = error
    payloads["bgp_reset"] = collect_bgp_resets(
        host, port, name, payloads.get("bgp"), budget, calls_used
    )
    print(
        f"iosxe device={name} elapsed_s={time.monotonic() - started:.3f} calls={sum(1 for label, _, _ in CALLS if errors.get(label) != 'budget')} result={'fail' if any(errors.values()) else 'ok'}",
        file=sys.stderr,
    )
    if any(errors.get(label) for label, _, _ in CALLS):
        return None, errors
    return payloads, errors


def system_fields(body, name):
    node = unwrap_body(body)
    if isinstance(node, dict) and "device-system-data" in node:
        node = node["device-system-data"]
    if not isinstance(node, dict):
        print(f"iosxe device={name} call=system keys={top_keys(body)}", file=sys.stderr)
        return {}
    if "boot-time" not in node:
        print(f"iosxe device={name} call=system missing=boot-time keys={top_keys(body)}", file=sys.stderr)
    return node


def cpu_value(body):
    node = unwrap_body(body)
    if isinstance(node, dict) and "cpu-utilization" in node:
        node = node["cpu-utilization"]
    for row in as_list(node):
        if isinstance(row, dict) and "five-minutes" in row:
            return coerce_int(row.get("five-minutes"))
    return None


def memory_pct(body):
    node = unwrap_body(body)
    if isinstance(node, dict) and "memory-statistic" in node:
        node = node["memory-statistic"]
    chosen = None
    for row in as_list(node):
        if not isinstance(row, dict):
            continue
        if row.get("name") == "Processor" or chosen is None:
            chosen = row
        if row.get("name") == "Processor":
            break
    if not isinstance(chosen, dict):
        return None
    used = coerce_int(chosen.get("used-memory"))
    total = coerce_int(chosen.get("total-memory"))
    if used is None or not total:
        return None
    return int(round(used / total * 100))


def interface_rows(body):
    node = unwrap_body(body)
    if isinstance(node, dict) and "interface" in node:
        return [row for row in as_list(node.get("interface")) if isinstance(row, dict)]
    if isinstance(node, list):
        return [row for row in node if isinstance(row, dict)]
    return []


def bgp_rows(body):
    node = unwrap_body(body)
    families = []
    if isinstance(node, dict) and "address-family" in node:
        families = as_list(node.get("address-family"))
    elif isinstance(node, dict) and "address-families" in node:
        inner = node["address-families"]
        if isinstance(inner, dict):
            families = as_list(inner.get("address-family"))
    elif isinstance(node, list):
        families = node
    neighbors = []
    for family in families:
        if not isinstance(family, dict):
            continue
        summaries = family.get("bgp-neighbor-summaries") or {}
        if isinstance(summaries, dict):
            family_neighbors = as_list(summaries.get("bgp-neighbor-summary"))
        elif isinstance(summaries, list):
            family_neighbors = summaries
        else:
            family_neighbors = []
        afi = blank_to_none(family.get("afi-safi"))
        vrf = blank_to_none(family.get("vrf-name")) or "default"
        for neighbor in family_neighbors:
            if not isinstance(neighbor, dict):
                continue
            item = dict(neighbor)
            item["_afi_safi"] = afi
            item["_vrf"] = vrf
            neighbors.append(item)
    return neighbors


def build_rows(name, payloads, peers, checked, prior_rows=None, intended=None):
    prior_map = {row_id(row): row for row in (prior_rows or [])}
    intended = intended or set()
    reasons = payloads.get("bgp_reset") or {}
    system = system_fields(payloads.get("system"), name)
    boot = canon_time(blank_to_none(system.get("boot-time"))) or checked
    device_row = {
        "name": name,
        "kind": "device",
        "subject": name,
        "keys": [f"device:{name}"],
        "state": "up",
        "last_changed": str(boot),
        "software_version": version_token(system.get("software-version")),
        "last_reboot_reason": blank_to_none(system.get("last-reboot-reason")),
        "reason_severity": blank_to_none(system.get("reason-severity")),
        "cpu_5m": cpu_value(payloads.get("cpu")),
        "mem_used_pct": memory_pct(payloads.get("memory")),
        "unsaved_config": coerce_bool(system.get("unsaved-config")),
    }
    rows = [device_row]
    for iface in interface_rows(payloads.get("interfaces")):
        iname = iface.get("name")
        if not iname or str(iname).startswith(SKIP_PREFIXES):
            continue
        admin = blank_to_none(iface.get("admin-status"))
        oper = blank_to_none(iface.get("oper-status"))
        stats = iface.get("statistics") or {}
        prior_iface = prior_map.get((name, "interface", str(iname)))
        rows.append(
            {
                "name": name,
                "kind": "interface",
                "subject": str(iname),
                "keys": [f"device:{name}", f"interface:{name}/{iname}"],
                "state": oper,
                "admin_status": admin,
                "intent": classify_interface(
                    admin, oper, prior_iface, str(iname) in intended
                ),
                "last_changed": str(canon_time(blank_to_none(iface.get("last-change"))) or checked),
                "in_errors": coerce_int(stats.get("in-errors")),
                "in_crc_errors": coerce_int(stats.get("in-crc-errors")),
                "in_discards": coerce_int(stats.get("in-discards")),
                "num_flaps": coerce_int(stats.get("num-flaps")),
                "input_acl": blank_to_none(iface.get("input-security-acl")),
                "output_acl": blank_to_none(iface.get("output-security-acl")),
            }
        )
    for neighbor in bgp_rows(payloads.get("bgp")):
        peer_id = blank_to_none(neighbor.get("id"))
        if peer_id is None:
            continue
        peer_name = peers.get(str(peer_id))
        keys = [f"device:{name}"]
        if peer_name and f"device:{peer_name}" not in keys:
            keys.append(f"device:{peer_name}")
        rows.append(
            {
                "name": name,
                "kind": "bgp",
                "subject": str(peer_id),
                "keys": keys,
                "state": blank_to_none(neighbor.get("state")),
                "last_changed": checked,
                "up_time": blank_to_none(neighbor.get("up-time")),
                "prefixes_received": coerce_int(neighbor.get("prefixes-received")),
                "remote_as": coerce_int(neighbor.get("as")),
                "peer": f"device:{peer_name}" if peer_name else None,
                "reset_reason": reasons.get(str(peer_id)),
            }
        )
    return rows


def reboot_corroborated(old_dev, new_dev, old_rows, new_rows):
    if old_dev.get("last_reboot_reason") != new_dev.get("last_reboot_reason"):
        return True
    if old_dev.get("software_version") != new_dev.get("software_version"):
        return True
    boot = instant_epoch(new_dev.get("last_changed"))
    for row in new_rows:
        if row["kind"] == "interface":
            changed = instant_epoch(row.get("last_changed"))
            if boot is not None and changed is not None and changed >= boot:
                return True
        if row["kind"] == "bgp":
            old = next(
                (
                    item
                    for item in old_rows
                    if item["kind"] == "bgp" and item.get("subject") == row.get("subject")
                ),
                None,
            )
            if old and up_time_shorter(old.get("up_time"), row.get("up_time")):
                return True
    return False


def direction(kind, field, prior, current, extra=None):
    extra = extra or {}
    if field == "boot_time":
        return "worse" if extra.get("reboot") else "changed"
    if field in ("num_flaps", "in_errors", "in_crc_errors") and extra.get("reset"):
        return "changed"
    if field in ("num_flaps", "in_errors", "in_crc_errors", "up_time"):
        return "worse"
    if field in ("cpu_5m", "mem_used_pct"):
        if prior is None or current is None:
            return "worse" if (current or 0) >= (CPU_LINE if field == "cpu_5m" else MEM_LINE) else "better"
        return "worse" if current > prior else "better"
    if field == "state" and kind == "interface":
        if prior == "if-oper-state-ready" and current != "if-oper-state-ready":
            return "worse"
        if current == "if-oper-state-ready" and prior != "if-oper-state-ready":
            return "better"
        return "changed"
    if field == "state" and kind == "bgp":
        if prior == "fsm-established" and current != "fsm-established":
            return "worse"
        if current == "fsm-established" and prior != "fsm-established":
            return "better"
        return "changed"
    if field in ("input_acl", "output_acl", "peer"):
        if prior and not current:
            return "worse"
        if field == "peer" and current and not prior:
            return "better"
        return "changed"
    if field == "admin_status":
        if current != "if-state-up" and extra.get("intended"):
            return "worse"
        return "changed"
    if field in ("unsaved_config", "reset_reason"):
        return "changed"
    if field == "row" and kind == "bgp" and current is None:
        return "worse"
    if field == "row" and kind == "interface" and extra.get("intended") and current is None:
        return "worse"
    return "changed"


def diff_device(prior_rows, new_rows, checked, intended=None):
    intended = intended or set()
    prior = {row_id(row): row for row in prior_rows}
    current = {row_id(row): row for row in new_rows}
    old_dev = next((row for row in prior_rows if row.get("kind") == "device"), None)
    new_dev = next((row for row in new_rows if row.get("kind") == "device"), None)
    reboot = False
    if old_dev and new_dev:
        shift = boot_shift_seconds(old_dev.get("last_changed"), new_dev.get("last_changed"))
        if shift is not None and abs(shift) > BOOT_SKEW_SECONDS:
            reboot = reboot_corroborated(old_dev, new_dev, prior_rows, new_rows)
    changed = []
    for key, row in current.items():
        old = prior.get(key)
        extra = {
            "reboot": reboot,
            "intended": row.get("subject") in intended,
        }
        if old is None:
            changed.append(_change(row, "row", None, row["subject"], checked, extra))
            continue
        if row["kind"] == "bgp":
            row["last_changed"] = old.get("last_changed") or checked
        pairs = _material_pairs(old, row, reboot)
        if pairs and row["kind"] == "bgp":
            row["last_changed"] = checked
        for field, before, after, at, pair_extra in pairs:
            merged = dict(extra)
            merged.update(pair_extra)
            changed.append(_change(row, field, before, after, at or checked, merged))
    for key, old in prior.items():
        if key not in current:
            extra = {"intended": old.get("subject") in intended}
            changed.append(_change(old, "row", old.get("subject"), None, checked, extra))
    return changed


def _change(row, field, prior, current, at, extra=None):
    extra = extra or {}
    item = {
        "keys": list(row["keys"]),
        "field": field,
        "prior": prior,
        "current": current,
        "at": at,
        "_kind": row["kind"],
        "_id": row_id(row),
        "_reboot": bool(extra.get("reboot")),
        "_reset": bool(extra.get("reset")),
        "_intended": bool(extra.get("intended")),
    }
    return item


def _material_pairs(old, row, reboot):
    pairs = []
    if row["kind"] == "device":
        shift = boot_shift_seconds(old.get("last_changed"), row.get("last_changed"))
        if shift is not None and abs(shift) > BOOT_SKEW_SECONDS:
            pairs.append(
                (
                    "boot_time",
                    old.get("last_changed"),
                    row.get("last_changed"),
                    row.get("last_changed"),
                    {"reboot": reboot},
                )
            )
        if old.get("software_version") != row.get("software_version"):
            pairs.append(("software_version", old.get("software_version"), row.get("software_version"), None, {}))
        if old.get("unsaved_config") != row.get("unsaved_config"):
            pairs.append(("unsaved_config", old.get("unsaved_config"), row.get("unsaved_config"), None, {}))
        if crossed(old.get("cpu_5m"), row.get("cpu_5m"), CPU_LINE):
            pairs.append(("cpu_5m", old.get("cpu_5m"), row.get("cpu_5m"), None, {}))
        if crossed(old.get("mem_used_pct"), row.get("mem_used_pct"), MEM_LINE):
            pairs.append(("mem_used_pct", old.get("mem_used_pct"), row.get("mem_used_pct"), None, {}))
    elif row["kind"] == "interface":
        if old.get("state") != row.get("state"):
            pairs.append(("state", old.get("state"), row.get("state"), row.get("last_changed"), {}))
        old_admin = old.get("admin_status") or "if-state-up"
        if old_admin != row.get("admin_status"):
            pairs.append(("admin_status", old_admin, row.get("admin_status"), row.get("last_changed"), {}))
        for field in ("input_acl", "output_acl"):
            if old.get(field) != row.get(field):
                pairs.append((field, old.get(field), row.get(field), None, {}))
        for field in ("num_flaps", "in_errors", "in_crc_errors"):
            before = old.get(field)
            after = row.get(field)
            if isinstance(before, int) and isinstance(after, int) and after > before:
                pairs.append((field, before, after, None, {}))
            elif isinstance(before, int) and isinstance(after, int) and after < before:
                pairs.append((field, before, after, None, {"reset": True}))
    elif row["kind"] == "bgp":
        if old.get("state") != row.get("state"):
            pairs.append(("state", old.get("state"), row.get("state"), None, {}))
        if old.get("peer") != row.get("peer"):
            pairs.append(("peer", old.get("peer"), row.get("peer"), None, {}))
        if old.get("prefixes_received") != row.get("prefixes_received"):
            pairs.append(("prefixes_received", old.get("prefixes_received"), row.get("prefixes_received"), None, {}))
        if up_time_shorter(old.get("up_time"), row.get("up_time")):
            pairs.append(("up_time", old.get("up_time"), row.get("up_time"), None, {}))
        if old.get("reset_reason") != row.get("reset_reason") and row.get("reset_reason"):
            pairs.append(("reset_reason", old.get("reset_reason"), row.get("reset_reason"), None, {}))
    return pairs


def _way(item):
    return direction(
        item["_kind"],
        item["field"],
        item["prior"],
        item["current"],
        {"reboot": item.get("_reboot"), "reset": item.get("_reset"), "intended": item.get("_intended")},
    )


def overall_delta(changed, first):
    if first:
        return "first"
    if not changed:
        return "unchanged"
    ways = [_way(item) for item in changed]
    if "worse" in ways:
        return "worse"
    if ways and all(way == "better" for way in ways):
        return "better"
    return "changed"


def plane_status(rows, prior_by_id, changed, intended_by_name=None):
    intended_by_name = intended_by_name or {}
    rebooted = {item["_id"] for item in changed if item["field"] == "boot_time" and item.get("_reboot")}
    increased = {
        item["_id"]
        for item in changed
        if item["field"] in ("num_flaps", "in_errors", "in_crc_errors") and not item.get("_reset")
    }
    missing_bgp = [
        item
        for item in changed
        if item["field"] == "row" and item["_kind"] == "bgp" and item["current"] is None
    ]
    if missing_bgp:
        return "degraded"
    for row in rows:
        intended = intended_by_name.get(row.get("name")) or set()
        if row["kind"] == "device":
            if row_id(row) in rebooted:
                return "degraded"
            if (row.get("cpu_5m") or 0) >= CPU_LINE or (row.get("mem_used_pct") or 0) >= MEM_LINE:
                return "degraded"
        elif row["kind"] == "interface":
            if required_interface_failed(row, row.get("subject") in intended) or row_id(row) in increased:
                return "degraded"
        elif row["kind"] == "bgp" and row.get("state") != "fsm-established":
            return "degraded"
    return "ok"


def metric_for(name, rows, at, prior_rows=None, intended=None):
    intended = intended or set()
    ifaces = [row for row in rows if row["kind"] == "interface"]
    bgps = [row for row in rows if row["kind"] == "bgp"]
    device = next(row for row in rows if row["kind"] == "device")
    in_errors = 0
    discards = 0
    flaps = 0
    for row in ifaces:
        in_errors += (row.get("in_errors") or 0) + (row.get("in_crc_errors") or 0)
        discards += row.get("in_discards") or 0
        flaps += row.get("num_flaps") or 0
    seen = {row.get("subject") for row in bgps}
    missing = sum(
        1
        for row in (prior_rows or [])
        if row.get("kind") == "bgp" and row.get("subject") not in seen
    )
    failed_ifaces = sum(
        1 for row in ifaces if required_interface_failed(row, row.get("subject") in intended)
    )
    return {
        "at": at,
        "scope": f"device:{name}",
        "oper_not_ready": failed_ifaces,
        "bgp_not_established": sum(1 for row in bgps if row.get("state") != "fsm-established") + missing,
        "num_flaps": flaps,
        "in_errors": in_errors,
        "in_discards": discards,
        "cpu_5m_max": device.get("cpu_5m"),
        "mem_used_pct_max": device.get("mem_used_pct"),
    }


def null_metric(name, at):
    return {
        "at": at,
        "scope": f"device:{name}",
        "oper_not_ready": None,
        "bgp_not_established": None,
        "num_flaps": None,
        "in_errors": None,
        "in_discards": None,
        "cpu_5m_max": None,
        "mem_used_pct_max": None,
    }


METRIC_FIELDS = (
    "at",
    "scope",
    "oper_not_ready",
    "bgp_not_established",
    "num_flaps",
    "in_errors",
    "in_discards",
    "cpu_5m_max",
    "mem_used_pct_max",
)


KEY_RE = re.compile(r"^(device|interface|site|service|test|control|incident|change):[^ ]+$")
WATCH_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$")
METRIC_SCOPE_RE = re.compile(r"^(estate|device:[^ ]+)$")
ROW_INT = (
    "cpu_5m", "mem_used_pct", "in_errors", "in_crc_errors", "in_discards",
    "num_flaps", "prefixes_received", "remote_as",
)
ROW_STR = (
    "software_version", "last_reboot_reason", "reason_severity",
    "input_acl", "output_acl", "up_time", "peer",
    "admin_status", "intent", "reset_reason",
)


def _text(value):
    if not isinstance(value, str):
        return None
    value = value.replace("\r", " ").replace("\n", " ").strip()
    return value or None


def keep_prior(rows, fit, label):
    """Coerce inherited rows to the current schema. Drop a row that cannot fit.

    A prior board was written by an older visit. An extra field or a missing
    count on that history must not fail this visit.
    """
    kept = []
    dropped = 0
    for row in rows or []:
        fitted = fit(row)
        if fitted is None:
            dropped += 1
        else:
            kept.append(fitted)
    if dropped:
        print(
            f"iosxe dropped {dropped} prior {label} that did not fit the current schema",
            file=sys.stderr,
        )
    return kept


def fit_metric(row):
    if not isinstance(row, dict):
        return None
    at = _text(row.get("at"))
    scope = _text(row.get("scope"))
    if not at or not scope or METRIC_SCOPE_RE.match(scope) is None:
        return None
    out = {"at": at, "scope": scope}
    for field in METRIC_FIELDS:
        if field in ("at", "scope"):
            continue
        out[field] = None if field not in row else coerce_int(row.get(field))
    return out


def fit_board_row(row):
    if not isinstance(row, dict):
        return None
    name = _text(row.get("name"))
    subject = _text(row.get("subject"))
    kind = row.get("kind")
    last = _text(row.get("last_changed"))
    if not name or not subject or kind not in ("device", "interface", "bgp") or not last:
        return None
    keys = []
    for key in row.get("keys") or []:
        if isinstance(key, str) and KEY_RE.match(key) and key not in keys:
            keys.append(key)
    if not keys:
        return None
    state = row.get("state")
    out = {
        "name": name,
        "kind": kind,
        "subject": subject,
        "keys": keys[:16],
        "state": None if state is None else _text(state),
        "last_changed": last,
    }
    for field in ROW_INT:
        if field in row:
            out[field] = coerce_int(row.get(field))
    for field in ROW_STR:
        if field in row:
            out[field] = _text(row.get(field))
    if "unsaved_config" in row:
        out["unsaved_config"] = coerce_bool(row.get("unsaved_config"))
    return out


def fit_visit(row):
    if not isinstance(row, dict):
        return None
    checked = _text(row.get("checked_at"))
    status = row.get("status")
    coverage = row.get("coverage")
    delta = row.get("delta")
    if not checked or status not in ("ok", "degraded", "unknown"):
        return None
    if coverage not in ("complete", "partial", "unavailable"):
        return None
    if delta not in ("first", "unchanged", "worse", "better", "changed"):
        return None
    if not isinstance(row.get("stamp_written"), bool):
        return None
    watch = row.get("watch_id")
    if watch is not None:
        watch = _text(watch)
        if not watch or WATCH_RE.match(watch) is None:
            return None
    scope = row.get("scope")
    if scope != "all":
        if not isinstance(scope, list) or not scope:
            return None
        if not all(isinstance(item, str) and item.startswith("device:") and " " not in item for item in scope):
            return None
    return {
        "watch_id": watch,
        "checked_at": checked,
        "status": status,
        "coverage": coverage,
        "delta": delta,
        "stamp_written": row["stamp_written"],
        "scope": scope,
    }


def watch_or_none(value):
    text = _text(value) if value is not None else None
    if text and WATCH_RE.match(text):
        return text
    if value:
        print("iosxe ignored a prior watch id that is not the current stamp form", file=sys.stderr)
    return None


def estate_metric(metrics, at):
    usable = [row for row in metrics if row.get("oper_not_ready") is not None]
    if not usable:
        return null_metric("estate", at) | {"scope": "estate"}
    def total(field):
        return sum(row[field] or 0 for row in usable)
    cpus = [row["cpu_5m_max"] for row in usable if row["cpu_5m_max"] is not None]
    mems = [row["mem_used_pct_max"] for row in usable if row["mem_used_pct_max"] is not None]
    return {
        "at": at,
        "scope": "estate",
        "oper_not_ready": total("oper_not_ready"),
        "bgp_not_established": total("bgp_not_established"),
        "num_flaps": total("num_flaps"),
        "in_errors": total("in_errors"),
        "in_discards": total("in_discards"),
        "cpu_5m_max": max(cpus) if cpus else None,
        "mem_used_pct_max": max(mems) if mems else None,
    }


def concerns_for(names, rows_by_name, prior_by_id, changed, intended_by_name=None):
    intended_by_name = intended_by_name or {}
    increased = {}
    rebooted_names = set()
    for item in changed:
        if item["field"] in ("num_flaps", "in_errors", "in_crc_errors") and not item.get("_reset"):
            increased.setdefault(item["_id"][0], True)
        if item["field"] == "boot_time" and item.get("_reboot"):
            rebooted_names.add(item["_id"][0])
    concerns = []
    for name in names:
        rows = rows_by_name.get(name) or []
        device = next((row for row in rows if row["kind"] == "device"), None)
        if device is None:
            continue
        intended = intended_by_name.get(name) or set()
        hot = (device.get("cpu_5m") or 0) >= CPU_LINE or (device.get("mem_used_pct") or 0) >= MEM_LINE
        unsaved = device.get("unsaved_config") is True
        fault = any(
            required_interface_failed(row, row.get("subject") in intended)
            for row in rows
            if row["kind"] == "interface"
        )
        fault = fault or any(row.get("state") != "fsm-established" for row in rows if row["kind"] == "bgp")
        fault = fault or name in increased
        if name in rebooted_names or hot or unsaved or fault:
            concerns.append({"type": "device", "name": name, "source_ref": "inventory/prod.json"})
    return concerns[:8]


def degrades(row, intended=None):
    """A row that is abnormal now. A new row is not abnormal just for being new."""
    intended = intended or set()
    if row["kind"] == "device":
        return (row.get("cpu_5m") or 0) >= CPU_LINE or (row.get("mem_used_pct") or 0) >= MEM_LINE
    if row["kind"] == "interface":
        return required_interface_failed(row, row.get("subject") in intended)
    if row["kind"] == "bgp":
        return row.get("state") != "fsm-established"
    return False


def abnormal(row, changed_fields, intended=None):
    if "boot_time" in changed_fields:
        return True
    if degrades(row, intended):
        return True
    if row["kind"] == "interface":
        return bool(
            changed_fields
            & {"state", "admin_status", "num_flaps", "in_errors", "in_crc_errors", "input_acl", "output_acl"}
        )
    if row["kind"] == "bgp":
        return bool(changed_fields - {"row"})
    return bool(changed_fields - {"row"})


def headline_for(changed, unchanged, coverage, failed, first, nrows):
    if coverage == "unavailable":
        if failed:
            return "IOS-XE RESTCONF failed on every device in scope. Board rows kept as they were."
        return "IOS-XE health visit did not collect. Board rows kept as they were."
    if first:
        text = f"Baseline. {nrows} board rows."
    elif not changed:
        text = f"Partial collection. Failed: {', '.join(failed)}." if failed else "No material change."
    else:
        bits = []
        for item in changed[:6]:
            bits.append(f"{item['keys'][0]} {item['field']} {item['prior']} -> {item['current']}")
        text = "; ".join(bits)
        if len(changed) > 6:
            text += f"; {len(changed) - 6} more"
        text += f". {unchanged} other board rows unchanged."
    return text[:500]


def public_change(item):
    return {key: item[key] for key in ("keys", "field", "prior", "current", "at")}


def next_read(item):
    if item["field"] == "up_time" or (
        item["_kind"] == "bgp" and item["field"] in ("state", "row", "reset_reason", "prefixes_received")
    ):
        return (
            "GET Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors/"
            "neighbor={afi-safi},{vrf-name},{id} fields=connection;session-state"
        )
    if item["field"] == "boot_time":
        return (
            "GET Cisco-IOS-XE-device-hardware-oper:device-hardware-data/"
            "device-hardware/device-system-data fields=boot-time;last-reboot-reason;reason-severity"
        )
    if item["field"] == "unsaved_config":
        return "none (running/startup difference unknown; no verified GET on this visit)"
    if item["_kind"] == "interface":
        return (
            "GET Cisco-IOS-XE-interfaces-oper:interfaces "
            "fields=interface(name;admin-status;oper-status;last-change;"
            "statistics(num-flaps;in-crc-errors;in-errors))"
        )
    return "none"


def ring(items, limit=10):
    return list(items)[-limit:]


def prune_stamps(ws):
    folder = Path(ws) / "health" / "iosxe"
    if not folder.is_dir():
        return
    stamps = sorted(path for path in folder.glob("*.json") if path.is_file())
    for path in stamps[:-10]:
        path.unlink()


def fresh_stamp_id(ws, moment):
    folder = Path(ws) / "health" / "iosxe"
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        name = stamp_name(moment)
        if not (folder / f"{name}.json").exists():
            return name, moment
        moment = moment + timedelta(seconds=1)


def resolve_workspace(given):
    """Directory that contains inventory/prod.json.

    The shell cwd is not stable, so a relative file_explorer often misses.
    This file is attached at <root>/skills/health-device/scripts/, and the
    workspace is <root>/file_explorer.
    """
    raw = Path(given)
    candidates = [raw]
    if not raw.is_absolute():
        candidates.append(Path.cwd() / raw)
        candidates.append(Path.cwd())
    candidates.append(Path(__file__).resolve().parents[3] / "file_explorer")
    seen = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.append(resolved)
        if (resolved / "inventory" / "prod.json").is_file():
            print(f"iosxe workspace={resolved}", file=sys.stderr)
            return resolved
    print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
    print("tried " + ", ".join(str(path) for path in seen), file=sys.stderr)
    return None


def cmd_collect(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    prod = visit_common.load_json(ws, "inventory/prod.json")
    if prod is None:
        print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc)
    topology = visit_common.load_json(ws, "inventory/topology-observed.json")
    board = visit_common.load_board(ws, "iosxe") or {}
    iosxe = board.get("iosxe") or {}
    prior_rows = list(iosxe.get("current") or [])
    first = not prior_rows
    prior_by_id = {row_id(row): row for row in prior_rows}
    scope_arg = args.scope or []
    candidates = restconf_devices(prod)
    prod_names = {device.get("name") for device in prod.get("devices") or [] if device.get("name")}
    ignored = []
    if scope_arg:
        wanted = {item.split(":", 1)[1].lower() for item in scope_arg if item.startswith("device:")}
        selected = []
        matched = set()
        for device in candidates:
            if device["name"].lower() in wanted:
                selected.append(device)
                matched.add(device["name"].lower())
        ignored = [item for item in scope_arg if item.startswith("device:") and item.split(":", 1)[1].lower() not in matched]
        targets = selected
        scope_value = [f"device:{device['name']}" for device in targets]
    else:
        targets = candidates
        scope_value = "all"

    at = checked_at(now)
    collected = {}
    failed = []
    budget = visit_common.Budget(240)
    calls_used = [0]
    for device in targets:
        if budget.exhausted() or calls_used[0] >= MAX_CALLS:
            failed.append(device["name"])
            continue
        payloads, errors = collect_device(device, budget, calls_used)
        if payloads is None:
            failed.append(device["name"])
        else:
            collected[device["name"]] = payloads
    if targets and len(failed) == len(targets):
        coverage = "unavailable"
    elif failed:
        coverage = "partial"
    elif not targets:
        coverage = "unavailable"
    else:
        coverage = "complete"

    peers = address_index(collected, topology, prod_names)
    intended_by_name = {device["name"]: intended_interfaces(prod, device["name"]) for device in targets}
    interval_s = interval_seconds(iosxe.get("last_collected_at"), at)
    new_by_name = {}
    for name, payloads in collected.items():
        prior_device = [row for row in prior_rows if row.get("name") == name]
        new_by_name[name] = build_rows(
            name, payloads, peers, at, prior_device, intended_by_name.get(name) or set()
        )

    changed = []
    if coverage != "unavailable":
        for name, rows in new_by_name.items():
            prior_device = [row for row in prior_rows if row.get("name") == name]
            changed.extend(
                diff_device(prior_device, rows, at, intended_by_name.get(name) or set())
            )

    current_rows = []
    seen_devices = set()
    for device in targets:
        name = device["name"]
        seen_devices.add(name)
        if name in new_by_name:
            current_rows.extend(new_by_name[name])
        else:
            current_rows.extend(
                keep_prior(
                    [row for row in prior_rows if row.get("name") == name],
                    fit_board_row,
                    "board rows",
                )
            )
    current_rows.extend(
        keep_prior(
            [row for row in prior_rows if row.get("name") not in seen_devices],
            fit_board_row,
            "board rows",
        )
    )
    if len(current_rows) > 120:
        print(f"iosxe board rows {len(current_rows)} capped at 120", file=sys.stderr)
        current_rows = current_rows[:120]

    status = "unknown" if coverage == "unavailable" else plane_status(
        [row for rows in new_by_name.values() for row in rows],
        prior_by_id,
        changed,
        intended_by_name,
    )
    delta = "unchanged" if coverage == "unavailable" else overall_delta(changed, first and coverage == "complete")
    if first and coverage == "partial":
        delta = "first" if not prior_rows else overall_delta(changed, False)

    metrics = []
    for device in targets:
        name = device["name"]
        if name in new_by_name:
            metrics.append(
                metric_for(
                    name,
                    new_by_name[name],
                    at,
                    [row for row in prior_rows if row.get("name") == name],
                    intended_by_name.get(name) or set(),
                )
            )
        else:
            metrics.append(null_metric(name, at))
    if not metrics:
        metrics = [estate_metric([], at)]

    fields_by_id = {}
    for item in changed:
        fields_by_id.setdefault(item["_id"], set()).add(item["field"])
    reading_rows = []
    if coverage != "unavailable":
        for row in current_rows:
            if row.get("name") not in new_by_name:
                continue
            fields = fields_by_id.get(row_id(row), set())
            if first or fields or abnormal(row, fields, intended_by_name.get(row.get("name"))):
                reading_rows.append(row)
    readings_truncated = len(reading_rows) > READINGS_CAP
    if readings_truncated:
        def rank_reading(row):
            fields = fields_by_id.get(row_id(row), set())
            intended = intended_by_name.get(row.get("name"))
            return (0 if fields or abnormal(row, fields, intended) else 1, row["name"], row["kind"], row["subject"])
        reading_rows = sorted(reading_rows, key=rank_reading)[:READINGS_CAP]

    readings = []
    for row in reading_rows:
        item = dict(row)
        fields = fields_by_id.get(row_id(row), set())
        if first and not degrades(row, intended_by_name.get(row.get("name"))):
            item["note"] = "Baseline."
        readings.append(item)

    unchanged = None if coverage == "unavailable" else sum(1 for row in current_rows if row_id(row) not in {row_id(row) for row in reading_rows})
    changed.sort(key=lambda item: (0 if _way(item) == "worse" else 1))
    changed_truncated = len(changed) > CHANGED_CAP
    changed = changed[:CHANGED_CAP]
    delta = "unchanged" if coverage == "unavailable" else overall_delta(changed, first and not prior_rows)

    write_stamp = first or bool(changed) or coverage != "complete"
    prior_watch = iosxe.get("last_visit_id")
    baseline = watch_or_none(iosxe.get("baseline_visit_id"))
    watch = None
    stamp_rel = None
    if write_stamp:
        watch, moment = fresh_stamp_id(ws, now)
        at = checked_at(moment)
        for row in metrics:
            row["at"] = at
        stamp = {
            "keys": union_keys(readings) or union_keys(current_rows),
            "schema": "health-iosxe-check/v6",
            "source": "iosxe",
            "watch_id": watch,
            "checked_at": at,
            "ok": status == "ok",
            "status": status if status != "unknown" else "unknown",
            "headline": headline_for(changed, unchanged if unchanged is not None else 0, coverage, failed, first, len(current_rows)),
            "window": "live",
            "scope": scope_value if scope_value else "all",
            "coverage": {"state": coverage, "detail": _detail(collected, failed)},
            "metrics": metrics,
            "readings": readings,
            "unchanged": unchanged,
            "baseline_ref": None if first else (f"health/iosxe/{baseline}.json" if baseline else None),
            "vs_prior": {
                "prior_watch_id": None if first else prior_watch,
                "delta": "first" if first else delta,
                "changed": [public_change(item) for item in ([] if first else changed)],
            },
        }
        concern_rows = concerns_for(
            list(new_by_name), new_by_name, prior_by_id, [] if first else changed, intended_by_name
        )
        if concern_rows:
            stamp["concerns"] = concern_rows
        if first:
            stamp["vs_prior"]["delta"] = "first"
            stamp["vs_prior"]["changed"] = []
            stamp["vs_prior"]["prior_watch_id"] = None
        try:
            visit_common.validate(stamp, CHECK_SCHEMA)
        except ValueError as exc:
            print(f"stamp schema: {exc}", file=sys.stderr)
            return 1
        stamp_rel = f"health/iosxe/{watch}.json"
        path = Path(ws) / stamp_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        prune_stamps(ws)
        if first:
            baseline = watch

    visit_delta = "first" if first and write_stamp else delta
    visit = {
        "watch_id": watch if write_stamp else None,
        "checked_at": at,
        "status": status if status != "unknown" else "unknown",
        "coverage": coverage if coverage != "not_requested" else "unavailable",
        "delta": visit_delta if visit_delta in ("first", "unchanged", "worse", "better", "changed") else "unchanged",
        "stamp_written": bool(write_stamp),
        "scope": scope_value if scope_value else "all",
    }
    series = keep_prior(iosxe.get("series") or [], fit_metric, "series rows")
    series.append(estate_metric(metrics, at))
    visits = keep_prior(iosxe.get("visits") or [], fit_visit, "visit rows")
    visits.append(visit)
    new_board = {
        "keys": union_keys(current_rows),
        "schema": "health-metadata-iosxe/v5",
        "updated_at": at,
        "source_agent": "health-device",
        "iosxe": {
            "last_visit_id": watch if write_stamp else watch_or_none(prior_watch),
            "last_collected_at": at,
            "baseline_visit_id": watch if first and write_stamp else watch_or_none(baseline),
            "current": current_rows[:120],
            "series": ring(series),
            "visits": ring(visits),
        },
    }
    try:
        visit_common.validate(new_board, BOARD_SCHEMA)
    except ValueError as exc:
        print(f"board schema: {exc}", file=sys.stderr)
        return 1
    try:
        visit_common.save_board(ws, "iosxe", new_board)
    except OSError as exc:
        print(f"board write: {exc}", file=sys.stderr)
        return 1

    needs = []
    if write_stamp and not first:
        for item in changed:
            note = {
                "keys": item["keys"],
                "field": item["field"],
                "prior": item["prior"],
                "current": item["current"],
                "interval_s": interval_s,
                "impact": "unknown" if item["field"] in ("boot_time", "up_time", "unsaved_config") and not item.get("_reboot") else None,
                "next": next_read(item),
            }
            if item["field"] == "boot_time":
                note["kind"] = "reload" if item.get("_reboot") else "timestamp_correction"
            if item["field"] == "up_time":
                note["kind"] = "session_reset"
            if item["_kind"] == "interface":
                far = far_of(topology, item["_id"][0], item["_id"][2])
                if far:
                    note["far"] = far
            if item.get("_reset"):
                note["counter_reset"] = True
            needs.append({key: value for key, value in note.items() if value is not None})
    payload = {
        "plane": "iosxe",
        "watch_id": watch if write_stamp else None,
        "stamp": stamp_rel,
        "status": status,
        "coverage": coverage,
        "scope": scope_value if scope_value else "all",
        "delta": "first" if first and write_stamp else delta,
        "changed_count": 0 if first else len(changed),
        "unchanged": unchanged,
        "degraded": status == "degraded",
        "needs_note": needs,
        "unresolved": [],
        "partial": coverage == "partial",
        "board_rows": len(current_rows),
        "last_visit_id": new_board["iosxe"]["last_visit_id"],
    }
    if ignored:
        payload["ignored"] = ignored
    if changed_truncated:
        payload["changed_truncated"] = True
    if readings_truncated:
        payload["readings_truncated"] = True
    if failed:
        payload["failed"] = failed
    print(visit_common.summary(payload))
    return 0


def _detail(collected, failed):
    if not collected and failed:
        return "RESTCONF failed after retry"
    text = f"system-data, cpu, memory, interfaces, bgp on {len(collected)} devices"
    if failed:
        text += "; failed: " + ", ".join(failed)
    return text[:400]


def cmd_annotate(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    notes = {}
    for item in args.note or []:
        if "=" not in item:
            print("note must be <keys joined by +>=<text>", file=sys.stderr)
            return 1
        key, text = item.split("=", 1)
        notes[key.rstrip(">")] = text
    try:
        stamp_path = Path(args.stamp) if str(args.stamp).startswith("/") else ws / args.stamp
        visit_common.annotate(stamp_path, args.headline, notes, CHECK_SCHEMA)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(visit_common.summary({"plane": "iosxe", "stamp": args.stamp, "annotated": True}))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="IOS-XE health visit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--workspace", required=True)
    collect.add_argument("--scope", action="append", default=[])
    note = sub.add_parser("annotate")
    note.add_argument("--workspace", required=True)
    note.add_argument("--stamp", required=True)
    note.add_argument("--headline", required=True)
    note.add_argument("--note", action="append", default=[])
    args = parser.parse_args(argv)
    if args.cmd == "collect":
        return cmd_collect(args)
    return cmd_annotate(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
