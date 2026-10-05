#!/usr/bin/env python3
"""Splunk health visit. One command collects, diffs, and writes the board.

collect runs under execution_type mcp_orchestration. annotate runs under
standard and only edits headline and notes. The searches and the material
rules are references/splunk.md. NetFlow is not this script.

The agent copies the path Studio shows for this file. Do not hardcode it.

  python3 <skill>/scripts/visit_splunk.py collect --workspace <file_explorer>
  python3 <skill>/scripts/visit_splunk.py annotate --workspace <file_explorer> \\
      --stamp health/splunk/<stamp>.json --headline "..." --note "device:NAME=..."
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
REF_PATH = Path(__file__).resolve().parent.parent / "references" / "splunk.md"
CHECK_SCHEMA = SCHEMA_DIR / "health-splunk-check.schema.json"
BOARD_SCHEMA = SCHEMA_DIR / "health-metadata-splunk.schema.json"

BUCKET_FIELD = {
    "bgp": "bgp_events",
    "link": "link_events",
    "config": "config_events",
    "reload": "reload_events",
    "acl": "acl_events",
    "auth_ok": "auth_ok",
    "auth_failed": "auth_failed",
    "ssh_no_match": "ssh_no_match",
}
ROW_FIELDS = (
    "name",
    "kind",
    "subject",
    "keys",
    "count",
    "at",
    "state",
    "source_ip",
    "peer",
    "detail",
)
METRIC_FIELDS = (
    "at",
    "scope",
    "name",
    "events",
    "bgp_events",
    "link_events",
    "config_events",
    "reload_events",
    "acl_events",
    "auth_ok",
    "auth_failed",
    "ssh_no_match",
)
CHANGED_CAP = 32
READINGS_CAP = 64
KEY_RE = re.compile(r"^(device|interface|site|service|test|control|incident|change):[^ ]+$")


def stamp_name(moment):
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


def checked_at(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def time_ge(left, right):
    left_at = canon_time(left)
    right_at = canon_time(right)
    if left_at and right_at:
        return left_at >= right_at
    return False


def canon_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0)


def coerce_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def blank(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def searches():
    text = REF_PATH.read_text(encoding="utf-8")
    blocks = re.findall(r"```\n(.*?)```", text, re.S)
    if len(blocks) < 2:
        print('{"error": "splunk.md is missing S1 and S2"}', file=sys.stderr)
        return None, None
    return blocks[0].strip() + "\n", blocks[1].strip() + "\n"


def substitute(search, index, sourcetype):
    return search.replace("index=<index>", f"index={index}", 1).replace(
        "sourcetype=<sourcetype>", f"sourcetype={sourcetype}", 1
    )


def splunk_search(label, query, earliest, latest):
    started = time.monotonic()
    envelope = visit_common.mcp_call(
        "splunk_search",
        {
            "query": query,
            "earliest_time": earliest,
            "latest_time": latest,
            "max_results": 200,
        },
        retries=1,
    )
    elapsed = time.monotonic() - started
    payload, error = visit_common.unwrap_splunk(envelope)
    shown = "ok" if error is None else str(error)[:120]
    print(
        f"splunk call={label} elapsed_s={elapsed:.3f} result={shown}",
        file=sys.stderr,
    )
    return payload, error


def expected_names(prod):
    names = []
    for device in prod.get("devices") or []:
        name = device.get("name")
        platform = str(device.get("platform") or "").lower()
        if name and platform != "linux":
            names.append(name)
    return names


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


def address_device(value, nets):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return None
    for net, name in nets:
        if ip in net:
            return name
    return None


def resolve_dev(dev, by_lower, hosts_map, access, nets):
    if not dev:
        return None, False
    if dev.lower() in by_lower:
        return by_lower[dev.lower()], True
    via_cidr = address_device(dev, nets)
    if via_cidr and via_cidr.lower() in by_lower:
        return by_lower[via_cidr.lower()], True
    pinned = hosts_map.get(dev)
    if pinned and pinned.lower() in by_lower:
        return by_lower[pinned.lower()], True
    for name, hosts in access.items():
        if dev in hosts:
            return name, True
    return dev, False


def row_key(name, kind, subject):
    return (name, kind, subject)


def fit_row(row):
    if not isinstance(row, dict):
        return None
    name = blank(row.get("name"))
    kind = blank(row.get("kind"))
    subject = blank(row.get("subject"))
    count = coerce_int(row.get("count"))
    at = blank(row.get("at"))
    if not name or kind not in BUCKET_FIELD or not subject or not count or count < 1 or not at:
        return None
    keys = [key for key in (row.get("keys") or []) if isinstance(key, str) and KEY_RE.match(key)]
    return {
        "name": name,
        "kind": kind,
        "subject": subject,
        "keys": keys[:8],
        "count": count,
        "at": at,
        "state": blank(row.get("state")),
        "source_ip": blank(row.get("source_ip")),
        "peer": blank(row.get("peer")),
        "detail": blank(row.get("detail")),
    }


def fit_metric(row):
    if not isinstance(row, dict):
        return None
    if not all(field in row for field in METRIC_FIELDS):
        return None
    scope = row.get("scope")
    if not isinstance(scope, str) or not re.match(r"^(estate|device:[^ ].*|host:[^ ].*)$", scope):
        return None
    return {field: row.get(field) for field in METRIC_FIELDS}


def fit_visit(row):
    if not isinstance(row, dict):
        return None
    needed = ("watch_id", "checked_at", "status", "coverage", "delta", "stamp_written", "window_start", "window_end")
    if not all(field in row for field in needed):
        return None
    if row.get("status") not in ("ok", "degraded", "unknown"):
        return None
    if row.get("coverage") not in ("complete", "partial", "unavailable"):
        return None
    if row.get("delta") not in ("first", "unchanged", "worse", "better", "changed"):
        return None
    return {field: row.get(field) for field in needed + ("silent", "unresolved") if field in row or field in needed}


def keep(rows, fit):
    kept = []
    for row in rows or []:
        item = fit(row)
        if item is not None:
            kept.append(item)
    return kept


def empty_metric(at, scope="estate", name=None):
    row = {field: None for field in METRIC_FIELDS}
    row["at"] = at
    row["scope"] = scope
    row["name"] = name
    return row


def metric_from_buckets(at, scope, name, buckets):
    row = empty_metric(at, scope, name)
    total = 0
    for bucket, count in buckets.items():
        total += count
        field = BUCKET_FIELD.get(bucket)
        if field:
            row[field] = (row[field] or 0) + count
    for field in BUCKET_FIELD.values():
        if row[field] is None:
            row[field] = 0
    row["events"] = total
    return row


def estate_metric(metrics, at):
    row = empty_metric(at)
    if not metrics:
        return row
    for field in (
        "events",
        "bgp_events",
        "link_events",
        "config_events",
        "reload_events",
        "acl_events",
        "auth_ok",
        "auth_failed",
        "ssh_no_match",
    ):
        values = [item.get(field) for item in metrics if isinstance(item.get(field), int)]
        row[field] = sum(values) if values else 0
    return row


def keys_for(name, kind, subject, peer, resolved):
    if not resolved:
        return []
    keys = []
    device_key = f"device:{name}"
    if KEY_RE.match(device_key):
        keys.append(device_key)
    if kind == "link" and subject and " " not in subject:
        interface_key = f"interface:{name}/{subject}"
        if KEY_RE.match(interface_key):
            keys.append(interface_key)
    if kind == "bgp" and peer and KEY_RE.match(peer) and peer not in keys:
        keys.append(peer)
    return keys[:8]


def peer_for(kind, subject, nets, by_lower):
    if kind != "bgp" or not subject:
        return None
    name = address_device(subject, nets)
    if name and name.lower() in by_lower:
        key = f"device:{by_lower[name.lower()]}"
        if KEY_RE.match(key):
            return key
    return None


def later(left, right):
    left_at = canon_time(left.get("at"))
    right_at = canon_time(right.get("at"))
    if left_at and right_at:
        return right if right_at >= left_at else left
    return right if right.get("at", "") >= left.get("at", "") else left


def degrades(row):
    kind = row.get("kind")
    state = (row.get("state") or "").lower()
    count = row.get("count") or 0
    if kind == "reload":
        return True
    if kind == "bgp" and (state in ("down", "active reset", "passive reset") or count >= 2):
        return True
    if kind == "link" and count >= 2:
        return True
    if kind == "link" and state == "down":
        return True
    return False


def concerns_kind(row):
    return degrades(row) or row.get("kind") == "auth_failed"


def change_item(row, prior):
    kind = row["kind"]
    count = row["count"]
    state = row.get("state") or ""
    if kind == "bgp":
        field = "bgp_state"
        current = f"{state} x{count}" if count >= 2 else state
        prior_value = None if prior is None else prior.get("state")
    elif kind == "link":
        field = "link_state"
        current = f"{state} x{count}" if count >= 2 else state
        prior_value = None if prior is None else prior.get("state")
    elif kind == "config":
        field = "config"
        current = f"{row['subject']} via {row.get('detail') or ''} from {row.get('source_ip') or ''}".strip()
        prior_value = None if prior is None else prior.get("at")
    elif kind == "reload":
        field = "reload"
        current = row.get("detail") or row["subject"]
        prior_value = None if prior is None else prior.get("at")
    elif kind == "acl":
        field = "acl"
        current = f"{state} x{count}"
        prior_value = None if prior is None else prior.get("at")
    else:
        field = "auth_failed"
        current = f"{row['subject']} from {row.get('source_ip') or ''} x{count}".strip()
        prior_value = None if prior is None else prior.get("at")
    return {
        "keys": list(row["keys"]),
        "field": field,
        "prior": prior_value,
        "current": current,
        "at": row["at"],
    }


def is_worse(row):
    return degrades(row) or row.get("kind") == "auth_failed"


def is_better(row):
    state = (row.get("state") or "").lower()
    return row.get("kind") in ("bgp", "link") and state in ("up",) and (row.get("count") or 0) == 1


def overall_delta(rows, first):
    if first:
        return "first"
    if not rows:
        return "unchanged"
    if any(is_worse(row) for row in rows):
        return "worse"
    if all(is_better(row) for row in rows):
        return "better"
    return "changed"


def union_keys(rows):
    found = []
    for row in rows:
        for key in row.get("keys") or []:
            if key not in found:
                found.append(key)
    return found


def ring(items, limit=10):
    return list(items)[-limit:]


def prune_stamps(ws):
    folder = Path(ws) / "health" / "splunk"
    if not folder.is_dir():
        return
    stamps = sorted(path for path in folder.glob("*.json") if path.is_file())
    for path in stamps[:-10]:
        path.unlink()


def fresh_stamp_id(ws, moment):
    folder = Path(ws) / "health" / "splunk"
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        name = stamp_name(moment)
        if not (folder / f"{name}.json").exists():
            return name, moment
        moment = moment + timedelta(seconds=1)


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
            print(f"splunk workspace={resolved}", file=sys.stderr)
            return resolved
    print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
    print("tried " + ", ".join(str(path) for path in seen), file=sys.stderr)
    return None


def group_s1(rows, by_lower, hosts_map, access, nets):
    grouped = {}
    unresolved = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        dev = blank(raw.get("dev"))
        bucket = blank(raw.get("bucket"))
        count = coerce_int(raw.get("count")) or 0
        if not dev or not bucket or count < 1:
            continue
        name, resolved = resolve_dev(dev, by_lower, hosts_map, access, nets)
        if not resolved and dev not in unresolved:
            unresolved.append(dev)
        slot = grouped.setdefault(name, {"resolved": resolved, "buckets": {}, "last_at": None, "devs": []})
        slot["resolved"] = slot["resolved"] or resolved
        slot["buckets"][bucket] = slot["buckets"].get(bucket, 0) + count
        slot["devs"].append(dev)
        last_at = blank(raw.get("last_at"))
        if last_at and (slot["last_at"] is None or time_ge(last_at, slot["last_at"])):
            slot["last_at"] = last_at
    return grouped, unresolved


def group_s2(rows, by_lower, hosts_map, access, nets):
    grouped = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        dev = blank(raw.get("dev"))
        kind = blank(raw.get("kind"))
        subject = blank(raw.get("subject"))
        count = coerce_int(raw.get("count"))
        at = blank(raw.get("at"))
        if not dev or kind not in ("bgp", "link", "config", "reload", "acl", "auth_failed"):
            continue
        if not subject or not count or count < 1 or not at:
            continue
        name, resolved = resolve_dev(dev, by_lower, hosts_map, access, nets)
        peer = peer_for(kind, subject, nets, by_lower) if resolved else None
        row = {
            "name": name,
            "kind": kind,
            "subject": subject,
            "keys": keys_for(name, kind, subject, peer, resolved),
            "count": count,
            "at": at,
            "state": blank(raw.get("state")),
            "source_ip": blank(raw.get("source_ip")),
            "peer": peer,
            "detail": blank(raw.get("detail")),
            "_resolved": resolved,
        }
        key = row_key(name, kind, subject)
        grouped[key] = later(grouped[key], row) if key in grouped else row
    return list(grouped.values())


def note_for(row, first):
    if first and not concerns_kind(row):
        return "Baseline."
    kind = row["kind"]
    if kind == "config":
        return f"{row['subject']} via {row.get('detail') or 'unknown'}."
    if kind == "acl":
        return f"{row.get('state') or 'logged'} x{row['count']}."
    if kind in ("bgp", "link") and (row.get("count") or 0) >= 2:
        return "Flapped."
    if row.get("state"):
        return f"{row['state']}."
    return f"{kind} at {row['at']}."


def cmd_collect(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    prod = visit_common.load_json(ws, "inventory/prod.json")
    if prod is None:
        print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
        return 1
    board = visit_common.load_board(ws, "splunk") or {}
    splunk = board.get("splunk") if isinstance(board.get("splunk"), dict) else {}
    index = blank(splunk.get("index"))
    sourcetype = blank(splunk.get("sourcetype"))
    if not index or not sourcetype or index.startswith("<") or sourcetype.startswith("<"):
        print('{"error": "splunk.index or splunk.sourcetype missing on the board"}', file=sys.stderr)
        return 1
    s1, s2 = searches()
    if s1 is None:
        return 1

    now = datetime.now(timezone.utc)
    at = checked_at(now)
    watermark = blank(splunk.get("collected_through"))
    earliest = watermark or "-7d"
    window_label = "watermark" if watermark else "baseline"
    first = not keep(splunk.get("current") or [], fit_row)
    prior_rows = keep(splunk.get("current") or [], fit_row)
    prior_by_id = {row_key(row["name"], row["kind"], row["subject"]): row for row in prior_rows}

    budget = visit_common.Budget(240)
    if budget.exhausted():
        print('{"error": "budget exhausted"}', file=sys.stderr)
        return 1
    s1_payload, s1_error = splunk_search("s1", substitute(s1, index, sourcetype), earliest, "now")
    if s1_error or s1_payload is None:
        return write_unavailable(ws, board, splunk, at, earliest, s1_error or "s1 failed")
    s1_truncated = bool(s1_payload.get("truncated"))
    if budget.exhausted():
        return write_unavailable(ws, board, splunk, at, earliest, "budget")
    s2_payload, s2_error = splunk_search("s2", substitute(s2, index, sourcetype), earliest, "now")
    s2_truncated = bool(s2_payload and s2_payload.get("truncated"))
    s2_failed = s2_error is not None or s2_payload is None

    by_lower, access = prod_index(prod)
    hosts_map = splunk.get("hosts") if isinstance(splunk.get("hosts"), dict) else {}
    nets = cidr_index(visit_common.load_json(ws, "inventory/topology-observed.json"))
    grouped, unresolved = group_s1(s1_payload.get("results") or [], by_lower, hosts_map, access, nets)
    s2_rows = [] if s2_failed else group_s2(s2_payload.get("results") or [], by_lower, hosts_map, access, nets)

    metrics = []
    latest_event = None
    seen_names = set()
    for name, slot in sorted(grouped.items()):
        scope = f"device:{name}" if slot["resolved"] else f"host:{name}"
        if not re.match(r"^(device|host):[^ ].*$", scope):
            scope = f"host:{name.replace(' ', '_')}"
        metrics.append(metric_from_buckets(at, scope, name, slot["buckets"]))
        if slot["resolved"]:
            seen_names.add(name)
        last_at = slot["last_at"]
        if last_at and (latest_event is None or time_ge(last_at, latest_event)):
            latest_event = last_at
    if not metrics:
        metrics = [estate_metric([], at)]

    expected = expected_names(prod)
    silent = [name for name in expected if name not in seen_names]
    coverage = "partial" if s2_failed or s1_truncated or s2_truncated else "complete"

    current_map = {row_key(row["name"], row["kind"], row["subject"]): row for row in prior_rows}
    changed_rows = []
    for row in s2_rows:
        key = row_key(row["name"], row["kind"], row["subject"])
        prior = prior_by_id.get(key)
        stored = {field: row[field] for field in ROW_FIELDS}
        current_map[key] = stored
        changed_rows.append((stored, prior))
    current_rows = list(current_map.values())
    current_rows.sort(key=lambda row: row.get("at") or "")
    if len(current_rows) > 120:
        print(f"splunk board rows {len(current_rows)} capped at 120", file=sys.stderr)
        current_rows = current_rows[-120:]

    status = "degraded" if any(degrades(row) for row, _prior in changed_rows) else "ok"
    delta = overall_delta([row for row, _prior in changed_rows], first)
    write_stamp = first or bool(changed_rows) or coverage != "complete"
    reading_source = [row for row, _prior in changed_rows]
    readings_truncated = len(reading_source) > READINGS_CAP
    if readings_truncated:
        reading_source = sorted(reading_source, key=lambda row: (0 if concerns_kind(row) else 1, row["name"]))[:READINGS_CAP]
    readings = []
    for row in reading_source:
        item = dict(row)
        item["note"] = note_for(row, first)
        readings.append(item)
    reading_ids = {row_key(row["name"], row["kind"], row["subject"]) for row in readings}
    unchanged = 0 if first else sum(1 for row in current_rows if row_key(row["name"], row["kind"], row["subject"]) not in reading_ids)

    public_changed = []
    for row, prior in changed_rows:
        if row_key(row["name"], row["kind"], row["subject"]) not in reading_ids:
            continue
        public_changed.append(change_item(row, prior))
    public_changed = public_changed[:CHANGED_CAP]

    prior_watch = blank(splunk.get("last_visit_id"))
    baseline = blank(splunk.get("baseline_visit_id"))
    watch = None
    stamp_rel = None
    if write_stamp:
        watch, moment = fresh_stamp_id(ws, now)
        at = checked_at(moment)
        for row in metrics:
            row["at"] = at
        for row in readings:
            if row["note"] == "Baseline." or first:
                pass
        headline = "Baseline." if first else f"{len(readings)} syslog rows. {unchanged} board rows unchanged."
        stamp = {
            "keys": union_keys(readings) or union_keys(current_rows),
            "schema": "health-splunk-check/v3",
            "source": "splunk",
            "watch_id": watch,
            "checked_at": at,
            "ok": status == "ok",
            "status": status,
            "headline": headline[:500],
            "window": window_label,
            "window_start": earliest,
            "window_end": "now",
            "coverage": {"state": coverage, "detail": _detail(s2_failed, s1_truncated or s2_truncated)},
            "metrics": metrics,
            "readings": readings,
            "unchanged": unchanged,
            "baseline_ref": None if first or not baseline else f"health/splunk/{baseline}.json",
            "vs_prior": {
                "prior_watch_id": None if first else prior_watch,
                "delta": "first" if first else delta,
                "changed": [] if first else public_changed,
            },
        }
        concern_names = []
        for row, _prior in changed_rows:
            if concerns_kind(row) and row["name"] not in concern_names and row.get("keys"):
                concern_names.append(row["name"])
        concerns = [
            {"type": "device", "name": name, "source_ref": "inventory/prod.json"}
            for name in concern_names[:8]
        ]
        if concerns:
            stamp["concerns"] = concerns
        try:
            visit_common.validate(stamp, CHECK_SCHEMA)
        except ValueError as exc:
            print(f"stamp schema: {exc}", file=sys.stderr)
            return 1
        stamp_rel = f"health/splunk/{watch}.json"
        path = Path(ws) / stamp_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        prune_stamps(ws)
        if first:
            baseline = watch

    advance = coverage == "complete" and not s2_failed
    new_through = splunk.get("collected_through")
    if advance:
        candidate = latest_event or at
        old = canon_time(splunk.get("collected_through"))
        new = canon_time(candidate)
        if old is None or (new is not None and new >= old) or new is None:
            new_through = candidate

    series = keep(splunk.get("series") or [], fit_metric)
    series.append(estate_metric(metrics, at))
    visit = {
        "watch_id": watch if write_stamp else None,
        "checked_at": at,
        "status": status,
        "coverage": coverage,
        "delta": "first" if first and write_stamp else (delta if delta != "first" else "changed"),
        "stamp_written": bool(write_stamp),
        "window_start": earliest,
        "window_end": "now",
        "silent": silent[:100],
        "unresolved": unresolved[:100],
    }
    visits = keep(splunk.get("visits") or [], fit_visit)
    visits.append(visit)
    new_board = {
        "keys": union_keys(current_rows),
        "schema": "health-metadata-splunk/v2",
        "updated_at": at,
        "source_agent": "health-logging",
        "splunk": {
            "index": index,
            "sourcetype": sourcetype,
            "collected_through": new_through,
            "last_visit_id": watch if write_stamp else prior_watch,
            "last_collected_at": at,
            "baseline_visit_id": baseline if baseline else (watch if first and write_stamp else None),
            "current": current_rows,
            "series": ring(series),
            "visits": ring(visits),
        },
    }
    if isinstance(splunk.get("dashboard_id"), str) or splunk.get("dashboard_id") is None and "dashboard_id" in splunk:
        new_board["splunk"]["dashboard_id"] = splunk.get("dashboard_id")
    if isinstance(splunk.get("hosts"), dict):
        new_board["splunk"]["hosts"] = splunk.get("hosts")
    if isinstance(board.get("provenance"), dict):
        new_board["provenance"] = board["provenance"]
    try:
        visit_common.validate(new_board, BOARD_SCHEMA)
    except ValueError as exc:
        print(f"board schema: {exc}", file=sys.stderr)
        return 1
    try:
        visit_common.save_board(ws, "splunk", new_board)
    except OSError as exc:
        print(f"board write: {exc}", file=sys.stderr)
        return 1

    needs = []
    if write_stamp and not first:
        for row, prior in changed_rows:
            if not concerns_kind(row):
                continue
            item = change_item(row, prior)
            if not item["keys"]:
                continue
            needs.append(
                {
                    "keys": item["keys"],
                    "field": item["field"],
                    "prior": item["prior"],
                    "current": item["current"],
                }
            )
    devices_line = f"{len(seen_names)} of {len(expected)} logged; Silent: {', '.join(silent) if silent else 'none'}; Unresolved: {', '.join(unresolved) if unresolved else 'none'}"
    payload = {
        "plane": "splunk",
        "watch_id": watch if write_stamp else None,
        "stamp": stamp_rel,
        "status": status,
        "coverage": coverage,
        "delta": "first" if first and write_stamp else delta,
        "changed_count": 0 if first else len(public_changed),
        "unchanged": unchanged,
        "degraded": status == "degraded",
        "needs_note": needs[:8],
        "unresolved": unresolved[:20],
        "partial": coverage == "partial",
        "board_rows": len(current_rows),
        "last_visit_id": new_board["splunk"]["last_visit_id"],
        "devices": devices_line,
    }
    if readings_truncated:
        payload["readings_truncated"] = True
    print(visit_common.summary(payload))
    return 0


def _detail(s2_failed, truncated):
    if s2_failed and truncated:
        return "S2 failed; S1 truncated"
    if s2_failed:
        return "S2 failed"
    if truncated:
        return "search truncated at max_results"
    return "S1 and S2"


def write_unavailable(ws, board, splunk, at, earliest, reason):
    print(f"splunk unavailable: {reason}", file=sys.stderr)
    now = datetime.now(timezone.utc)
    watch, moment = fresh_stamp_id(ws, now)
    at = checked_at(moment)
    metric = empty_metric(at)
    stamp = {
        "keys": [],
        "schema": "health-splunk-check/v3",
        "source": "splunk",
        "watch_id": watch,
        "checked_at": at,
        "ok": None,
        "status": "unknown",
        "headline": "Splunk search failed.",
        "window": "watermark" if earliest != "-7d" else "baseline",
        "window_start": earliest,
        "window_end": "now",
        "coverage": {"state": "unavailable", "detail": str(reason)[:200]},
        "metrics": [metric],
        "readings": [],
        "unchanged": None,
        "baseline_ref": None,
        "vs_prior": {"prior_watch_id": blank(splunk.get("last_visit_id")), "delta": "unchanged", "changed": []},
    }
    try:
        visit_common.validate(stamp, CHECK_SCHEMA)
    except ValueError as exc:
        print(f"stamp schema: {exc}", file=sys.stderr)
        return 1
    stamp_rel = f"health/splunk/{watch}.json"
    path = Path(ws) / stamp_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    prune_stamps(ws)
    prior_rows = keep(splunk.get("current") or [], fit_row)
    index = blank(splunk.get("index")) or "missing"
    sourcetype = blank(splunk.get("sourcetype")) or "missing"
    visit = {
        "watch_id": watch,
        "checked_at": at,
        "status": "unknown",
        "coverage": "unavailable",
        "delta": "unchanged",
        "stamp_written": True,
        "window_start": earliest,
        "window_end": "now",
    }
    visits = keep(splunk.get("visits") or [], fit_visit)
    visits.append(visit)
    series = keep(splunk.get("series") or [], fit_metric)
    series.append(metric)
    new_board = {
        "keys": union_keys(prior_rows),
        "schema": "health-metadata-splunk/v2",
        "updated_at": at,
        "source_agent": "health-logging",
        "splunk": {
            "index": index,
            "sourcetype": sourcetype,
            "collected_through": splunk.get("collected_through"),
            "last_visit_id": watch,
            "last_collected_at": at,
            "baseline_visit_id": splunk.get("baseline_visit_id"),
            "current": prior_rows[:120],
            "series": ring(series),
            "visits": ring(visits),
        },
    }
    if isinstance(splunk.get("hosts"), dict):
        new_board["splunk"]["hosts"] = splunk["hosts"]
    try:
        visit_common.validate(new_board, BOARD_SCHEMA)
        visit_common.save_board(ws, "splunk", new_board)
    except (ValueError, OSError) as exc:
        print(f"board: {exc}", file=sys.stderr)
        return 1
    print(
        visit_common.summary(
            {
                "plane": "splunk",
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
    print(visit_common.summary({"plane": "splunk", "stamp": args.stamp, "annotated": True}))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="Splunk health visit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--workspace", required=True)
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
