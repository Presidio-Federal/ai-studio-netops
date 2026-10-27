#!/usr/bin/env python3
"""Apply one web allow-list on IOS-XE or FTD.

apply runs under execution_type mcp_orchestration. The frontier task
names the device. This script reads that device's PAT port from
inventory/prod.json, pushes the list, and writes state/firewall.json.
It does not take a username or password.

  python3 <skill>/scripts/apply_rule.py apply --workspace <file_explorer> \\
      --device <name> --destination any --permit-ports 80,443,8080

--remove deletes that same list. --deploy is FTD only and deploys every
pending change on that firewall.
"""
import argparse
import ipaddress
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace-handoff" / "scripts"))
try:
    import visit_common
except ImportError:
    print(
        '{"error": "visit_common missing; attach the workspace-handoff skill"}',
        file=sys.stderr,
    )
    sys.exit(1)

SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "firewall-state.schema.json"
LIST_NAME = "SCAN-ALLOW-WEB"
ACL_PATH = "Cisco-IOS-XE-native:native/ip/access-list"
ACL_DELETE = "Cisco-IOS-XE-native:native/ip/access-list/Cisco-IOS-XE-acl:extended=" + LIST_NAME


def stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def iso(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tool(name, args):
    inner, err = visit_common._github_tool_dict(visit_common.mcp_call(name, args))
    if err:
        return None, err
    if inner.get("ok") is not True:
        return None, str(inner.get("error") or "ok false")[:200]
    return inner, None


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def find_device(inventory, name):
    for device in (inventory or {}).get("devices") or []:
        if isinstance(device, dict) and device.get("name") == name:
            return device
    return None


def side_of(device):
    platform = (device.get("platform") or "").lower()
    node = ((device.get("source_metadata") or {}).get("node_definition") or "").lower()
    if platform == "ftd" or node == "ftdv":
        return "ftd"
    if platform == "iosxe":
        return "iosxe"
    return None


def access_of(device):
    rest = (device.get("access") or {}).get("restconf")
    if not isinstance(rest, dict):
        return None, None
    host = rest.get("host")
    port = rest.get("port")
    if not host or not isinstance(port, int):
        return None, None
    return str(host), port


def ios_payload(ports, destination):
    rules = []
    seq = 10
    for port in ports:
        ace = {
            "action": "permit",
            "protocol": "tcp",
            "any": [None],
            "dst-any": [None],
            "dst-eq": int(port),
        }
        if destination != "any":
            ace.pop("dst-any")
            ace["dst-host"] = destination
        rules.append({"sequence": str(seq), "ace-rule": ace})
        seq += 10
    deny = {"action": "deny", "protocol": "ip", "any": [None], "dst-any": [None]}
    if destination != "any":
        deny.pop("dst-any")
        deny["dst-host"] = destination
    rules.append({"sequence": str(seq), "ace-rule": deny})
    return {
        "Cisco-IOS-XE-native:access-list": {
            "Cisco-IOS-XE-acl:extended": [{
                "name": LIST_NAME,
                "access-list-seq-rule": rules,
            }]
        }
    }


def ios_has_list(body):
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    acl = data.get("Cisco-IOS-XE-native:access-list") if isinstance(data, dict) else None
    if not isinstance(acl, dict):
        return False
    for item in acl.get("Cisco-IOS-XE-acl:extended") or []:
        if isinstance(item, dict) and item.get("name") == LIST_NAME:
            return True
    return False


def apply_ios(host, port, ports, destination, remove):
    target = {"host": host, "port": port}
    if remove:
        deleted, err = tool("iosxe_restconf_delete", {"path": ACL_DELETE, **target})
        if err:
            return None, err
        tool("iosxe_save_config", target)
        return {"removed": True, "verified": True}, None
    current, err = tool("iosxe_restconf_get", {"path": ACL_PATH, **target})
    if err:
        return None, err
    if ios_has_list(current):
        _, err = tool("iosxe_restconf_delete", {"path": ACL_DELETE, **target})
        if err:
            return None, err
    _, err = tool("iosxe_restconf_patch", {
        "path": ACL_PATH,
        "payload": ios_payload(ports, destination),
        **target,
    })
    if err:
        return None, err
    checked, err = tool("iosxe_restconf_get", {"path": ACL_PATH, **target})
    if err or not ios_has_list(checked or {}):
        return None, err or "allow-list missing after write"
    tool("iosxe_save_config", target)
    return {"removed": False, "verified": True}, None


def ftd_items(body):
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    return items if isinstance(items, list) else []


def ftd_ports(host, port, wanted):
    body, err = tool("ftd_get", {
        "path": "object/tcpports",
        "host": host,
        "port": port,
        "params": {"limit": "100"},
    })
    if err:
        return None, err
    found = {}
    for item in ftd_items(body):
        if not isinstance(item, dict):
            continue
        if str(item.get("port")) in wanted and item.get("id"):
            found[str(item["port"])] = {
                "id": item["id"],
                "type": "tcpportobject",
                "name": item.get("name"),
            }
    missing = [port_no for port_no in wanted if port_no not in found]
    return found, None if not missing else "missing tcp port object " + ",".join(missing)


def ftd_open_permits(rules):
    names = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("ruleAction") != "PERMIT" or rule.get("name") == LIST_NAME:
            continue
        if not rule.get("destinationPorts"):
            names.append(rule.get("name") or "unnamed")
    return names


def apply_ftd(host, port, ports, remove, deploy):
    target = {"host": host, "port": port}
    listed, err = tool("ftd_get", {"path": "policy/accesspolicies", **target})
    if err:
        return None, err
    policies = ftd_items(listed)
    if not policies or not policies[0].get("id"):
        return None, "no access policy"
    policy_id = policies[0]["id"]
    rules_path = f"policy/accesspolicies/{policy_id}/accessrules"
    rules_body, err = tool("ftd_get", {"path": rules_path, "params": {"limit": "100"}, **target})
    if err:
        return None, err
    rules = ftd_items(rules_body)
    existing = next((rule for rule in rules if isinstance(rule, dict) and rule.get("name") == LIST_NAME), None)
    if remove:
        if not existing:
            return {"removed": True, "verified": True, "pending": None, "open_permits": []}, None
        _, err = tool("ftd_delete", {"path": f"{rules_path}/{existing['id']}", **target})
        if err:
            return None, err
        pending, _ = tool("ftd_pending_changes", target)
        count = None if not isinstance(pending, dict) else pending.get("count")
        return {"removed": True, "verified": True, "pending": count, "open_permits": []}, None
    if existing:
        _, err = tool("ftd_delete", {"path": f"{rules_path}/{existing['id']}", **target})
        if err:
            return None, err
    refs, err = ftd_ports(host, port, [str(port_no) for port_no in ports])
    if err:
        return None, err
    payload = {
        "name": LIST_NAME,
        "type": "accessrule",
        "ruleAction": "PERMIT",
        "eventLogAction": "LOG_NONE",
        "destinationPorts": [refs[str(port_no)] for port_no in ports],
        "sourceNetworks": [],
        "destinationNetworks": [],
        "sourcePorts": [],
        "sourceZones": [],
        "destinationZones": [],
    }
    created, err = tool("ftd_post", {"path": rules_path, "payload": payload, **target})
    if err:
        return None, err
    data = created.get("data") if isinstance(created.get("data"), dict) else created
    if data.get("name") != LIST_NAME:
        return None, "allow-list missing after write"
    pending, _ = tool("ftd_pending_changes", target)
    count = None if not isinstance(pending, dict) else pending.get("count")
    if deploy:
        deployed, err = tool("ftd_deploy", {"confirm": True, **target})
        if err:
            return None, err
        state = deployed.get("state") if isinstance(deployed, dict) else None
        if state != "DEPLOYED":
            return None, "deploy state " + str(state or "unknown")
        return {"removed": False, "verified": True, "pending": 0, "deployed": True, "open_permits": ftd_open_permits(rules)}, None
    return {
        "removed": False,
        "verified": True,
        "pending": count,
        "deployed": False,
        "open_permits": ftd_open_permits(rules),
    }, None


def write_state(ws, started, device, side, result, pending, gaps, headline, ports, destination, next_action):
    finished = datetime.now(timezone.utc)
    body = {
        "schema": "firewall-state/v1",
        "updated_at": iso(finished),
        "source_agent": "ops-firewall",
        "status": "failed" if result == "failed" else ("gaps" if gaps else "ok"),
        "headline": headline,
        "next_action": next_action,
        "operation_id": stamp(started),
        "operation": "write" if result != "read" else "read",
        "started_at": iso(started),
        "completed_at": iso(finished),
        "device": {"name": device},
        "side": side or "iosxe",
        "action": "write",
        "result": result,
        "pending_count": pending,
        "permit_ports": [str(port) for port in ports],
        "destination": destination,
        "list_name": LIST_NAME,
        "gaps": gaps,
        "relations": [],
        "keys": [f"device:{device}"] if device else [],
    }
    if side not in ("iosxe", "ftd"):
        body["side"] = "iosxe"
    visit_common.validate(body, SCHEMA)
    save_json(Path(ws) / "state" / "firewall.json", body)


def emit(payload):
    print(visit_common.summary(payload))


def cmd_apply(args):
    started = datetime.now(timezone.utc)
    ws = Path(args.workspace)
    if not ws.is_dir():
        print("workspace is not a directory", file=sys.stderr)
        return 1
    ports = [part.strip() for part in args.permit_ports.split(",") if part.strip()]
    destination = (args.destination or "any").strip() or "any"
    if destination != "any":
        try:
            ipaddress.ip_address(destination)
        except ValueError:
            emit({"result": "blocked", "device": args.device, "gaps": ["destination must be any or one host address"]})
            return 0
    inventory = visit_common.load_json(ws, "inventory/prod.json")
    device = find_device(inventory, args.device)
    if device is None:
        emit({"result": "blocked", "device": args.device, "gaps": ["device not in inventory/prod.json"]})
        return 0
    expires = parse_time(inventory.get("expires_at"))
    if expires is not None and datetime.now(timezone.utc) >= expires:
        write_state(ws, started, args.device, side_of(device), "blocked", None, ["inventory stale"], f"{args.device}: inventory stale", ports, destination, "Refresh the prod inventory.")
        emit({"result": "blocked", "device": args.device, "wrote": ["state/firewall.json"], "gaps": ["inventory stale"]})
        return 0
    side = side_of(device)
    host, port = access_of(device)
    if side is None or host is None:
        gap = "no restconf access" if host is None else "platform is not iosxe or ftd"
        write_state(ws, started, args.device, side, "blocked", None, [gap], f"{args.device}: {gap}", ports, destination, "Ops Network Sync")
        emit({"result": "blocked", "device": args.device, "wrote": ["state/firewall.json"], "gaps": [gap]})
        return 0
    if side == "iosxe":
        outcome, err = apply_ios(host, port, ports, destination, args.remove)
    else:
        outcome, err = apply_ftd(host, port, ports, args.remove, args.deploy)
    if err:
        write_state(ws, started, args.device, side, "failed", None, [err], f"{args.device}: {err}", ports, destination, None)
        emit({"result": "failed", "device": args.device, "side": side, "wrote": ["state/firewall.json"], "gaps": [err]})
        return 0
    gaps = []
    if side == "iosxe" and not args.remove:
        gaps.append(f"{LIST_NAME} is not applied to an interface")
    if side == "ftd" and not args.remove:
        for name in outcome.get("open_permits") or []:
            gaps.append(f"{name}: permit with no destination ports")
        if not args.deploy:
            gaps.append("not deployed")
    pending = None if side == "iosxe" else outcome.get("pending")
    result = "written" if not args.remove else "written"
    if args.deploy and side == "ftd" and not args.remove:
        result = "deployed"
    action = "remove" if args.remove else "write"
    headline = f"{args.device}: {LIST_NAME} {action} ports {','.join(ports)} to {destination}"
    next_action = None
    if side == "ftd" and not args.deploy and not args.remove:
        next_action = f"Deploy. sends every pending change on {args.device}"
    write_state(ws, started, args.device, side, result if result != "deployed" else "deployed", pending, gaps, headline, ports, destination, next_action)
    emit({
        "result": result,
        "device": args.device,
        "side": side,
        "list": LIST_NAME,
        "ports": ports,
        "destination": destination,
        "pending": pending,
        "wrote": ["state/firewall.json"],
        "gaps": gaps,
    })
    return 0


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("--workspace", required=True)
    apply.add_argument("--device", required=True)
    apply.add_argument("--destination", default="any")
    apply.add_argument("--permit-ports", default="80,443,8080")
    apply.add_argument("--remove", action="store_true")
    apply.add_argument("--deploy", action="store_true")
    args = parser.parse_args()
    if args.command == "apply":
        return cmd_apply(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
