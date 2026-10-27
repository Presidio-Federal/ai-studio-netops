#!/usr/bin/env python3
"""Merge one CML lab into the workspace inventory.

collect runs under execution_type mcp_orchestration. It calls the four
read-only CML tools, reduces the lab, and writes the inventory file
then state/network-sync.json. The model does not see the lab body.

  python3 <skill>/scripts/collect_inventory.py collect --workspace <file_explorer> --environment prod

Lab title comes from the existing inventory. Pass --lab-title only when
that file does not exist yet. A missing title prints lab names and
writes no inventory.
"""
import argparse
import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
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

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
SKIP = {"external_connector", "unmanaged_switch"}
PLATFORMS = {
    "cat8000v": "iosxe",
    "iosv": "iosxe",
    "csr1000v": "iosxe",
    "iosvl2": "iosxe",
    "nxosv": "nxos",
    "nxosv9000": "nxos",
    "asav": "asa",
    "ftdv": "ftd",
    "ubuntu": "linux",
    "alpine": "linux",
    "server": "linux",
}
ROLES = ("wan", "edge", "branch", "hq", "cloud")
PAT = re.compile(r"^pat:(\d+):(\d+)$")
WORKFLOWS = (
    "sync_prod",
    "sync_dev",
    "drift_prod",
    "drift_dev",
    "deploy_twin",
    "reconcile_dev",
)


def stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def iso(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "lab"


def cml_body(tool, args):
    inner, err = visit_common._github_tool_dict(visit_common.mcp_call(tool, args))
    if err:
        return None, err
    if inner.get("ok") is not True:
        return None, str(inner.get("error") or "cml ok false")[:200]
    return inner, None


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def empty_slot():
    return {"latest_attempt": None, "current_snapshot": None}


def slot_of(raw):
    if not isinstance(raw, dict):
        return empty_slot()
    return {
        "latest_attempt": raw.get("latest_attempt"),
        "current_snapshot": raw.get("current_snapshot"),
    }


def prior_host(inventory):
    if not isinstance(inventory, dict):
        return None
    for device in inventory.get("devices") or []:
        if not isinstance(device, dict):
            continue
        access = device.get("access") or {}
        for side in ("restconf", "ssh"):
            endpoint = access.get(side)
            if isinstance(endpoint, dict) and endpoint.get("host"):
                return str(endpoint["host"])
    return None


def role_of(tags):
    found = set()
    for tag in tags:
        if tag in ROLES:
            found.add(tag)
        if ":" in tag and tag.split(":")[-1] in ROLES:
            found.add(tag.split(":")[-1])
    for name in ROLES:
        if name in found:
            return name
    return "unknown"


def intent_tags(tags):
    kept = []
    for tag in tags:
        if tag.startswith("pat:") or tag.startswith("synced:"):
            continue
        kept.append(tag)
    return kept


def platform_of(node_definition):
    key = (node_definition or "").strip()
    if key in PLATFORMS:
        return PLATFORMS[key]
    lowered = key.lower()
    return lowered or "unknown"


def endpoint(host, port, protocol, prior, platform):
    if not host or port is None:
        return None
    body = dict(prior) if isinstance(prior, dict) else {}
    body["host"] = host
    body["port"] = int(port)
    if protocol:
        body["protocol"] = protocol
    if not body.get("credential_ref") and protocol == "https" and platform == "iosxe":
        body["credential_ref"] = "iosxe-lab"
    return body


def parse_ports(tags):
    restconf = None
    ssh = None
    pat_tags = []
    for tag in tags:
        match = PAT.match(tag)
        if not match:
            continue
        pat_tags.append(tag)
        external = int(match.group(1))
        internal = match.group(2)
        if internal == "443" and restconf is None:
            restconf = external
        elif internal == "22" and ssh is None:
            ssh = external
    return restconf, ssh, pat_tags


def included(node):
    return isinstance(node, dict) and node.get("node_definition") not in SKIP and node.get("label")


def fill_tags(lab):
    """Lab details often omit tags. Read them before treating PAT as absent."""
    nodes = [node for node in lab.get("nodes") or [] if included(node)]
    missing = [node for node in nodes if not node.get("tags")]
    if not missing:
        return None
    ids = [node.get("id") for node in missing if node.get("id")]
    if not ids:
        return None
    body, err = cml_body("cml_get_node_info", {
        "lab_id": lab.get("lab_id") or "",
        "node_ids": json.dumps(ids),
        "include_configuration": False,
        "include_interfaces": False,
        "include_peers": False,
    })
    if err:
        return err
    by_id = {}
    for node in body.get("nodes") or []:
        if isinstance(node, dict) and node.get("id"):
            by_id[node["id"]] = node.get("tags") or []
    for node in missing:
        if node.get("id") in by_id:
            node["tags"] = by_id[node["id"]]
    return None


def interface_index(nodes):
    index = {}
    for node in nodes:
        if not included(node):
            continue
        for iface in node.get("interfaces") or []:
            if isinstance(iface, dict) and iface.get("id") and iface.get("label"):
                index[iface["id"]] = (node.get("label"), iface.get("label"))
    return index


def lab_links(lab, names):
    index = interface_index(lab.get("nodes") or [])
    rows = []
    gaps = []
    for link in lab.get("links") or []:
        if not isinstance(link, dict):
            continue
        a = index.get(link.get("interface_a"))
        b = index.get(link.get("interface_b"))
        if not a or not b:
            continue
        if a[0] not in names or b[0] not in names:
            continue
        if not a[1] or not b[1]:
            gaps.append(f"{a[0]}: link interface label missing")
            continue
        rows.append({
            "a_device": a[0],
            "a_interface": a[1],
            "b_device": b[0],
            "b_interface": b[1],
            "source_metadata": {"lab_id": lab.get("lab_id")},
        })
    return rows, gaps


def link_key(link):
    ends = tuple(sorted((
        (link.get("a_device"), link.get("a_interface")),
        (link.get("b_device"), link.get("b_interface")),
    )))
    return ends


def merge_links(prior_links, fresh, lab_id):
    fresh_keys = {link_key(link) for link in fresh}
    kept = []
    for link in prior_links or []:
        if not isinstance(link, dict):
            continue
        meta = link.get("source_metadata")
        if not isinstance(meta, dict):
            if link_key(link) not in fresh_keys:
                kept.append(copy.deepcopy(link))
            continue
        if link_key(link) in fresh_keys:
            continue
    for link in fresh:
        match = None
        for prior in prior_links or []:
            if isinstance(prior, dict) and link_key(prior) == link_key(link):
                match = prior
                break
        if isinstance(match, dict):
            row = copy.deepcopy(match)
            row.update(link)
            meta = dict(row.get("source_metadata") or {})
            meta["lab_id"] = lab_id
            row["source_metadata"] = meta
            kept.append(row)
        else:
            kept.append(link)
    return kept


def device_from_node(node, host, prior):
    tags = [tag for tag in (node.get("tags") or []) if isinstance(tag, str)]
    rest_port, ssh_port, pat_tags = parse_ports(tags)
    prior = prior if isinstance(prior, dict) else {}
    prior_access = prior.get("access") if isinstance(prior.get("access"), dict) else {}
    platform = platform_of(node.get("node_definition"))
    rest = endpoint(host, rest_port, "https", prior_access.get("restconf"), platform)
    ssh = endpoint(host, ssh_port, None, prior_access.get("ssh"), platform)
    meta = dict(prior.get("source_metadata") or {}) if isinstance(prior.get("source_metadata"), dict) else {}
    meta.update({
        "lab_id": node.get("_lab_id"),
        "lab_title": node.get("_lab_title"),
        "node_id": node.get("id"),
        "node_definition": node.get("node_definition"),
        "pat_tags": pat_tags,
    })
    if isinstance(node.get("x"), (int, float)) and isinstance(node.get("y"), (int, float)):
        meta["position"] = {"x": node.get("x"), "y": node.get("y")}
    elif "position" in meta and not (
        isinstance(node.get("x"), (int, float)) and isinstance(node.get("y"), (int, float))
    ):
        meta.pop("position", None)
    row = copy.deepcopy(prior) if prior else {}
    row.update({
        "name": node.get("label"),
        "platform": platform,
        "role": role_of(tags),
        "tags": intent_tags(tags),
        "operational_state": str(node.get("state") or "UNKNOWN"),
        "agent_access": bool(rest or ssh),
        "access": {"restconf": rest, "ssh": ssh},
        "source_metadata": meta,
    })
    access = dict(prior_access)
    access.update(row["access"])
    row["access"] = access
    return row


def keys_for(devices, links, site):
    found = set()
    if site:
        found.add(f"site:{site}")
    for device in devices:
        name = device.get("name")
        if isinstance(name, str) and name.strip():
            found.add(f"device:{name}")
    for link in links:
        for side in ("a", "b"):
            device = link.get(side + "_device")
            iface = link.get(side + "_interface")
            if isinstance(device, str) and isinstance(iface, str) and device.strip() and iface.strip():
                found.add(f"interface:{device}/{iface}")
    return sorted(found)


def coverage_for(devices, lab_names, missing_info):
    missing_rest = []
    missing_ssh = []
    accessible = 0
    for device in devices:
        if device.get("name") not in lab_names:
            continue
        access = device.get("access") or {}
        if device.get("agent_access"):
            accessible += 1
        if not isinstance(access.get("restconf"), dict):
            missing_rest.append(device["name"])
        if not isinstance(access.get("ssh"), dict):
            missing_ssh.append(device["name"])
    state = "partial" if missing_info or accessible != len(lab_names) else "complete"
    return {
        "state": state,
        "devices_discovered": len(lab_names),
        "devices_inspected": len(lab_names) - len(missing_info),
        "accessible_devices": accessible,
        "missing_device_info": missing_info,
        "missing_restconf": missing_rest,
        "missing_ssh": missing_ssh,
    }


def build_inventory(prior, lab, host, environment, tenant, site, infra_sot, now):
    prior = prior if isinstance(prior, dict) else {}
    by_name = {}
    for device in prior.get("devices") or []:
        if isinstance(device, dict) and device.get("name"):
            by_name[device["name"]] = device
    seen = set()
    fresh = []
    gaps = []
    missing_info = []
    for node in lab.get("nodes") or []:
        if not included(node):
            continue
        node = dict(node)
        node["_lab_id"] = lab.get("lab_id")
        node["_lab_title"] = lab.get("lab_title")
        name = node.get("label")
        if name in seen:
            gaps.append(f"{name}: duplicate node label")
            continue
        seen.add(name)
        if not node.get("tags"):
            missing_info.append(name)
        fresh.append(device_from_node(node, host, by_name.get(name)))
    names = {device["name"] for device in fresh}
    for name, device in by_name.items():
        if name not in names:
            fresh.append(copy.deepcopy(device))
            gaps.append(f"{name}: not in the lab; row kept")
    fresh.sort(key=lambda item: item.get("name") or "")
    new_links, link_gaps = lab_links(lab, names)
    gaps.extend(link_gaps)
    links = merge_links(prior.get("links") or [], new_links, lab.get("lab_id"))
    if not host:
        gaps.append("controller host unknown")
    collected = now
    published = now
    cover = dict(prior.get("coverage") or {})
    cover.update(coverage_for(fresh, names, missing_info))
    netbox = dict(prior.get("netbox") or {})
    netbox["tenant"] = tenant
    netbox["site"] = site
    source = dict(prior.get("source") or {})
    source["type"] = "cml"
    source["name"] = lab.get("lab_title")
    inventory = copy.deepcopy(prior) if prior else {}
    inventory.update({
        "schema": "network-access-inventory/v3",
        "snapshot_id": stamp(collected),
        "environment": environment,
        "collected_at": iso(collected),
        "published_at": iso(published),
        "expires_at": iso(collected + timedelta(hours=26)),
        "status": cover["state"],
        "coverage": cover,
        "source": source,
        "infra_sot": infra_sot,
        "lab_title": lab.get("lab_title"),
        "lab_id": lab.get("lab_id"),
        "netbox": netbox,
        "device_count": len(fresh),
        "devices": fresh,
        "links": links,
        "keys": keys_for(fresh, links, site),
    })
    return inventory, gaps


def seed_rows(inventory):
    rows = []
    for device in inventory.get("devices") or []:
        tags = device.get("tags") or []
        if "tag:simulate" not in tags:
            continue
        rest = (device.get("access") or {}).get("restconf")
        rows.append({
            "name": device.get("name"),
            "host": rest.get("host") if isinstance(rest, dict) else None,
            "port": rest.get("port") if isinstance(rest, dict) else None,
            "node_definition": (device.get("source_metadata") or {}).get("node_definition"),
        })
    rows.sort(key=lambda row: row["name"] or "")
    return rows


def seed_gate(environment, inventory, infra, onboard):
    if onboard or environment != "prod":
        return "skipped", None
    rows = seed_rows(inventory)
    if not isinstance(infra, dict) or not isinstance(infra.get("seed"), list):
        return "mismatch", "Ops NetBox SoT"
    snap = []
    for row in infra.get("seed") or []:
        if not isinstance(row, dict):
            continue
        snap.append({
            "name": row.get("name"),
            "host": row.get("host"),
            "port": row.get("port"),
            "node_definition": row.get("node_definition"),
        })
    status = infra.get("status")
    if snap == rows and status in ("ok", "gaps"):
        return "match", None
    return "mismatch", "Ops NetBox SoT"


def snapshot_of(inventory, environment):
    cover = inventory["coverage"]
    return {
        "snapshot_id": inventory["snapshot_id"],
        "path": f"inventory/{environment}.json",
        "status": inventory["status"],
        "collected_at": inventory["collected_at"],
        "expires_at": inventory["expires_at"],
        "device_count": inventory["device_count"],
        "accessible_count": cover["accessible_devices"],
        "coverage": {
            "state": cover["state"],
            "devices_discovered": cover["devices_discovered"],
            "devices_inspected": cover["devices_inspected"],
            "accessible_devices": cover["accessible_devices"],
            "missing_device_info": cover["missing_device_info"],
            "missing_restconf": cover["missing_restconf"],
            "missing_ssh": cover["missing_ssh"],
        },
    }


def state_shell(prior, environment, operation, op, started, finished, status, headline, gaps, next_action, attempt, snapshot):
    prior = prior if isinstance(prior, dict) else {}
    inventories = prior.get("inventories") if isinstance(prior.get("inventories"), dict) else {}
    prod = slot_of(inventories.get("prod"))
    dev = slot_of(inventories.get("dev"))
    slot = {
        "latest_attempt": attempt,
        "current_snapshot": snapshot if snapshot is not None else (
            prod if environment == "prod" else dev
        ).get("current_snapshot"),
    }
    if environment == "prod":
        prod = slot
    else:
        dev = slot
    body = {
        "schema": "network-sync-state/v2",
        "updated_at": iso(finished),
        "source_agent": "ops-network-sync",
        "status": status,
        "headline": headline,
        "operation_id": op,
        "operation": operation,
        "started_at": iso(started),
        "completed_at": iso(finished),
        "inventories": {"prod": prod, "dev": dev},
        "gaps": gaps,
        "next_action": next_action,
        "keys": [],
    }
    for key in WORKFLOWS:
        if key in prior and (prior[key] is None or isinstance(prior[key], dict)):
            body[key] = prior[key]
    return body


def failed_attempt(op, started, finished, headline):
    return {
        "operation_id": op,
        "attempted_at": iso(started),
        "completed_at": iso(finished),
        "status": "failed",
        "headline": headline,
        "coverage": {
            "state": "unavailable",
            "devices_discovered": None,
            "devices_inspected": None,
            "accessible_devices": None,
            "missing_device_info": [],
            "missing_restconf": [],
            "missing_ssh": [],
        },
    }


def write_state(ws, body):
    visit_common.validate(body, SCHEMA_DIR / "network-sync-state.schema.json")
    save_json(Path(ws) / "state" / "network-sync.json", body)


def emit(payload):
    print(visit_common.summary(payload))


def fail_collect(ws, prior_state, environment, operation, started, reason, labs=None):
    finished = datetime.now(timezone.utc)
    op = stamp(started)
    headline = reason[:180]
    body = state_shell(
        prior_state,
        environment,
        operation,
        op,
        started,
        finished,
        "failed",
        headline,
        [reason[:180]],
        None,
        failed_attempt(op, started, finished, headline),
        None,
    )
    try:
        write_state(ws, body)
    except ValueError as exc:
        print(str(exc)[:300], file=sys.stderr)
        return 1
    payload = {
        "result": "blocked" if labs is not None else "failed",
        "environment": environment,
        "wrote": ["state/network-sync.json"],
        "seed": "skipped",
        "gaps": [reason[:180]],
    }
    if labs is not None:
        payload["labs"] = labs
    emit(payload)
    return 0


def resolve_title(args, prior):
    if args.lab_title:
        return args.lab_title.strip(), None
    if isinstance(prior, dict):
        title = prior.get("lab_title") or (prior.get("source") or {}).get("name")
        if isinstance(title, str) and title.strip():
            return title.strip(), None
    listed, err = cml_body("cml_list_labs", {})
    if err:
        return None, err
    titles = []
    for lab in listed.get("labs") or []:
        if isinstance(lab, dict) and lab.get("title"):
            titles.append(lab["title"])
    return None, titles


def collect_lab(title):
    listed, err = cml_body("cml_list_labs", {})
    if err:
        return None, err
    matches = [
        lab for lab in (listed.get("labs") or [])
        if isinstance(lab, dict) and lab.get("title") == title and lab.get("id")
    ]
    if len(matches) != 1:
        reason = "lab title matched more than one lab" if len(matches) > 1 else "lab title not in cml_list_labs"
        return None, reason
    detailed, err = cml_body("cml_get_lab_details", {
        "lab_id": matches[0]["id"],
        "include_configurations": False,
    })
    if err:
        return None, err
    tag_err = fill_tags(detailed)
    if tag_err:
        return None, tag_err
    return detailed, None


def cmd_collect(args):
    environment = args.environment
    ws = Path(args.workspace)
    if not ws.is_dir():
        print("workspace is not a directory", file=sys.stderr)
        return 1
    started = datetime.now(timezone.utc)
    operation = "onboard" if args.onboard else f"collect-{environment}"
    rel = f"inventory/{environment}.json"
    prior = visit_common.load_json(ws, rel)
    prior_state = visit_common.load_json(ws, "state/network-sync.json")
    title, listed = resolve_title(args, prior)
    if not title:
        if isinstance(listed, list):
            return fail_collect(
                ws, prior_state, environment, operation, started,
                "lab title missing", labs=listed,
            )
        return fail_collect(ws, prior_state, environment, operation, started, listed or "lab title missing")
    lab, err = collect_lab(title)
    if err:
        return fail_collect(ws, prior_state, environment, operation, started, err)
    host = (args.controller_host or "").strip() or prior_host(prior)
    if isinstance(prior, dict) and isinstance(prior.get("netbox"), dict):
        tenant = prior["netbox"].get("tenant") or args.tenant or slug(title)
        site = prior["netbox"].get("site") or args.site or tenant
        infra = prior.get("infra_sot") or args.infra_sot or "git"
    else:
        tenant = args.tenant or slug(title)
        site = args.site or tenant
        infra = args.infra_sot or "git"
    inventory, gaps = build_inventory(
        prior, lab, host, environment, tenant, site, infra, started,
    )
    try:
        visit_common.validate(inventory, SCHEMA_DIR / "network-access-inventory.schema.json")
    except ValueError as exc:
        return fail_collect(ws, prior_state, environment, operation, started, f"inventory invalid: {exc}")
    infra_sot = visit_common.load_json(ws, "inventory/infra-sot.json")
    seed, next_action = seed_gate(environment, inventory, infra_sot, args.onboard)
    finished = datetime.now(timezone.utc)
    op = inventory["snapshot_id"]
    status = "ok" if inventory["status"] == "complete" else "partial"
    headline = (
        f"{environment} collect {inventory['status']}: "
        f"{inventory['device_count']} devices, "
        f"{inventory['coverage']['accessible_devices']} accessible"
    )
    attempt = {
        "operation_id": op,
        "attempted_at": inventory["collected_at"],
        "completed_at": iso(finished),
        "status": inventory["status"],
        "headline": headline,
    }
    body = state_shell(
        prior_state,
        environment,
        operation,
        op,
        started,
        finished,
        status,
        headline,
        gaps,
        next_action,
        attempt,
        snapshot_of(inventory, environment),
    )
    body["keys"] = list(inventory.get("keys") or [])
    try:
        visit_common.validate(body, SCHEMA_DIR / "network-sync-state.schema.json")
    except ValueError as exc:
        return fail_collect(ws, prior_state, environment, operation, started, f"state invalid: {exc}")
    save_json(ws / rel, inventory)
    save_json(ws / "state" / "network-sync.json", body)
    emit({
        "result": inventory["status"],
        "environment": environment,
        "devices": inventory["device_count"],
        "accessible": inventory["coverage"]["accessible_devices"],
        "links": len(inventory.get("links") or []),
        "wrote": [rel, "state/network-sync.json"],
        "seed": seed,
        "gaps": gaps,
    })
    return 0


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--workspace", required=True)
    collect.add_argument("--environment", required=True, choices=("prod", "dev"))
    collect.add_argument("--lab-title", default="")
    collect.add_argument("--tenant", default="")
    collect.add_argument("--site", default="")
    collect.add_argument("--infra-sot", default="", choices=("", "git", "netbox"))
    collect.add_argument("--controller-host", default="")
    collect.add_argument("--onboard", action="store_true")
    args = parser.parse_args()
    if args.command == "collect":
        return cmd_collect(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
