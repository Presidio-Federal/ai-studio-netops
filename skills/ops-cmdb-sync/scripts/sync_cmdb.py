#!/usr/bin/env python3
"""Sync one lab device. The box is the authority for hostname and address.

sync runs under execution_type mcp_orchestration. It reads inventory,
calls MCP, and writes state/cmdb-sync.json. The model passes the device
name from the task line. It does not reconcile the records itself.

  python3 <skill>/scripts/sync_cmdb.py sync --workspace <file_explorer> \\
      --device <name> --signal netbox|servicenow|unknown

Scope is the lab on inventory/prod.json: netbox.tenant, else source.name.
A device that is not in that file is not queried. NetBox find always
sends that tenant. ServiceNow is one exact-name query, limit 5, network
CI classes only. Neither call lists another inventory.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
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

SNOW_FIELDS = (
    "name,sys_id,sys_class_name,serial_number,asset_tag,"
    "ip_address,install_status,operational_status"
)
SNOW_CLASSES = (
    "cmdb_ci_netgear",
    "cmdb_ci_ip_router",
    "cmdb_ci_ip_switch",
    "cmdb_ci_ip_firewall",
)
SNOW_LABELS = {"Network Gear", "IP Router", "IP Switch", "IP Firewall"}
HOST_PATH = "Cisco-IOS-XE-native:native/hostname"
IFACE_PATH = "Cisco-IOS-XE-native:native/interface"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def op_id():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def load_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def cell(value):
    if isinstance(value, dict):
        shown = value.get("display")
        if shown not in (None, ""):
            return str(shown)
        stored = value.get("value")
        return "" if stored is None else str(stored)
    if value is None:
        return ""
    return str(value)


def sys_id_of(value):
    if isinstance(value, dict):
        return str(value.get("value") or value.get("sys_id") or "") or None
    if value in (None, ""):
        return None
    return str(value)


def host_of(address):
    text = cell(address).strip()
    if not text:
        return ""
    return text.split("/")[0].strip()


def prefix_of(address):
    text = cell(address).strip()
    parts = text.split("/")
    if len(parts) == 2 and parts[1].isdigit():
        return parts[1]
    return None


def tenant_name(record):
    tenant = record.get("tenant") if isinstance(record, dict) else None
    if isinstance(tenant, dict):
        return str(tenant.get("slug") or tenant.get("name") or "")
    if isinstance(tenant, str):
        return tenant
    return ""


def tag_slugs(record):
    slugs = []
    for tag in record.get("tags") or []:
        if isinstance(tag, dict) and tag.get("slug"):
            slugs.append(str(tag["slug"]))
        elif isinstance(tag, str):
            slugs.append(tag)
    return slugs


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def hostname_of(payload):
    for node in walk(payload):
        for key, value in node.items():
            if str(key).endswith("hostname") and isinstance(value, str) and value.strip():
                return value.strip()
    return None


def primary_on(node):
    ip = node.get("ip")
    if not isinstance(ip, dict):
        return None
    address = ip.get("address")
    if not isinstance(address, dict):
        return None
    primary = address.get("primary")
    if isinstance(primary, dict):
        found = primary.get("address")
        if isinstance(found, str) and found.strip():
            return found.strip()
    return None


def shutdown(node):
    flag = node.get("shutdown")
    return flag in (True, "true", [None], {})


def interface_address(payload):
    """Loopback0 with a static IPv4, else the first static IPv4."""
    loopback = None
    first = None
    for node in walk(payload):
        for key, value in node.items():
            kind = str(key).split(":")[-1]
            rows = value if isinstance(value, list) else None
            if rows is None or kind not in ("Loopback", "GigabitEthernet", "TenGigabitEthernet", "Vlan"):
                continue
            for row in rows:
                if not isinstance(row, dict) or shutdown(row):
                    continue
                addr = primary_on(row)
                if not addr or addr.lower() == "dhcp":
                    continue
                name = str(row.get("name") or "")
                if kind == "Loopback" and name in ("0", "Loopback0"):
                    loopback = ("Loopback0", host_of(addr))
                elif first is None:
                    label = name if name.startswith(kind) else f"{kind}{name}"
                    first = (label, host_of(addr))
    return loopback or first or (None, None)


def inner_dict(envelope):
    if not isinstance(envelope, dict) or not envelope.get("success"):
        err = None if not isinstance(envelope, dict) else envelope.get("error")
        return None, err or "success false"
    outer = envelope.get("result")
    raw = outer[0] if isinstance(outer, list) and outer else outer
    try:
        inner = json.loads(raw, strict=False) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return None, "result[0] not json"
    if isinstance(inner, list) and inner and isinstance(inner[0], dict):
        inner = inner[0]
    if not isinstance(inner, dict):
        return None, "inner envelope not an object"
    if inner.get("ok") is False:
        return None, str(inner.get("error") or "ok false")[:200]
    return inner, None


def object_rows(inner):
    for key in ("results", "rows", "objects"):
        rows = inner.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    data = inner.get("data") if isinstance(inner.get("data"), (dict, list)) else inner.get("result")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict) and ("id" in data or "name" in data):
        return [data]
    if "id" in inner or "name" in inner:
        return [inner]
    return None


def call_tool(tool, args):
    envelope = visit_common.mcp_call(tool, args, retries=1)
    inner, err = inner_dict(envelope)
    return inner, err


def lab_tenant(prod):
    netbox = prod.get("netbox") if isinstance(prod.get("netbox"), dict) else {}
    tenant = str(netbox.get("tenant") or "").strip()
    if tenant:
        return tenant
    source = prod.get("source") if isinstance(prod.get("source"), dict) else {}
    return str(source.get("name") or "").strip()


def prod_device(prod, name):
    for device in prod.get("devices") or []:
        if isinstance(device, dict) and device.get("name") == name:
            return device
    return None


def restconf_of(device):
    access = device.get("access") if isinstance(device.get("access"), dict) else {}
    rest = access.get("restconf")
    if not isinstance(rest, dict):
        return None, None
    host = rest.get("host")
    port = rest.get("port")
    if not host or port in (None, ""):
        return None, None
    try:
        return str(host), int(port)
    except (TypeError, ValueError):
        return None, None


def snap_id(snap, name):
    if not isinstance(snap, dict):
        return None
    for device in snap.get("devices") or []:
        if isinstance(device, dict) and device.get("name") == name and device.get("id") is not None:
            try:
                return int(device["id"])
            except (TypeError, ValueError):
                return None
    return None


def blank(record):
    started = now_iso()
    return {
        "schema": "cmdb-sync-state/v1",
        "updated_at": started,
        "source_agent": "ops-cmdb-sync",
        "status": "failed",
        "headline": "failed",
        "next_action": None,
        "operation_id": op_id(),
        "operation": "sync",
        "started_at": started,
        "completed_at": started,
        "signal": "unknown",
        "result": "failed",
        "device": {"name": "", "netbox_id": None, "servicenow_sys_id": None},
        "device_values": {"hostname": None, "primary_ipv4": None, "interface": None},
        "compared": [],
        "wrote": "none",
        "gaps": [],
        "relations": [],
        "keys": [],
    }


def finish(workspace, state, result, gaps):
    state["result"] = result
    state["gaps"] = gaps
    state["status"] = {"in_sync": "ok", "updated": "ok", "gaps": "gaps", "failed": "failed"}[result]
    state["completed_at"] = now_iso()
    state["updated_at"] = state["completed_at"]
    name = state["device"]["name"] or "device"
    state["headline"] = f"{result} {name}: {', '.join(gaps) if gaps else 'address matches'}"
    if result in ("in_sync", "updated"):
        state["next_action"] = None
    elif gaps:
        state["next_action"] = gaps[0]
    path = workspace / "state" / "cmdb-sync.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")
    summary = {
        "result": result,
        "device": state["device"]["name"],
        "wrote": state["wrote"],
        "address": state["device_values"]["primary_ipv4"],
        "gaps": gaps,
        "path": "state/cmdb-sync.json",
    }
    print(json.dumps(summary, separators=(",", ":")))
    return 0


def accept_lab(record, tenant):
    found = tenant_name(record)
    if found != tenant:
        return False
    return f"{tenant}-simulate" in tag_slugs(record)


def primary_ip(record):
    primary = record.get("primary_ip4")
    if isinstance(primary, dict):
        return primary.get("id"), cell(primary.get("address"))
    if isinstance(primary, int):
        return primary, ""
    return None, ""


def reported(netbox, snow):
    install = cell(snow.get("install_status")) if snow else ""
    operational = cell(snow.get("operational_status")) if snow else ""
    status = f"{install}/{operational}" if install or operational else ""
    dtype = netbox.get("device_type") if isinstance(netbox.get("device_type"), dict) else {}
    site = netbox.get("site") if isinstance(netbox.get("site"), dict) else {}
    rows = [
        ("serial", cell(netbox.get("serial")), cell(snow.get("serial_number")) if snow else ""),
        ("asset_tag", cell(netbox.get("asset_tag")), cell(snow.get("asset_tag")) if snow else ""),
        ("status", cell((netbox.get("status") or {}).get("value") if isinstance(netbox.get("status"), dict) else netbox.get("status")), status),
        ("model", cell(dtype.get("slug")), ""),
        ("site", cell(site.get("name")), ""),
    ]
    return [
        {"field": field, "device": None, "netbox": left, "servicenow": right, "verdict": "reported"}
        for field, left, right in rows
    ]


def sync(workspace, device_name, signal):
    state = blank(workspace)
    state["signal"] = signal if signal in ("netbox", "servicenow", "unknown") else "unknown"
    state["device"]["name"] = device_name
    prod = load_json(workspace / "inventory" / "prod.json")
    if not isinstance(prod, dict):
        state["gaps"] = ["no prod.json"]
        return finish(workspace, state, "failed", state["gaps"])
    tenant = lab_tenant(prod)
    device = prod_device(prod, device_name)
    if not tenant or device is None:
        return finish(workspace, state, "failed", ["outside lab inventory"])
    host, port = restconf_of(device)
    if not host:
        return finish(workspace, state, "failed", ["no restconf"])

    budget = visit_common.Budget()
    if budget.exhausted():
        return finish(workspace, state, "failed", ["budget"])

    hostname_payload, hostname_err = visit_common.unwrap_iosxe(
        visit_common.mcp_call(
            "iosxe_restconf_get",
            {"path": HOST_PATH, "host": host, "port": port},
            retries=1,
        )
    )
    hostname = hostname_of(hostname_payload) if hostname_err is None else None
    state["device_values"]["hostname"] = hostname
    if hostname != device_name:
        return finish(workspace, state, "failed", ["hostname mismatch"])

    iface_payload, iface_err = visit_common.unwrap_iosxe(
        visit_common.mcp_call(
            "iosxe_restconf_get",
            {"path": IFACE_PATH, "host": host, "port": port},
            retries=1,
        )
    )
    if iface_err and "404" in str(iface_err):
        call_tool("iosxe_get_platform_and_yang", {"host": host, "port": port, "list_modules": True})
        iface_payload, iface_err = visit_common.unwrap_iosxe(
            visit_common.mcp_call(
                "iosxe_restconf_get",
                {"path": IFACE_PATH, "host": host, "port": port},
                retries=0,
            )
        )
    interface, address = (None, None) if iface_err else interface_address(iface_payload)
    state["device_values"]["interface"] = interface
    state["device_values"]["primary_ipv4"] = address
    if hostname == device_name:
        state["keys"] = [f"device:{device_name}"]
        if interface:
            state["keys"].append(f"interface:{device_name}/{interface}")

    snap = load_json(workspace / "inventory" / "infra-sot.json")
    record = None
    object_id = snap_id(snap, device_name)
    if object_id is not None:
        inner, err = call_tool("netbox_get", {"object_type": "device", "object_id": object_id})
        rows = object_rows(inner) if err is None and inner else None
        record = rows[0] if rows else None
        if record is not None and not accept_lab(record, tenant):
            return finish(workspace, state, "failed", ["outside lab tenant"])
    if record is None:
        inner, err = call_tool(
            "netbox_find",
            {"object_type": "device", "name": device_name, "tenant": tenant, "limit": 5},
        )
        rows = object_rows(inner) if err is None and inner else None
        if rows is None:
            return finish(workspace, state, "failed", [err or "netbox unread"])
        if len(rows) > 5:
            return finish(workspace, state, "failed", ["unscoped netbox result"])
        matched = [row for row in rows if row.get("name") == device_name and accept_lab(row, tenant)]
        if len(matched) != 1:
            return finish(workspace, state, "failed", ["no netbox device" if not matched else "netbox name not unique"])
        record = matched[0]

    state["device"]["netbox_id"] = record.get("id") if isinstance(record.get("id"), int) else None
    ip_id, ip_address = primary_ip(record)
    if ip_id is not None and not ip_address:
        ip_inner, ip_err = call_tool("netbox_get", {"object_type": "ip_address", "object_id": ip_id})
        ip_rows = object_rows(ip_inner) if ip_err is None and ip_inner else None
        if ip_rows:
            ip_address = cell(ip_rows[0].get("address"))

    query = (
        f"name={device_name}^comments={tenant}^sys_class_nameIN{','.join(SNOW_CLASSES)}"
    )
    snow_payload, snow_err = visit_common.unwrap_snow(
        visit_common.mcp_call(
            "snow_query_table",
            {"table": "cmdb_ci", "query": query, "fields": SNOW_FIELDS, "limit": 5},
            retries=1,
        )
    )
    if snow_err:
        return finish(workspace, state, "failed", [f"servicenow unread: {snow_err}"[:180]])
    snow_rows = []
    for row in snow_payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        if cell(row.get("name")) != device_name:
            continue
        kind = cell(row.get("sys_class_name"))
        if kind not in SNOW_CLASSES and kind not in SNOW_LABELS:
            continue
        snow_rows.append(row)
    if len(snow_rows) > 1:
        return finish(workspace, state, "failed", ["servicenow name not unique"])
    snow = snow_rows[0] if snow_rows else None
    if snow:
        state["device"]["servicenow_sys_id"] = sys_id_of(snow.get("sys_id"))

    gaps = []
    compared = []
    wrote = "none"
    netbox_host = host_of(ip_address)
    snow_host = host_of(snow.get("ip_address")) if snow else ""
    if not address:
        gaps.append("no address on device")
        verdict = "gap"
    elif netbox_host == address:
        verdict = "match"
    elif ip_id is None or not prefix_of(ip_address):
        gaps.append("no netbox primary")
        verdict = "gap"
    else:
        new_address = f"{address}/{prefix_of(ip_address)}"
        inner, err = call_tool(
            "netbox_manage",
            {
                "action": "update",
                "object_type": "ip_address",
                "data": {"id": ip_id, "address": new_address},
            },
        )
        check, check_err = (None, err or "netbox update failed")
        if err is None and inner is not None:
            check, check_err = call_tool(
                "netbox_get",
                {"object_type": "ip_address", "object_id": ip_id},
            )
        checked = object_rows(check) if check_err is None and check else None
        if not checked or host_of(checked[0].get("address")) != address:
            gaps.append("netbox update failed")
            verdict = "gap"
        else:
            wrote = "netbox"
            verdict = "updated"
            netbox_host = address
            pointer = record.get("primary_ip4")
            pointer_id = pointer.get("id") if isinstance(pointer, dict) else pointer
            if pointer_id != ip_id and isinstance(record.get("id"), int):
                call_tool(
                    "netbox_manage",
                    {
                        "action": "update",
                        "object_type": "device",
                        "data": {"id": record["id"], "primary_ip4": ip_id},
                    },
                )
    if snow is None:
        gaps.append("no servicenow ci")
    elif address and snow_host != address:
        gaps.append("servicenow address differs")
        if verdict == "match":
            verdict = "gap"
    compared.append(
        {
            "field": "primary_ipv4",
            "device": address,
            "netbox": netbox_host,
            "servicenow": snow_host,
            "verdict": verdict,
        }
    )
    if snow is not None or record is not None:
        compared.extend(reported(record, snow))
    # de-duplicate gap strings, keep order
    seen = []
    for gap in gaps:
        if gap not in seen:
            seen.append(gap)
    state["compared"] = compared
    state["wrote"] = wrote
    if seen:
        result = "gaps"
    elif wrote == "netbox":
        result = "updated"
    else:
        result = "in_sync"
    return finish(workspace, state, result, seen)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--signal", default="unknown")
    args = parser.parse_args()
    if args.command != "sync":
        print('{"error":"unknown command"}', file=sys.stderr)
        return 2
    name = args.device.strip()
    if not name or any(ch.isspace() for ch in name):
        print('{"error":"device name is one token"}', file=sys.stderr)
        return 2
    started = time.monotonic()
    code = sync(Path(args.workspace), name, args.signal.strip().lower())
    print(f"sync elapsed_s={time.monotonic() - started:.3f}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
