#!/usr/bin/env python3
"""Security event response. collect runs the NetFlow and Splunk nurse queries.

collect runs under execution_type mcp_orchestration. It reads the health
boards, then calls elasticsearch_query with F1–F4 from health-elastic and
splunk_search with S1–S3 from health-logging. annotate runs under standard
and only sets the kind, the blocks, and the dispatched lines. This script
does not decide the kind.

The agent copies the path Studio shows for this file. Do not hardcode it.

  python3 <skill>/scripts/respond.py collect --workspace <file_explorer>
  python3 <skill>/scripts/respond.py annotate --workspace <file_explorer> \\
      --kind port_scan --headline "..." --block "iosxe|<device>|<source>|<destination>"
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace-handoff" / "scripts"))

try:
    import visit_common  # noqa: E402
except ImportError:
    print('{"error": "visit_common missing; attach the workspace-handoff skill"}', file=sys.stderr)
    sys.exit(1)

SPREAD = 20
STATE_NAME = "state/secops-event.json"
KINDS = {"port_scan", "deny_surge", "traffic_spike", "quiet", "unknown"}
SKILLS = Path(__file__).resolve().parents[2]
NETFLOW_MD = SKILLS / "health-elastic" / "references" / "netflow.md"
SPLUNK_MD = SKILLS / "health-logging" / "references" / "splunk.md"


def blank(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_workspace(given):
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
            print(f"secops workspace={resolved}", file=sys.stderr)
            return resolved
    print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
    return None


def tool_body(label, tool, args):
    envelope = visit_common.mcp_call(tool, args, retries=1)
    error = None
    inner = None
    if not isinstance(envelope, dict) or not envelope.get("success"):
        error = (envelope or {}).get("error") if isinstance(envelope, dict) else "empty envelope"
        error = error or "success false"
    else:
        outer = envelope.get("result")
        raw = outer[0] if isinstance(outer, list) and outer else outer
        try:
            inner = json.loads(raw, strict=False) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            error = "result[0] not json"
        if error is None and isinstance(inner, dict) and inner.get("ok") is False:
            error = inner.get("error") or "ok false"
        elif error is None and not isinstance(inner, dict):
            error = "inner envelope not an object"
    shown = "ok" if error is None else str(error)[:160]
    print(f"secops call={label} result={shown}", file=sys.stderr)
    return inner, error


def rows_of(inner):
    if not isinstance(inner, dict):
        return []
    found = inner.get("rows")
    if isinstance(found, list):
        return [row for row in found if isinstance(row, dict)]
    return []


def load_state(ws):
    path = ws / STATE_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_state(ws, payload):
    path = ws / STATE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def devices_by_name(prod):
    found = {}
    for device in prod.get("devices") or []:
        if isinstance(device, dict) and blank(device.get("name")):
            found[device["name"]] = device
    return found


def graph_of(prod):
    graph = defaultdict(set)
    for link in prod.get("links") or []:
        if not isinstance(link, dict):
            continue
        left = blank(link.get("a_device"))
        right = blank(link.get("b_device"))
        if left and right:
            graph[left].add(right)
            graph[right].add(left)
    return graph


def is_edge(device):
    name = device.get("name") or ""
    if device.get("platform") != "iosxe" or device.get("role") != "edge":
        return False
    upper = name.upper()
    if "ISP" in upper or "DC" in upper:
        return False
    return True


def closest(graph, by_name, start, accept):
    if start not in by_name:
        return None
    seen = {start}
    queue = [start]
    while queue:
        current = queue.pop(0)
        for nxt in sorted(graph.get(current) or []):
            if nxt in seen:
                continue
            seen.add(nxt)
            device = by_name.get(nxt)
            if device and accept(device):
                return nxt
            queue.append(nxt)
    return None


def placements(prod, netflow_rows):
    """One IOS-XE edge per scan source. Destination is any. No firewall, no prefix."""
    by_name = devices_by_name(prod)
    graph = graph_of(prod)
    blocks = []
    gaps = []
    seen = set()
    for row in netflow_rows:
        source = blank(row.get("source.ip"))
        src_name = blank(row.get("src_name"))
        dests = row.get("dests") or 0
        ports = row.get("ports") or 0
        if not source:
            continue
        if not (isinstance(dests, (int, float)) and isinstance(ports, (int, float))):
            continue
        if dests < SPREAD and ports < SPREAD:
            continue
        edge = closest(graph, by_name, src_name, is_edge) if src_name else None
        if not edge:
            gaps.append(f"{src_name or source}: no edge router")
            continue
        if edge in seen:
            continue
        seen.add(edge)
        blocks.append(
            {
                "device": edge,
                "side": "iosxe",
                "source": source,
                "destination": "any",
                "src_name": src_name,
            }
        )
    return blocks, gaps


def code_blocks(path, expect, label):
    if not path.is_file():
        print(json.dumps({"error": f"attach the {label} skill; {path.name} is not beside this skill"}), file=sys.stderr)
        return None
    text = path.read_text(encoding="utf-8")
    blocks = [block.strip() + "\n" for block in re.findall(r"```\n(.*?)```", text, re.S)]
    if len(blocks) < expect:
        print(json.dumps({"error": f"{path.name} is missing a query"}), file=sys.stderr)
        return None
    return blocks


def esql_interval(window):
    return {"15m": "15 minutes", "1h": "1 hour", "1d": "1 day"}.get(window or "")


def netflow_plane(board):
    if not isinstance(board, dict):
        return {}
    nested = board.get("netflow")
    if isinstance(nested, dict) and (nested.get("current") or nested.get("data_stream") or nested.get("measurement")):
        return nested
    return board


def splunk_plane(board):
    if not isinstance(board, dict):
        return {}
    nested = board.get("splunk")
    if isinstance(nested, dict) and (nested.get("index") or nested.get("current")):
        return nested
    return board


def elastic_rows(label, query, timerange, limit):
    inner, error = tool_body(
        label,
        "elasticsearch_query",
        {"query": query, "timerange": timerange, "limit": limit},
    )
    if error or not isinstance(inner, dict):
        return [], error or "empty"
    rows = []
    for row in inner.get("rows") or []:
        if not isinstance(row, dict):
            continue
        cleaned = {}
        for key, value in row.items():
            if isinstance(value, list):
                value = value[0] if value else None
            if value is not None and key in ("source", "src", "dst", "dst_port", "protocol", "event", "last_at", "source.ip", "prefix", "src_name", "zone"):
                value = str(value)
            cleaned[key] = value
        rows.append(cleaned)
    return rows, None


def splunk_rows(label, query, earliest, latest):
    envelope = visit_common.mcp_call(
        "splunk_search",
        {"query": query, "earliest_time": earliest, "latest_time": latest, "max_results": 200},
        retries=1,
    )
    payload, error = visit_common.unwrap_splunk(envelope)
    shown = "ok" if error is None else str(error)[:120]
    print(f"secops call={label} result={shown}", file=sys.stderr)
    if error or not isinstance(payload, dict):
        return [], error or "empty"
    return [row for row in payload.get("results") or [] if isinstance(row, dict)], None


def prior_rows(rows):
    found = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        protocol = str(row.get("protocol") or "")
        scope = str(row.get("scope") or "")
        detail = str(row.get("detail") or "")
        if protocol != "scan" and not scope.startswith("scan:") and "ports" not in detail:
            continue
        kept = {}
        for key in ("kind", "scope", "src", "dst", "dst_port", "protocol", "source_ip", "detail", "state", "name", "subject", "count"):
            if row.get(key) is not None:
                kept[key] = row.get(key)
        found.append(kept)
        if len(found) >= 15:
            break
    return found


def clock(board):
    if not isinstance(board, dict):
        return {"present": False}
    plane = board
    for key in ("netflow", "splunk", "application", "iosxe", "servicenow"):
        nested = board.get(key)
        if isinstance(nested, dict) and nested.get("last_collected_at"):
            plane = nested
            break
    return {
        "present": True,
        "last_collected_at": plane.get("last_collected_at") or board.get("last_collected_at"),
        "last_visit_id": plane.get("last_visit_id") or board.get("last_visit_id"),
    }


def cmd_collect(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    prod = visit_common.load_json(ws, "inventory/prod.json")
    if not isinstance(prod, dict):
        print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
        return 1
    health = visit_common.load_json(ws, "state/health.json")
    boards = {
        "application": visit_common.load_json(ws, "health/metadata-application.json"),
        "netflow": visit_common.load_json(ws, "health/metadata-netflow.json"),
        "splunk": visit_common.load_json(ws, "health/metadata-splunk.json"),
        "iosxe": visit_common.load_json(ws, "health/metadata-iosxe.json"),
        "servicenow": visit_common.load_json(ws, "health/metadata-servicenow.json"),
    }
    netflow = netflow_plane(boards["netflow"] if isinstance(boards["netflow"], dict) else {})
    splunk = splunk_plane(boards["splunk"] if isinstance(boards["splunk"], dict) else {})
    window = blank(netflow.get("window")) or "1h"
    interval = esql_interval(window)
    measurement = blank(netflow.get("data_stream")) or blank(netflow.get("measurement")) or ""
    if measurement and not (measurement.startswith("logs-") or measurement.startswith("metrics-")):
        measurement = ""
    esql = code_blocks(NETFLOW_MD, 4, "health-elastic")
    spl = code_blocks(SPLUNK_MD, 3, "health-logging")
    if esql is not None:
        esql = [block for block in esql if block.strip().startswith("FROM ")]
    if esql is None or spl is None or len(esql) < 4 or len(spl) < 3 or interval is None:
        if interval is None:
            print('{"error": "netflow window must be 15m, 1h, or 1d"}', file=sys.stderr)
        return 1
    gaps = []
    live = {}
    if not measurement:
        gaps.append("netflow board has no data_stream")
    else:
        for label, query, limit in (("f1", esql[0], 50), ("f2", esql[1], 50), ("f3", esql[2], 50), ("f4", esql[3], 30)):
            text = query.replace("<measurement>", measurement).replace("<window>", interval)
            rows, error = elastic_rows(label, text, window, limit)
            live[label] = rows
            if error:
                gaps.append(f"{label}: {str(error)[:140]}")
    rate_window = blank(splunk.get("window")) or "1h"
    if not re.fullmatch(r"\d+[mhd]", rate_window):
        rate_window = "1h"
    index = blank(splunk.get("index"))
    sourcetype = blank(splunk.get("sourcetype"))
    if not index or not sourcetype or index.startswith("<") or sourcetype.startswith("<"):
        gaps.append("splunk board has no index or sourcetype")
    else:
        earliest = {"s1": f"-{rate_window}", "s2": blank(splunk.get("collected_through")) or "-7d", "s3": f"-{rate_window}"}
        for label, query in (("s1", spl[0]), ("s2", spl[1]), ("s3", spl[2])):
            text = query.replace("index=<index>", f"index={index}", 1).replace("sourcetype=<sourcetype>", f"sourcetype={sourcetype}", 1)
            rows, error = splunk_rows(label, text, earliest[label], "now")
            live[label] = rows
            if error:
                gaps.append(f"{label}: {str(error)[:140]}")
    addresses = []
    if measurement:
        address_query = (
            f"FROM {measurement}"
            f" | WHERE @timestamp >= NOW() - {interval} AND destination.port > 0 AND destination.port < 32768"
            " | EVAL prefix = IP_PREFIX(destination.ip, 24, 0)"
            " | STATS flows = COUNT(*), dests = COUNT_DISTINCT(destination.ip), ports = COUNT_DISTINCT(destination.port),"
            " src_name = MAX(lab.source.device), zone = MAX(lab.destination.zone) BY source.ip, prefix"
            " | WHERE dests >= 20 OR ports >= 20"
            " | SORT flows DESC | LIMIT 20"
        )
        addresses, address_error = elastic_rows("addresses", address_query, window, 20)
        if address_error:
            gaps.append("addresses: " + str(address_error)[:140])
            addresses = []
    blocks, place_gaps = placements(prod, addresses)
    gaps.extend(place_gaps)
    problems = []
    if isinstance(health, dict):
        for item in health.get("problems") or []:
            if isinstance(item, dict):
                problems.append({"id": item.get("id"), "status": item.get("status"), "hypothesis": item.get("hypothesis")})
            if len(problems) >= 8:
                break
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema": "secops-event/v1",
        "updated_at": now,
        "source_agent": "secops-event-response",
        "status": "gaps" if gaps else "ok",
        "headline": "Evidence collected. Kind not set.",
        "next_action": None,
        "kind": None,
        "evidence": {
            "window": window,
            "data_stream": measurement or None,
            "splunk_index": index,
            "prior": {
                "health": {
                    "updated_at": (health or {}).get("updated_at") if isinstance(health, dict) else None,
                    "headline": (health or {}).get("headline") if isinstance(health, dict) else None,
                    "problems": problems,
                },
                "boards": {name: clock(board if isinstance(board, dict) else {}) for name, board in boards.items()},
                "netflow_scans": prior_rows((netflow.get("current") or []) if isinstance(netflow, dict) else []),
                "splunk_rows": prior_rows((splunk.get("current") or []) if isinstance(splunk, dict) else []),
            },
            "live": {key: live.get(key) or [] for key in ("f1", "f2", "f3", "f4", "s1", "s2", "s3")},
            "addresses": addresses,
            "placements": blocks,
        },
        "blocks": [],
        "dispatched": [],
        "gaps": gaps,
        "relations": [],
        "keys": [],
    }
    write_state(ws, payload)
    summary = {
        "wrote": STATE_NAME,
        "window": window,
        "prior_scans": len(payload["evidence"]["prior"]["netflow_scans"]),
        "f4": live.get("f4") or [],
        "s3": live.get("s3") or [],
        "placements": [
            {"device": item["device"], "side": item["side"], "source": item["source"], "destination": item["destination"], "src_name": item.get("src_name")}
            for item in blocks
        ],
        "gaps": gaps[:8],
    }
    print(json.dumps(summary, separators=(",", ":")))
    return 0


def cmd_annotate(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    payload = load_state(ws)
    if not isinstance(payload, dict):
        print('{"error": "state/secops-event.json missing"}', file=sys.stderr)
        return 1
    kind = blank(args.kind)
    if kind is not None and kind not in KINDS:
        print('{"error": "kind must be port_scan, deny_surge, traffic_spike, quiet, or unknown"}', file=sys.stderr)
        return 1
    if kind:
        payload["kind"] = kind
    if blank(args.headline):
        payload["headline"] = args.headline.strip()
    allowed = {
        (item.get("device"), item.get("source"), item.get("destination"))
        for item in (payload.get("evidence") or {}).get("placements") or []
        if isinstance(item, dict)
    }
    blocks = list(payload.get("blocks") or [])
    seen = {(item.get("device"), item.get("source"), item.get("destination")) for item in blocks if isinstance(item, dict)}
    for raw in args.block or []:
        parts = raw.split("|")
        if len(parts) != 4:
            print('{"error": "block is side|device|source|destination"}', file=sys.stderr)
            return 1
        side, device, source, destination = [part.strip() for part in parts]
        if side not in ("iosxe", "ftd"):
            print('{"error": "block side is iosxe or ftd"}', file=sys.stderr)
            return 1
        if (device, source, destination) not in allowed:
            print(json.dumps({"error": "block is not a listed placement", "device": device}), file=sys.stderr)
            return 1
        key = (device, source, destination)
        if key in seen:
            continue
        seen.add(key)
        blocks.append({"device": device, "side": side, "source": source, "destination": destination})
    payload["blocks"] = blocks
    dispatched = list(payload.get("dispatched") or [])
    for line in args.sent or []:
        text = line.strip()
        if text and text not in dispatched:
            dispatched.append(text)
    payload["dispatched"] = dispatched
    if blocks:
        first = blocks[0]
        payload["next_action"] = f"On {first['device']}, permit tcp to any ports 80, 443, 8080, then deny ip to any."
    payload["status"] = "gaps" if payload.get("gaps") else "ok"
    payload["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    keys = []
    for block in blocks:
        key = f"device:{block['device']}"
        if key not in keys:
            keys.append(key)
    payload["keys"] = keys
    write_state(ws, payload)
    print(json.dumps({"wrote": STATE_NAME, "kind": payload.get("kind"), "blocks": len(blocks), "dispatched": len(dispatched)}, separators=(",", ":")))
    return 0


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--workspace", required=True)
    annotate = sub.add_parser("annotate")
    annotate.add_argument("--workspace", required=True)
    annotate.add_argument("--kind")
    annotate.add_argument("--headline")
    annotate.add_argument("--block", action="append")
    annotate.add_argument("--sent", action="append")
    args = parser.parse_args()
    if args.command == "collect":
        return cmd_collect(args)
    return cmd_annotate(args)


if __name__ == "__main__":
    sys.exit(main())
