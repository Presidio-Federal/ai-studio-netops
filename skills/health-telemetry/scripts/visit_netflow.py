#!/usr/bin/env python3
"""NetFlow health visit. One command collects, diffs, and writes the board.

collect runs under execution_type mcp_orchestration. annotate runs under
standard and only edits headline and notes. The Flux and the material
rules are references/netflow.md. Splunk is not this script.

The agent copies the path Studio shows for this file. Do not hardcode it.

  python3 <skill>/scripts/visit_netflow.py collect --workspace <file_explorer>
  python3 <skill>/scripts/visit_netflow.py annotate --workspace <file_explorer> \\
      --stamp health/netflow/<stamp>.json --headline "..." --note "device:NAME=..."
"""
import argparse
import ipaddress
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
REF_PATH = Path(__file__).resolve().parent.parent / "references" / "netflow.md"
CHECK_SCHEMA = SCHEMA_DIR / "health-netflow-check.schema.json"
BOARD_SCHEMA = SCHEMA_DIR / "health-metadata-netflow.schema.json"
KEY_RE = re.compile(r"^(device|site):[^ ]+$")
ROW_FIELDS = (
    "kind",
    "scope",
    "source",
    "exporter_name",
    "exporter_site",
    "device",
    "exporter",
    "src",
    "dst",
    "dst_port",
    "protocol",
    "src_device",
    "dst_device",
    "keys",
    "at",
    "state",
    "bytes",
    "flows",
    "last_flow_at",
    "last_seen_at",
)
READINGS_CAP = 60


def stamp_name(moment):
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


def checked_at(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def canon_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0)


def strip_arg(value):
    return str(value or "").strip().strip("'\"")


def blank(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def coerce_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None


def flux_queries():
    text = REF_PATH.read_text(encoding="utf-8")
    blocks = re.findall(r"```\n(.*?)```", text, re.S)
    flux = [block.strip() + "\n" for block in blocks if block.strip().startswith("from(")]
    if len(flux) < 2:
        print('{"error": "netflow.md is missing F1 and F2"}', file=sys.stderr)
        return None, None
    return flux[0], flux[1]


def substitute(query, bucket, measurement):
    return query.replace("<bucket>", bucket).replace("<measurement>", measurement)


def window_delta(window):
    match = re.fullmatch(r"(\d+)([mhd])", window or "1h")
    if not match:
        return timedelta(hours=1)
    count = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return timedelta(minutes=count)
    if unit == "d":
        return timedelta(days=count)
    return timedelta(hours=count)


# grafana_query_influx rejects a query whose text has no range(.
# buckets() does not take a range; the comment satisfies that check
# and Influx ignores it. Bucket names come from this result.
BUCKETS_QUERY = """
buckets()
  |> keep(columns: ["name"])
// range(start: v.timeRangeStart, stop: v.timeRangeStop)
"""
FLOW_TAGS = ("source", "src", "dst", "dst_port", "protocol")


def tool_body(label, tool, args):
    """Inner object from call_mcp. Grafana tools return {ok, ...}."""
    started = time.monotonic()
    envelope = visit_common.mcp_call(tool, args, retries=1)
    elapsed = time.monotonic() - started
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
    print(f"netflow call={label} elapsed_s={elapsed:.3f} result={shown}", file=sys.stderr)
    return inner, error


def grafana_query(label, query, timerange, datasource_uid):
    args = {"timerange": timerange, "query": query}
    if datasource_uid:
        args["datasource_uid"] = datasource_uid
    started = time.monotonic()
    envelope = visit_common.mcp_call("grafana_query_influx", args, retries=1)
    elapsed = time.monotonic() - started
    payload, error = visit_common.unwrap_grafana(envelope)
    shown = "ok" if error is None else str(error)[:160]
    print(f"netflow call={label} elapsed_s={elapsed:.3f} result={shown}", file=sys.stderr)
    return payload, error


def influx_uids(preferred):
    """Influx datasource uids from grafana_list_datasources. Preferred first."""
    body, error = tool_body("datasources", "grafana_list_datasources", {})
    found = []
    if error is None and body:
        for item in body.get("datasources") or []:
            if item.get("type") == "influxdb" and item.get("uid"):
                found.append(item["uid"])
    ordered = []
    if preferred:
        ordered.append(preferred)
    for uid in found:
        if uid not in ordered:
            ordered.append(uid)
    return ordered or [preferred]


def bucket_names(uid):
    payload, error = grafana_query("buckets", BUCKETS_QUERY, "15m", uid)
    if error or not payload:
        return []
    names = []
    for row in payload.get("rows") or []:
        name = blank(row.get("name"))
        if name and not name.startswith("_") and name not in names:
            names.append(name)
    return names


def schema_values(label, args):
    body, error = tool_body(label, "grafana_influx_schema", args)
    if error or not body:
        return []
    return [value for value in body.get("values") or [] if isinstance(value, str) and value]


def flow_measurements(bucket, uid, preferred):
    """Measurements in this bucket whose tags can feed F1 and F2."""
    names = schema_values("measurements", {"bucket": bucket, "datasource_uid": uid} if uid else {"bucket": bucket})
    if preferred and preferred in names:
        names = [preferred] + [name for name in names if name != preferred]
    kept = []
    for name in names:
        args = {"bucket": bucket, "measurement": name}
        if uid:
            args["datasource_uid"] = uid
        keys = set(schema_values("tags", args))
        if all(tag in keys for tag in FLOW_TAGS):
            kept.append(name)
    return kept


def discover_flows(f1_query, window, uids, preferred_measurement, skip):
    """First bucket and measurement whose F1 returns rows. None of the names are fixed."""
    for uid in uids:
        for bucket in bucket_names(uid):
            for measurement in flow_measurements(bucket, uid, preferred_measurement):
                pair = (uid or "", bucket, measurement)
                if pair in skip:
                    continue
                skip.add(pair)
                payload, error = grafana_query(
                    "f1", substitute(f1_query, bucket, measurement), window, uid
                )
                if error:
                    continue
                if payload and payload.get("rows"):
                    return uid, bucket, measurement, payload
    return None, None, None, None


def prod_index(prod):
    by_lower = {}
    access = {}
    for device in prod.get("devices") or []:
        name = device.get("name")
        if not name:
            continue
        by_lower[name.lower()] = name
        hosts = access.setdefault(name, set())
        block = device.get("access") or {}
        for key in ("restconf", "ssh"):
            host = (block.get(key) or {}).get("host")
            if host:
                hosts.add(str(host))
    return by_lower, access


def cidr_index(topology):
    nets = []
    if not isinstance(topology, dict):
        return nets
    for device in topology.get("devices") or []:
        name = device.get("name")
        if not name:
            continue
        for interface in device.get("interfaces") or []:
            cidr = interface.get("cidr")
            if not cidr or "/" not in str(cidr):
                continue
            try:
                nets.append((ipaddress.ip_network(str(cidr), strict=False), name))
            except ValueError:
                continue
    return nets


def address_device(value, nets, by_lower):
    try:
        ip = ipaddress.ip_address(str(value))
    except ValueError:
        return None
    for net, name in nets:
        if ip in net and name.lower() in by_lower:
            return by_lower[name.lower()]
    return None


def named_device(value, by_lower):
    if not value or value in ("unmapped", "unknown"):
        return None
    if str(value).lower() in by_lower:
        return by_lower[str(value).lower()]
    return None


def resolve_exporter(source, exporter_name, exporters, by_lower, access, nets):
    for row in exporters:
        if row.get("source") == source and row.get("device"):
            found = named_device(row["device"], by_lower)
            if found:
                return found
    found = named_device(exporter_name, by_lower)
    if found:
        return found
    found = address_device(source, nets, by_lower)
    if found:
        return found
    for name, hosts in access.items():
        if source in hosts:
            return name
    return None


def resolve_flow(addr, by_lower, access, nets):
    found = address_device(addr, nets, by_lower)
    if found:
        return found
    for name, hosts in access.items():
        if addr in hosts:
            return name
    return None


def device_key(name):
    if not name:
        return None
    key = f"device:{name}"
    return key if KEY_RE.match(key) else None


def site_key(site):
    if not site or site == "unknown":
        return None
    key = f"site:{site}"
    return key if KEY_RE.match(key) else None


def flow_scope(source, src, dst, dst_port, protocol):
    return f"flow:{source}/{src}>{dst}:{dst_port}/{protocol}"


def fit_row(row):
    if not isinstance(row, dict):
        return None
    kind = row.get("kind")
    scope = blank(row.get("scope"))
    source = blank(row.get("source"))
    state = row.get("state")
    at = blank(row.get("at"))
    if kind not in ("exporter", "conversation") or not scope or not source or not at:
        return None
    if state not in ("reporting", "silent", "present", "absent"):
        return None
    keys = [key for key in (row.get("keys") or []) if isinstance(key, str) and KEY_RE.match(key)]
    item = {field: row.get(field) for field in ROW_FIELDS}
    item["kind"] = kind
    item["scope"] = scope
    item["source"] = source
    item["exporter_name"] = blank(row.get("exporter_name"))
    item["keys"] = keys[:8]
    item["at"] = at
    item["state"] = state
    item["bytes"] = coerce_int(row.get("bytes"))
    item["flows"] = coerce_int(row.get("flows"))
    return item


def fit_metric(row):
    needed = (
        "at",
        "scope",
        "exporters",
        "exporters_silent",
        "exporters_unresolved",
        "flows",
        "bytes",
        "conversations",
        "conversations_absent",
        "top_scope",
    )
    if not isinstance(row, dict) or row.get("scope") != "estate":
        return None
    if not all(field in row for field in needed):
        return None
    return {field: row.get(field) for field in needed}


def fit_visit(row):
    needed = ("watch_id", "checked_at", "status", "coverage", "delta", "stamp_written", "window")
    if not isinstance(row, dict) or not all(field in row for field in needed):
        return None
    if row.get("status") not in ("ok", "degraded", "unknown"):
        return None
    if row.get("coverage") not in ("complete", "partial", "unavailable"):
        return None
    if row.get("delta") not in ("first", "unchanged", "worse", "better", "changed"):
        return None
    return {field: row.get(field) for field in needed}


def keep(rows, fit):
    return [item for item in (fit(row) for row in rows or []) if item is not None]


def null_metric(at):
    return {
        "at": at,
        "scope": "estate",
        "exporters": None,
        "exporters_silent": None,
        "exporters_unresolved": None,
        "flows": None,
        "bytes": None,
        "conversations": None,
        "conversations_absent": None,
        "top_scope": None,
    }


def union_keys(rows):
    found = []
    for row in rows:
        for key in row.get("keys") or []:
            if key not in found and re.match(r"^(device|interface|site|service|test|control|incident|change|application):[^ ]+$", key):
                found.append(key)
    return found


def ring(items, limit=10):
    return list(items)[-limit:]


def prune_stamps(ws):
    folder = Path(ws) / "health" / "netflow"
    if not folder.is_dir():
        return
    stamps = sorted(path for path in folder.glob("*.json") if path.is_file())
    for path in stamps[:-10]:
        path.unlink()


def fresh_stamp_id(ws, moment):
    folder = Path(ws) / "health" / "netflow"
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        name = stamp_name(moment)
        if not (folder / f"{name}.json").exists():
            return name, moment
        moment = moment + timedelta(seconds=1)


def resolve_workspace(given):
    raw = Path(strip_arg(given))
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
            print(f"netflow workspace={resolved}", file=sys.stderr)
            return resolved
    print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
    print("tried " + ", ".join(str(path) for path in seen), file=sys.stderr)
    return None


def locate_stamp(ws, given):
    text = strip_arg(given)
    rel = text[1:] if text.startswith("/") else text
    name = strip_arg(Path(rel).name)
    if name.endswith(".json"):
        name = name[:-5]
    candidates = []
    if rel:
        candidates.append(ws / rel)
        if not rel.endswith(".json"):
            candidates.append(ws / f"{rel}.json")
    if name:
        candidates.append(ws / "health" / "netflow" / f"{name}.json")
    for path in candidates:
        if path.is_file():
            return path
    return candidates[-1] if candidates else ws / "health" / "netflow" / "missing.json"


def exporter_row(raw, at, exporters, by_lower, access, nets):
    source = blank(raw.get("source"))
    if not source:
        return None
    name = blank(raw.get("exporter_name"))
    site = blank(raw.get("exporter_site"))
    device = resolve_exporter(source, name, exporters, by_lower, access, nets)
    keys = []
    for key in (device_key(device), site_key(site)):
        if key and key not in keys:
            keys.append(key)
    return {
        "kind": "exporter",
        "scope": f"exporter:{source}",
        "source": source,
        "exporter_name": name,
        "exporter_site": site,
        "device": device,
        "exporter": None,
        "src": None,
        "dst": None,
        "dst_port": None,
        "protocol": None,
        "src_device": None,
        "dst_device": None,
        "keys": keys,
        "at": at,
        "state": "reporting",
        "bytes": coerce_int(raw.get("bytes")) or 0,
        "flows": coerce_int(raw.get("flows")) or 0,
        "last_flow_at": blank(raw.get("last_at")),
        "last_seen_at": None,
    }


def conversation_row(raw, at, device_by_source, by_lower, access, nets):
    source = blank(raw.get("source"))
    src = blank(raw.get("src"))
    dst = blank(raw.get("dst"))
    dst_port = blank(raw.get("dst_port"))
    protocol = blank(raw.get("protocol"))
    if not source or not src or not dst or not dst_port or not protocol:
        return None
    src_device = resolve_flow(src, by_lower, access, nets)
    dst_device = resolve_flow(dst, by_lower, access, nets)
    exporter = device_by_source.get(source)
    keys = []
    for key in (device_key(exporter), device_key(src_device), device_key(dst_device)):
        if key and key not in keys:
            keys.append(key)
    return {
        "kind": "conversation",
        "scope": flow_scope(source, src, dst, dst_port, protocol),
        "source": source,
        "exporter_name": blank(raw.get("exporter_name")),
        "exporter_site": None,
        "device": None,
        "exporter": exporter,
        "src": src,
        "dst": dst,
        "dst_port": dst_port,
        "protocol": protocol,
        "src_device": src_device,
        "dst_device": dst_device,
        "keys": keys,
        "at": at,
        "state": "present",
        "bytes": coerce_int(raw.get("bytes")) or 0,
        "flows": coerce_int(raw.get("flows")) or 0,
        "last_flow_at": None,
        "last_seen_at": blank(raw.get("last_at")),
    }


def carry_exporter(prior, at):
    row = dict(prior)
    row["state"] = "silent"
    row["bytes"] = 0
    row["flows"] = 0
    row["at"] = at
    return row


def carry_conversation(prior, at):
    row = dict(prior)
    row["state"] = "absent"
    row["bytes"] = 0
    row["flows"] = 0
    row["at"] = at
    return row


def too_old(value, now):
    moment = canon_time(value)
    if moment is None:
        return False
    return now - moment > timedelta(days=7)


def byte_move(prior, current):
    old = coerce_int(prior) or 0
    new = coerce_int(current) or 0
    if old <= 0 or new <= 0:
        return False
    return new >= old * 4 or new <= old / 4


def material(row, prior):
    if prior is None:
        return "row", None, row["state"] if row["kind"] == "exporter" else "present"
    if row["state"] != prior.get("state"):
        return "state", prior.get("state"), row["state"]
    if row["kind"] == "conversation" and byte_move(prior.get("bytes"), row.get("bytes")):
        return "bytes", prior.get("bytes"), row.get("bytes")
    return None, None, None


def is_worse(row, prior):
    if row["kind"] == "exporter" and row["state"] == "silent" and (prior is None or prior.get("state") != "silent"):
        return prior is not None
    if row["kind"] == "conversation" and row["state"] == "absent" and (row.get("src_device") or row.get("dst_device")):
        return prior is not None and prior.get("state") != "absent"
    return False


def is_better(row, prior):
    if prior is None:
        return False
    return (prior.get("state"), row["state"]) in (("silent", "reporting"), ("absent", "present"))


def overall_delta(pairs, first):
    if first:
        return "first"
    if not pairs:
        return "unchanged"
    if any(is_worse(row, prior) for row, prior, _field in pairs):
        return "worse"
    if any(is_better(row, prior) for row, prior, _field in pairs) and not any(
        is_worse(row, prior) for row, prior, _field in pairs
    ):
        return "better"
    return "changed"


def note_for(row, prior, first):
    if first and not (row["kind"] == "exporter" and row["state"] == "silent"):
        return "Baseline."
    if row["kind"] == "exporter" and row["state"] == "silent":
        return f"Silent since {row.get('last_flow_at') or row['at']}."
    if row["kind"] == "exporter" and prior and prior.get("state") == "silent":
        return "Reporting again."
    if row["state"] == "absent":
        return "Absent this window."
    if prior is None:
        return "New row."
    if row["kind"] == "conversation":
        return f"Bytes {prior.get('bytes')} -> {row.get('bytes')}."
    return f"{prior.get('state')} -> {row['state']}."


def cap_board(rows):
    if len(rows) <= 120:
        return rows
    absent = [row for row in rows if row["state"] == "absent"]
    rest = [row for row in rows if row["state"] != "absent"]
    absent.sort(key=lambda row: row.get("last_seen_at") or "")
    overflow = len(rows) - 120
    return rest + absent[overflow:]


def estate(rows, at, top_scope):
    exporters = [row for row in rows if row["kind"] == "exporter"]
    conversations = [row for row in rows if row["kind"] == "conversation"]
    reporting = [row for row in exporters if row["state"] == "reporting"]
    return {
        "at": at,
        "scope": "estate",
        "exporters": len(reporting),
        "exporters_silent": sum(1 for row in exporters if row["state"] == "silent"),
        "exporters_unresolved": sum(1 for row in reporting if not row.get("device")),
        "flows": sum(row.get("flows") or 0 for row in reporting),
        "bytes": sum(row.get("bytes") or 0 for row in reporting),
        "conversations": sum(1 for row in conversations if row["state"] == "present"),
        "conversations_absent": sum(1 for row in conversations if row["state"] == "absent"),
        "top_scope": top_scope,
    }


def save_board(ws, board):
    visit_common.validate(board, BOARD_SCHEMA)
    visit_common.save_board(ws, "netflow", board)


def lookup_provenance(board, discovered):
    """Schema allows provenance.netflow only. The workspace board uses bucket, measurement, and window."""
    raw = board.get("provenance") if isinstance(board.get("provenance"), dict) else {}
    marks = [raw.get("netflow"), raw.get("bucket"), raw.get("measurement")]
    if discovered or "discovered" in marks:
        return {"netflow": "discovered"}
    if "user" in marks:
        return {"netflow": "user"}
    return None


def user_pinned(board):
    raw = board.get("provenance") if isinstance(board.get("provenance"), dict) else {}
    return raw.get("netflow") == "user" or raw.get("bucket") == "user" or raw.get("measurement") == "user"


def plane_block(board):
    """The lookup and rows. A nested netflow object, or the flat board already in the workspace."""
    nested = board.get("netflow")
    if isinstance(nested, dict) and (blank(nested.get("bucket")) or nested.get("current") or nested.get("exporters")):
        return nested
    flat_keys = (
        "bucket",
        "measurement",
        "window",
        "datasource_uid",
        "exporters",
        "last_visit_id",
        "last_collected_at",
        "baseline_visit_id",
        "current",
        "series",
        "visits",
    )
    if any(key in board for key in ("bucket", "measurement", "current", "exporters")):
        return {key: board[key] for key in flat_keys if key in board}
    return nested if isinstance(nested, dict) else {}


def cmd_collect(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    prod = visit_common.load_json(ws, "inventory/prod.json")
    if prod is None:
        print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
        return 1
    board = visit_common.load_board(ws, "netflow") or {}
    netflow = plane_block(board)
    pinned_user = user_pinned(board)
    window = blank(netflow.get("window")) or "1h"
    prior_bucket = blank(netflow.get("bucket")) or ""
    prior_measurement = blank(netflow.get("measurement")) or ""
    if prior_bucket.startswith("<"):
        prior_bucket = ""
    if prior_measurement.startswith("<"):
        prior_measurement = ""
    bucket = blank(args.bucket) or prior_bucket
    measurement = blank(args.measurement) or prior_measurement
    datasource = blank(args.datasource_uid) or blank(netflow.get("datasource_uid"))
    explicit = bool(blank(args.bucket) or blank(args.measurement) or blank(args.datasource_uid))
    f1_query, f2_query = flux_queries()
    if f1_query is None:
        return 1

    now = datetime.now(timezone.utc)
    at = checked_at(now)
    started = now - window_delta(window)
    first = not blank(netflow.get("baseline_visit_id"))
    prior_rows = keep(netflow.get("current") or [], fit_row)
    prior_by_scope = {row["scope"]: row for row in prior_rows}
    exporters = []
    for row in netflow.get("exporters") or []:
        if not isinstance(row, dict) or not blank(row.get("source")):
            continue
        item = {
            "source": row["source"],
            "exporter_name": blank(row.get("exporter_name")),
            "device": blank(row.get("device")),
        }
        if row.get("exporter_site") is not None:
            item["exporter_site"] = blank(row.get("exporter_site"))
        exporters.append(item)

    budget = visit_common.Budget(240)
    if budget.exhausted():
        print('{"error": "budget exhausted"}', file=sys.stderr)
        return 1
    f1_payload = None
    discovered = False
    lookup_note = None
    f1_error = None
    if bucket and measurement:
        f1_payload, f1_error = grafana_query("f1", substitute(f1_query, bucket, measurement), window, datasource)
    if not (f1_payload and f1_payload.get("rows")):
        tried = f"{bucket}/{measurement}" if bucket and measurement else "no lookup on the board"
        if pinned_user and prior_bucket and prior_measurement and not explicit:
            print(
                f"Need: bucket\nTried: {prior_bucket}/{prior_measurement} (empty)\nWhich bucket holds the NetFlow data now?",
                file=sys.stderr,
            )
            return 1
        skip = set()
        if bucket and measurement:
            skip.add((datasource or "", bucket, measurement))
        found_uid, found_bucket, found_measurement, f1_payload = discover_flows(
            f1_query, window, influx_uids(datasource), measurement, skip
        )
        if not f1_payload:
            reason = f1_error or f"F1 empty; tried {tried}; no other bucket returned rows"
            return write_unavailable(ws, board, netflow, at, window, reason)
        old = f"{prior_bucket}/{prior_measurement}" if prior_bucket else "none"
        lookup_note = f"bucket moved: {old} -> {found_bucket}/{found_measurement}"
        bucket, measurement, datasource = found_bucket, found_measurement, found_uid or datasource
        discovered = True
    f1_rows = f1_payload.get("rows") or []

    by_lower, access = prod_index(prod)
    nets = cidr_index(visit_common.load_json(ws, "inventory/topology-observed.json"))
    built_exporters = []
    for raw in f1_rows:
        if isinstance(raw, dict):
            row = exporter_row(raw, at, exporters, by_lower, access, nets)
            if row:
                built_exporters.append(row)
    if not built_exporters:
        return write_unavailable(ws, board, netflow, at, window, "F1 rows had no source")
    seen_sources = {row["source"] for row in built_exporters}
    device_by_source = {row["source"]: row.get("device") for row in built_exporters}

    f2_failed = False
    f2_rows = []
    truncated = bool(f1_payload.get("truncated"))
    if not budget.exhausted():
        f2_payload, f2_error = grafana_query("f2", substitute(f2_query, bucket, measurement), window, datasource)
        if f2_error or f2_payload is None:
            f2_failed = True
        else:
            f2_rows = f2_payload.get("rows") or []
            truncated = truncated or bool(f2_payload.get("truncated"))
    else:
        f2_failed = True

    conversations = []
    if not f2_failed:
        for raw in f2_rows:
            if isinstance(raw, dict):
                row = conversation_row(raw, at, device_by_source, by_lower, access, nets)
                if row:
                    conversations.append(row)
        seen_scopes = {row["scope"] for row in conversations}
        for prior in prior_rows:
            if prior["kind"] != "conversation" or prior["scope"] in seen_scopes:
                continue
            if too_old(prior.get("last_seen_at"), now):
                continue
            conversations.append(carry_conversation(prior, at))
    else:
        conversations = [row for row in prior_rows if row["kind"] == "conversation"]

    carried = []
    seen_exporter_scopes = {row["scope"] for row in built_exporters}
    for prior in prior_rows:
        if prior["kind"] == "exporter" and prior["scope"] not in seen_exporter_scopes:
            carried.append(carry_exporter(prior, at))
    current_rows = cap_board(built_exporters + carried + conversations)
    top = None
    present = [row for row in conversations if row["state"] == "present"]
    if present:
        top = max(present, key=lambda row: row.get("bytes") or 0)["scope"]

    pairs = []
    for row in current_rows:
        if f2_failed and row["kind"] == "conversation":
            continue
        prior = prior_by_scope.get(row["scope"])
        field, _prior_value, _current_value = material(row, prior)
        if field:
            pairs.append((row, prior, field))

    coverage = "partial" if f2_failed or truncated else "complete"
    status = "degraded" if any(row["kind"] == "exporter" and row["state"] == "silent" for row in current_rows) else "ok"
    delta = overall_delta(pairs, first)
    write_stamp = first or bool(pairs) or coverage != "complete"
    reading_rows = [row for row, _prior, _field in pairs]
    if first:
        reading_rows = list(current_rows)
    readings_truncated = len(reading_rows) > READINGS_CAP
    if readings_truncated:
        reading_rows = sorted(
            reading_rows,
            key=lambda row: (0 if row["kind"] == "exporter" and row["state"] == "silent" else 1, row["scope"]),
        )[:READINGS_CAP]
    prior_for = {row["scope"]: prior for row, prior, _field in pairs}
    readings = []
    for row in reading_rows:
        item = {field: row.get(field) for field in ROW_FIELDS}
        item["note"] = note_for(row, prior_for.get(row["scope"]), first)
        readings.append(item)
    reading_scopes = {row["scope"] for row in readings}
    unchanged = 0 if first else sum(1 for row in current_rows if row["scope"] not in reading_scopes)

    public_changed = []
    if not first:
        for row, prior, field in pairs:
            if row["scope"] not in reading_scopes:
                continue
            _field, prior_value, current_value = material(row, prior)
            public_changed.append(
                {
                    "keys": list(row["keys"]),
                    "field": field,
                    "prior": prior_value,
                    "current": current_value,
                    "at": row["at"],
                }
            )
        public_changed = public_changed[:READINGS_CAP]

    metric = estate(current_rows, at, top)
    prior_watch = blank(netflow.get("last_visit_id"))
    baseline = blank(netflow.get("baseline_visit_id"))
    watch = None
    stamp_rel = None
    if write_stamp:
        watch, moment = fresh_stamp_id(ws, now)
        at = checked_at(moment)
        metric["at"] = at
        headline = "Baseline." if first else f"{len(readings)} flow rows moved. {unchanged} board rows unchanged."
        if lookup_note:
            headline = f"{lookup_note}. {headline}"
        stamp = {
            "keys": union_keys(readings) or union_keys(current_rows),
            "schema": "health-netflow-check/v1",
            "source": "netflow",
            "watch_id": watch,
            "checked_at": at,
            "ok": status == "ok",
            "status": status,
            "headline": headline[:500],
            "window": window,
            "window_start": checked_at(moment - window_delta(window)),
            "window_end": at,
            "coverage": {
                "state": coverage,
                "detail": (
                    (lookup_note + "; " if lookup_note else "")
                    + ("F2 failed" if f2_failed else ("truncated" if truncated else "F1 and F2"))
                )[:500],
            },
            "metrics": [metric],
            "readings": readings,
            "unchanged": unchanged,
            "baseline_ref": None if first or not baseline else f"health/netflow/{baseline}.json",
            "vs_prior": {
                "prior_watch_id": None if first else prior_watch,
                "delta": "first" if first else delta,
                "changed": [] if first else public_changed,
            },
        }
        concerns = []
        for row in current_rows:
            if row["kind"] == "exporter" and row["state"] == "silent" and row.get("device"):
                concerns.append({"type": "device", "name": row["device"], "source_ref": "inventory/prod.json"})
        if concerns:
            stamp["concerns"] = concerns[:8]
        try:
            visit_common.validate(stamp, CHECK_SCHEMA)
        except ValueError as exc:
            print(f"stamp schema: {exc}", file=sys.stderr)
            return 1
        stamp_rel = f"health/netflow/{watch}.json"
        path = Path(ws) / stamp_rel
        path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        prune_stamps(ws)
        if first:
            baseline = watch

    for row in built_exporters:
        known = next((item for item in exporters if item.get("source") == row["source"]), None)
        if known is None:
            exporters.append(
                {
                    "source": row["source"],
                    "exporter_name": row.get("exporter_name"),
                    "exporter_site": row.get("exporter_site"),
                    "device": row.get("device"),
                }
            )
        elif row.get("device") and not known.get("device"):
            known["device"] = row["device"]

    series = keep(netflow.get("series") or [], fit_metric)
    series.append(metric)
    visit = {
        "watch_id": watch if write_stamp else None,
        "checked_at": at,
        "status": status,
        "coverage": coverage,
        "delta": "first" if first and write_stamp else delta,
        "stamp_written": bool(write_stamp),
        "window": window,
    }
    visits = keep(netflow.get("visits") or [], fit_visit)
    visits.append(visit)
    new_board = {
        "keys": union_keys(current_rows),
        "schema": "health-metadata-netflow/v1",
        "updated_at": at,
        "source_agent": "health-telemetry",
        "netflow": {
            "bucket": bucket,
            "measurement": measurement,
            "window": window,
            "exporters": exporters,
            "last_visit_id": watch if write_stamp else prior_watch,
            "last_collected_at": at,
            "baseline_visit_id": baseline if baseline else (watch if first and write_stamp else None),
            "current": current_rows,
            "series": ring(series),
            "visits": ring(visits),
        },
    }
    if datasource:
        new_board["netflow"]["datasource_uid"] = datasource
    elif "datasource_uid" in netflow:
        new_board["netflow"]["datasource_uid"] = netflow.get("datasource_uid")
    provenance = lookup_provenance(board, discovered)
    if provenance:
        new_board["provenance"] = provenance
    try:
        save_board(ws, new_board)
    except (ValueError, OSError) as exc:
        print(f"board: {exc}", file=sys.stderr)
        return 1

    needs = []
    if write_stamp and not first:
        for row, prior, field in pairs:
            if row["kind"] == "exporter" and row["state"] != "silent" and field == "row":
                continue
            if row["kind"] == "conversation" and field == "bytes":
                continue
            if not row["keys"]:
                continue
            _field, prior_value, current_value = material(row, prior)
            needs.append(
                {"keys": row["keys"], "field": field, "prior": prior_value, "current": current_value}
            )
    exporters_n = sum(1 for row in current_rows if row["kind"] == "exporter")
    silent_n = sum(1 for row in current_rows if row["kind"] == "exporter" and row["state"] == "silent")
    conv_n = sum(1 for row in current_rows if row["kind"] == "conversation")
    payload = {
        "plane": "netflow",
        "watch_id": watch if write_stamp else None,
        "stamp": stamp_rel,
        "status": status,
        "coverage": coverage,
        "delta": "first" if first and write_stamp else delta,
        "changed_count": 0 if first else len(public_changed),
        "unchanged": unchanged,
        "degraded": status == "degraded",
        "needs_note": needs[:8],
        "unresolved": [],
        "partial": coverage == "partial",
        "board_rows": len(current_rows),
        "last_visit_id": new_board["netflow"]["last_visit_id"],
        "board": f"{exporters_n} exporters ({silent_n} silent), {conv_n} conversations",
    }
    if readings_truncated:
        payload["readings_truncated"] = True
    print(visit_common.summary(payload))
    return 0


def write_unavailable(ws, board, netflow, at, window, reason):
    print(f"netflow unavailable: {reason}", file=sys.stderr)
    now = datetime.now(timezone.utc)
    watch, moment = fresh_stamp_id(ws, now)
    at = checked_at(moment)
    metric = null_metric(at)
    prior_rows = keep(netflow.get("current") or [], fit_row)
    stamp = {
        "keys": union_keys(prior_rows),
        "schema": "health-netflow-check/v1",
        "source": "netflow",
        "watch_id": watch,
        "checked_at": at,
        "ok": None,
        "status": "unknown",
        "headline": "NetFlow query failed.",
        "window": window,
        "window_start": checked_at(moment - window_delta(window)),
        "window_end": at,
        "coverage": {"state": "unavailable", "detail": str(reason)[:200]},
        "metrics": [metric],
        "readings": [],
        "unchanged": None,
        "baseline_ref": None,
        "vs_prior": {"prior_watch_id": blank(netflow.get("last_visit_id")), "delta": "unchanged", "changed": []},
    }
    try:
        visit_common.validate(stamp, CHECK_SCHEMA)
    except ValueError as exc:
        print(f"stamp schema: {exc}", file=sys.stderr)
        return 1
    stamp_rel = f"health/netflow/{watch}.json"
    path = Path(ws) / stamp_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    prune_stamps(ws)
    bucket = blank(netflow.get("bucket")) or "missing"
    measurement = blank(netflow.get("measurement")) or "missing"
    visit = {
        "watch_id": watch,
        "checked_at": at,
        "status": "unknown",
        "coverage": "unavailable",
        "delta": "unchanged",
        "stamp_written": True,
        "window": window,
    }
    visits = keep(netflow.get("visits") or [], fit_visit)
    visits.append(visit)
    series = keep(netflow.get("series") or [], fit_metric)
    series.append(metric)
    exporters = []
    for row in netflow.get("exporters") or []:
        if isinstance(row, dict) and blank(row.get("source")):
            exporters.append(
                {
                    "source": row["source"],
                    "exporter_name": blank(row.get("exporter_name")),
                    "device": blank(row.get("device")),
                }
            )
    new_board = {
        "keys": union_keys(prior_rows),
        "schema": "health-metadata-netflow/v1",
        "updated_at": at,
        "source_agent": "health-telemetry",
        "netflow": {
            "bucket": bucket,
            "measurement": measurement,
            "window": window,
            "exporters": exporters,
            "last_visit_id": watch,
            "last_collected_at": at,
            "baseline_visit_id": netflow.get("baseline_visit_id"),
            "current": prior_rows[:120],
            "series": ring(series),
            "visits": ring(visits),
        },
    }
    if "datasource_uid" in netflow:
        new_board["netflow"]["datasource_uid"] = netflow.get("datasource_uid")
    try:
        save_board(ws, new_board)
    except (ValueError, OSError) as exc:
        print(f"board: {exc}", file=sys.stderr)
        return 1
    print(
        visit_common.summary(
            {
                "plane": "netflow",
                "watch_id": watch,
                "stamp": stamp_rel,
                "status": "unknown",
                "coverage": "unavailable",
                "delta": "unchanged",
                "changed_count": 0,
                "unchanged": None,
                "degraded": False,
                "needs_note": [],
                "unresolved": [],
                "partial": False,
                "board_rows": len(prior_rows),
                "last_visit_id": watch,
            }
        )
    )
    return 0


def cmd_annotate(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    notes = {}
    for item in args.note or []:
        item = strip_arg(item)
        if "=" not in item:
            print("note must be <keys joined by +>=<text>", file=sys.stderr)
            return 1
        key, text = item.split("=", 1)
        notes[strip_arg(key).rstrip(">")] = strip_arg(text)
    stamp_path = locate_stamp(ws, args.stamp)
    if not stamp_path.is_file():
        print(f"stamp not found: {args.stamp}", file=sys.stderr)
        return 1
    try:
        visit_common.annotate(stamp_path, strip_arg(args.headline), notes, CHECK_SCHEMA)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    rel = stamp_path.relative_to(ws) if stamp_path.is_relative_to(ws) else stamp_path
    print(visit_common.summary({"plane": "netflow", "stamp": str(rel), "annotated": True}))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="NetFlow health visit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--workspace", required=True)
    collect.add_argument("--bucket", default=None)
    collect.add_argument("--measurement", default=None)
    collect.add_argument("--datasource-uid", default=None)
    collect.set_defaults(func=cmd_collect)
    note = sub.add_parser("annotate")
    note.add_argument("--workspace", required=True)
    note.add_argument("--stamp", required=True)
    note.add_argument("--headline", required=True)
    note.add_argument("--note", action="append", default=[])
    note.set_defaults(func=cmd_annotate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
