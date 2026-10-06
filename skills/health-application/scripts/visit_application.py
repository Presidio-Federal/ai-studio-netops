#!/usr/bin/env python3
"""Application health visit. One command collects, diffs, and writes the board.

collect runs under execution_type mcp_orchestration. annotate runs under
standard and only edits headline and notes. The expressions and the
material rules are references/prometheus.md.

The agent copies the path Studio shows for this file. Do not hardcode it.

  python3 <skill>/scripts/visit_application.py collect --workspace <file_explorer>
  python3 <skill>/scripts/visit_application.py annotate --workspace <file_explorer> \\
      --stamp health/application/<stamp>.json --headline "..." --note "application:NAME=..."
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
REF_PATH = Path(__file__).resolve().parent.parent / "references" / "prometheus.md"
CHECK_SCHEMA = SCHEMA_DIR / "health-application-check.schema.json"
BOARD_SCHEMA = SCHEMA_DIR / "health-metadata-application.schema.json"
EXPR_ORDER = ("P1", "P2", "P3", "P4", "P5", "P6", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "H1", "H2", "H3", "H4")
OPTIONAL_EXPR = {"P5", "P6", "C5", "C6", "C7", "C8"}
DEFAULT_VANTAGES = ("cloud", "hq", "branch")
KEY_RE = re.compile(r"^(device|site|application|test):[^ ]+$")
READINGS_CAP = 60


def stamp_name(moment):
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


def checked_at(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def blank(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def whole(value):
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def decimal(value):
    if value is None or value == "":
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def load_exprs():
    text = REF_PATH.read_text(encoding="utf-8")
    found = dict(re.findall(r"\*\*([PCH]\d)\*\* `([^`]+)`", text))
    if any(name not in found for name in EXPR_ORDER):
        print('{"error": "prometheus.md is missing an expression"}', file=sys.stderr)
        return None
    return found


def tool_body(label, tool, args):
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
    print(f"application call={label} elapsed_s={elapsed:.3f} result={shown}", file=sys.stderr)
    return inner, error


def prom_series(label, expr, timerange, datasource_uid):
    args = {"expr": expr, "timerange": timerange, "instant": True}
    if datasource_uid:
        args["datasource_uid"] = datasource_uid
    inner, error = tool_body(label, "grafana_query_prometheus", args)
    if error or not inner:
        return None, error or "empty"
    found = []
    truncated = bool(inner.get("truncated"))
    for item in inner.get("series") or []:
        if not isinstance(item, dict):
            continue
        labels = dict(item.get("labels") or {})
        value = None
        rows = item.get("rows") or []
        if rows and isinstance(rows[-1], dict):
            for key, val in rows[-1].items():
                if key in ("Time", "_time"):
                    continue
                if isinstance(val, (int, float)):
                    value = val
                elif val is not None and key not in labels:
                    labels[key] = val
        found.append({"labels": labels, "value": value})
        truncated = truncated or bool(item.get("truncated"))
    return {"series": found, "truncated": truncated}, None


def label_of(item, *names):
    labels = item.get("labels") or {}
    for name in names:
        text = blank(labels.get(name))
        if text:
            return text
    return None


def index_by(series, *names):
    found = {}
    for item in series or []:
        key = tuple(label_of(item, name) for name in names)
        if None in key:
            continue
        found[key] = item
    return found


def prod_names(prod):
    found = {}
    for device in prod.get("devices") or []:
        name = device.get("name")
        if name:
            found[str(name).lower()] = name
    return found


def device_for(host, by_lower):
    if not host:
        return None
    return by_lower.get(str(host).lower())


def key_list(*items):
    found = []
    for item in items:
        if item and item not in found and KEY_RE.match(item):
            found.append(item)
    return found[:8]


def app_key(service):
    if not service:
        return None
    return f"application:{service}"


def site_key(site):
    if not site:
        return None
    return f"site:{site}"


def device_key(name):
    if not name:
        return None
    return f"device:{name}"


def part(value):
    text = str(value or "none").replace(" ", "")
    return text or "none"


def window_seconds(window):
    match = re.fullmatch(r"(\d+)([smhd])", window or "")
    if not match:
        return 3600
    return int(match.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]


def finite_limit(value):
    number = whole(value)
    if number is None or number <= 0 or number >= 2**60:
        return None
    return number


def probe_rows(results, by_lower, window):
    p1 = (results.get("P1") or {}).get("series") or []
    p2 = index_by((results.get("P2") or {}).get("series"), "instance")
    p3 = index_by((results.get("P3") or {}).get("series"), "instance")
    p4 = index_by((results.get("P4") or {}).get("series"), "instance")
    p5 = index_by((results.get("P5") or {}).get("series"), "instance")
    p6 = index_by((results.get("P6") or {}).get("series"), "instance")
    span = window_seconds(window)
    rows = []
    for item in p1:
        instance = label_of(item, "instance")
        service = label_of(item, "service") or "none"
        environment = label_of(item, "environment", "env", "site") or "none"
        vantage = label_of(item, "vantage_point") or "none"
        site = label_of(item, "site")
        success = whole(item.get("value"))
        if success not in (0, 1):
            success = None
        http = whole((p2.get((instance,)) or {}).get("value")) if instance else None
        duration = whole(((p3.get((instance,)) or {}).get("value") or 0) * 1000) if instance and (instance,) in p3 else None
        pct = whole((p4.get((instance,)) or {}).get("value")) if instance else None
        content = None
        if instance and (instance,) in p5:
            failed_body = whole((p5.get((instance,)) or {}).get("value"))
            content = 0 if failed_body else 1
        latency = whole((p6.get((instance,)) or {}).get("value")) if instance and (instance,) in p6 else None
        if success is None:
            state = "unknown"
        elif success == 0 or content == 0:
            state = "down"
        elif content is None:
            state = "unvalidated"
        else:
            state = "up"
        missing = []
        if not instance or (instance,) not in p2:
            missing.append("http_code")
        if content is None:
            missing.append("content")
        if pct is None:
            missing.append("fail_pct")
        if latency is None:
            missing.append("latency_window")
        if duration is None:
            missing.append("duration")
        app_name = service if service != "none" else None
        env_name = environment if environment != "none" else None
        rows.append(
            {
                "kind": "probe",
                "scope": f"probe:{part(service)}@{part(environment)}@{part(instance)}@{part(vantage)}",
                "application": app_name,
                "environment": env_name,
                "vantage_site": vantage if vantage != "none" else None,
                "site": site,
                "target": instance,
                "success": success,
                "http_code": http,
                "content_ok": content,
                "duration_ms": duration,
                "latency_ms_window": latency,
                "success_pct_window": pct,
                "fail_pct_window": None if pct is None else max(0, 100 - pct),
                "fail_seconds_window": None if pct is None else int(round((max(0, 100 - pct) / 100) * span)),
                "missing": missing,
                "state": state,
                "keys": key_list(
                    app_key(app_name),
                    site_key(site),
                    f"test:probe/{part(service)}@{part(environment)}@{part(instance)}@{part(vantage)}",
                ),
            }
        )
    return rows


def container_rows(results, by_lower):
    c1 = (results.get("C1") or {}).get("series") or []
    c2 = index_by((results.get("C2") or {}).get("series"), "name", "instance")
    c3 = index_by((results.get("C3") or {}).get("series"), "name", "instance")
    c4 = index_by((results.get("C4") or {}).get("series"), "name", "instance")
    c5 = index_by((results.get("C5") or {}).get("series"), "name", "instance")
    c6 = index_by((results.get("C6") or {}).get("series"), "name", "instance")
    c7 = index_by((results.get("C7") or {}).get("series"), "name", "instance")
    c8 = index_by((results.get("C8") or {}).get("series"), "name", "instance")
    rows = []
    for item in c1:
        labels = item.get("labels") or {}
        name = label_of(item, "name")
        instance = label_of(item, "instance")
        host = label_of(item, "host_name", "instance")
        if not name or not host:
            continue
        service = label_of(item, "service")
        device = device_for(host, by_lower)
        pair = (name, instance) if instance else None
        cpu = decimal((c2.get(pair) or {}).get("value")) if pair else None
        mem = whole((c3.get(pair) or {}).get("value")) if pair and pair in c3 else None
        rx = whole((c4.get(pair) or {}).get("value")) if pair and pair in c4 else None
        mem_limit = finite_limit((c5.get(pair) or {}).get("value")) if pair and pair in c5 else None
        cpu_limit = decimal((c6.get(pair) or {}).get("value")) if pair and pair in c6 else None
        if cpu_limit is not None and (cpu_limit <= 0 or cpu_limit > 1024):
            cpu_limit = None
        throttled = decimal((c7.get(pair) or {}).get("value")) if pair and pair in c7 else None
        oom = whole((c8.get(pair) or {}).get("value")) if pair and pair in c8 else None
        missing = ["exit"]
        if mem_limit is None:
            missing.append("mem_limit")
        if cpu_limit is None:
            missing.append("cpu_limit")
        if throttled is None:
            missing.append("throttle")
        if oom is None:
            missing.append("oom")
        rows.append(
            {
                "kind": "container",
                "scope": f"container:{host}/{name}",
                "name": name,
                "host": host,
                "device": device,
                "application": service,
                "service": label_of(item, "application"),
                "site": label_of(item, "site"),
                "image": label_of(item, "image"),
                "started_epoch": whole(item.get("value")),
                "cpu_pct": cpu,
                "cpu_limit": cpu_limit,
                "cpu_throttled_s": throttled,
                "mem_bytes": mem,
                "mem_limit_bytes": mem_limit,
                "rx_bytes_s": rx,
                "oom_events": oom,
                "missing": missing,
                "state": "running",
                "keys": key_list(app_key(service), device_key(device), site_key(label_of(item, "site"))),
            }
        )
    return rows


def host_rows(results, by_lower):
    h1 = (results.get("H1") or {}).get("series") or []
    h2 = {}
    h3 = {}
    for item in (results.get("H2") or {}).get("series") or []:
        host = label_of(item, "host_name", "instance")
        if host:
            h2[host] = item.get("value")
    for item in (results.get("H3") or {}).get("series") or []:
        host = label_of(item, "host_name", "instance")
        if host:
            h3[host] = item.get("value")
    down = {}
    up = {}
    h4_ok = "H4" in results and results.get("H4") is not None
    for item in (results.get("H4") or {}).get("series") or []:
        host = label_of(item, "host_name", "instance")
        iface = label_of(item, "device")
        if not host:
            continue
        value = whole(item.get("value"))
        if value == 0 and iface:
            down.setdefault(host, []).append(iface)
        elif value == 1:
            up[host] = up.get(host, 0) + 1
    rows = []
    for item in h1:
        host = label_of(item, "host_name", "instance")
        if not host:
            continue
        device = device_for(host, by_lower)
        site = label_of(item, "site")
        ifaces = sorted(down.get(host) or []) if h4_ok else None
        rows.append(
            {
                "kind": "host",
                "scope": f"host:{host}",
                "host": host,
                "device": device,
                "site": site,
                "role": label_of(item, "role"),
                "boot_epoch": whole(item.get("value")),
                "mem_available_pct": whole(h2.get(host)),
                "fs_root_avail_pct": whole(h3.get(host)),
                "interfaces_down": ifaces,
                "interfaces_up": up.get(host, 0) if h4_ok else None,
                "state": "up",
                "keys": key_list(device_key(device), site_key(site)),
            }
        )
    return rows


def target_rows(targets, by_lower):
    rows = []
    for item in targets or []:
        if not isinstance(item, dict):
            continue
        labels = item.get("labels") or {}
        job = blank(labels.get("job"))
        instance = blank(labels.get("instance"))
        url = blank(item.get("scrapeUrl")) or ""
        if not job or not instance or job == "prometheus":
            continue
        if "/probe?" not in url and job == "prometheus":
            continue
        host = blank(labels.get("host_name"))
        device = device_for(host, by_lower)
        health = blank(item.get("health")) or "unknown"
        if health not in ("up", "down", "unknown"):
            health = "unknown"
        rows.append(
            {
                "kind": "target",
                "scope": f"target:{job}/{instance}",
                "scrape_pool": job,
                "instance": instance,
                "host": host,
                "device": device,
                "health": health,
                "last_error": blank(item.get("lastError")),
                "last_scrape": blank(item.get("lastScrape")),
                "state": health,
                "keys": key_list(device_key(device)),
            }
        )
    return rows


def probe_jobs(targets):
    found = []
    for item in targets or []:
        if not isinstance(item, dict):
            continue
        url = blank(item.get("scrapeUrl")) or ""
        job = blank((item.get("labels") or {}).get("job"))
        if job and "/probe?" in url and job not in found:
            found.append(job)
    return found


def carry(prior, at, state):
    row = dict(prior)
    row["state"] = state
    row["at"] = at
    return row


def crossed(prior, current, line):
    if prior is None or current is None:
        return False
    return (prior >= line) != (current >= line)


def iface_text(value):
    if value is None:
        return None
    if isinstance(value, list):
        return ",".join(value)
    return str(value)


def latency_limit(app):
    raw = app.get("latency_threshold_ms") if isinstance(app, dict) else None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 500
    return value if value > 0 else 500


def duration_moved(row, prior, threshold):
    current = row.get("duration_ms")
    if not isinstance(current, int):
        return False
    previous = prior.get("duration_ms")
    if isinstance(previous, bool) or not isinstance(previous, int):
        previous = None
    over_now = current > threshold
    over_then = previous is not None and previous > threshold
    if over_now != over_then:
        return True
    if previous is not None and previous > 0:
        return current >= previous * 3 or previous >= current * 3
    return False


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def throttle_moved(row, prior):
    return positive(row.get("cpu_throttled_s")) != positive(prior.get("cpu_throttled_s"))


def oom_moved(row, prior):
    current = row.get("oom_events")
    previous = prior.get("oom_events")
    if not isinstance(current, int):
        return False
    if not isinstance(previous, int):
        return current > 0
    return (current > 0 or previous > 0) and current != previous


def pressure(row):
    limit = row.get("mem_limit_bytes")
    used = row.get("mem_bytes")
    if not isinstance(limit, int) or limit <= 0 or not isinstance(used, int):
        return None
    return 100 * used / limit


def pressure_moved(row, prior):
    current = pressure(row)
    previous = pressure(prior)
    if current is None or previous is None:
        return False
    return (previous >= 90) != (current >= 90)


def material(row, prior, threshold):
    if prior is None:
        return "row", None, row.get("state")
    kind = row["kind"]
    if kind == "probe":
        if row.get("success") != prior.get("success"):
            return "success", prior.get("success"), row.get("success")
        if row.get("http_code") != prior.get("http_code"):
            return "http_code", prior.get("http_code"), row.get("http_code")
        if row.get("content_ok") != prior.get("content_ok"):
            return "content_ok", prior.get("content_ok"), row.get("content_ok")
        if row.get("latency_ms_window") is not None and duration_moved(
            {"duration_ms": row.get("latency_ms_window")},
            {"duration_ms": prior.get("latency_ms_window")},
            threshold,
        ):
            return "latency_ms_window", prior.get("latency_ms_window"), row.get("latency_ms_window")
        if row.get("latency_ms_window") is None and duration_moved(row, prior, threshold):
            return "duration_ms", prior.get("duration_ms"), row.get("duration_ms")
    elif kind == "container":
        old = prior.get("started_epoch")
        new = row.get("started_epoch")
        if old is not None and new is not None and abs(new - old) > 60:
            return "started_epoch", old, new
        if row.get("state") != prior.get("state"):
            return "state", prior.get("state"), row.get("state")
        if crossed(prior.get("cpu_pct"), row.get("cpu_pct"), 80):
            return "cpu_pct", prior.get("cpu_pct"), row.get("cpu_pct")
        if throttle_moved(row, prior):
            return "cpu_throttled_s", prior.get("cpu_throttled_s"), row.get("cpu_throttled_s")
        if oom_moved(row, prior):
            return "oom_events", prior.get("oom_events"), row.get("oom_events")
        if pressure_moved(row, prior):
            return "mem_limit_bytes", prior.get("mem_bytes"), row.get("mem_bytes")
    elif kind == "host":
        old = prior.get("boot_epoch")
        new = row.get("boot_epoch")
        if old is not None and new is not None and abs(new - old) > 60:
            return "boot_epoch", old, new
        if iface_text(row.get("interfaces_down")) != iface_text(prior.get("interfaces_down")):
            return "interfaces_down", iface_text(prior.get("interfaces_down")), iface_text(row.get("interfaces_down"))
        if crossed(prior.get("mem_available_pct"), row.get("mem_available_pct"), 10):
            return "mem_available_pct", prior.get("mem_available_pct"), row.get("mem_available_pct")
        if crossed(prior.get("fs_root_avail_pct"), row.get("fs_root_avail_pct"), 10):
            return "fs_root_avail_pct", prior.get("fs_root_avail_pct"), row.get("fs_root_avail_pct")
        if row.get("state") != prior.get("state"):
            return "state", prior.get("state"), row.get("state")
    elif kind == "target" and row.get("health") != prior.get("health"):
        return "health", prior.get("health"), row.get("health")
    return None, None, None


def is_worse(row, prior, field, threshold):
    if field == "row":
        return row["kind"] == "probe" and row.get("state") == "down"
    if row["kind"] == "probe" and field == "success" and row.get("success") == 0:
        return True
    if field == "content_ok":
        return row.get("content_ok") == 0
    if row["kind"] == "container" and field in ("state", "started_epoch") and (
        row.get("state") == "gone" or field == "started_epoch"
    ):
        return True
    if row["kind"] == "host" and field in ("boot_epoch", "state", "interfaces_down"):
        if field == "interfaces_down":
            return bool(row.get("interfaces_down")) and iface_text(row.get("interfaces_down")) != iface_text(
                (prior or {}).get("interfaces_down")
            )
        return True
    if row["kind"] == "target" and field == "health" and row.get("health") != "up":
        return True
    if field in ("duration_ms", "latency_ms_window"):
        current = row.get(field)
        previous = (prior or {}).get(field)
        if not isinstance(current, int):
            return False
        if not isinstance(previous, int):
            return current > threshold
        return current > previous
    if field == "cpu_throttled_s":
        return positive(row.get("cpu_throttled_s"))
    if field == "oom_events":
        return isinstance(row.get("oom_events"), int) and row["oom_events"] > 0
    if field == "mem_limit_bytes":
        current = pressure(row)
        previous = pressure(prior or {})
        return current is not None and previous is not None and current > previous
    if field in ("mem_available_pct", "fs_root_avail_pct", "cpu_pct"):
        current = row.get(field)
        previous = (prior or {}).get(field)
        if current is None or previous is None:
            return False
        return current < previous
    return False


def is_better(row, prior, field):
    if prior is None:
        return False
    if row["kind"] == "probe" and field == "success" and prior.get("success") == 0 and row.get("success") == 1:
        return True
    if field == "duration_ms":
        current = row.get("duration_ms")
        previous = prior.get("duration_ms")
        return isinstance(current, int) and isinstance(previous, int) and current < previous
    if field == "latency_ms_window":
        current = row.get("latency_ms_window")
        previous = prior.get("latency_ms_window")
        return isinstance(current, int) and isinstance(previous, int) and current < previous
    if field == "content_ok":
        return prior.get("content_ok") == 0 and row.get("content_ok") == 1
    if field == "cpu_throttled_s":
        return positive(prior.get("cpu_throttled_s")) and not positive(row.get("cpu_throttled_s"))
    if field == "oom_events":
        return isinstance(prior.get("oom_events"), int) and prior["oom_events"] > 0 and row.get("oom_events") == 0
    if row["kind"] == "container" and field == "state" and prior.get("state") == "gone" and row.get("state") == "running":
        return True
    if row["kind"] == "host" and field == "state" and prior.get("state") == "unreachable" and row.get("state") == "up":
        return True
    if row["kind"] == "target" and field == "health" and prior.get("health") != "up" and row.get("health") == "up":
        return True
    return False


def overall_delta(pairs, first, threshold):
    if first:
        return "first"
    if not pairs:
        return "unchanged"
    if any(is_worse(row, prior, field, threshold) for row, prior, field in pairs):
        return "worse"
    if any(is_better(row, prior, field) for row, prior, field in pairs):
        return "better"
    return "changed"


def note_for(row, prior, field, first):
    if first:
        return "Baseline."
    if prior is None:
        return "New row."
    if field == "started_epoch":
        return "Container start time moved."
    if field == "boot_epoch":
        return "Host boot time moved."
    if field == "state":
        return f"{prior.get('state')} -> {row.get('state')}."
    return f"{field} {prior.get(field)} -> {row.get(field)}."


def keep_kind(rows, kind):
    return [row for row in rows if isinstance(row, dict) and row.get("kind") == kind and blank(row.get("scope"))]


def union_keys(rows):
    found = []
    for row in rows:
        for key in row.get("keys") or []:
            if key not in found and KEY_RE.match(key):
                found.append(key)
    return found


VISIT_FIELDS = ("watch_id", "checked_at", "status", "coverage", "delta", "stamp_written", "window")


def fit_visit(row):
    if not isinstance(row, dict):
        return None
    if not blank(row.get("checked_at")) or not blank(row.get("window")):
        return None
    if row.get("status") not in ("ok", "degraded", "unknown"):
        return None
    if row.get("coverage") not in ("complete", "partial", "unavailable"):
        return None
    if row.get("delta") not in ("first", "unchanged", "worse", "better", "changed"):
        return None
    if not isinstance(row.get("stamp_written"), bool):
        return None
    return {field: row.get(field) for field in VISIT_FIELDS}


def ring(items, limit=10):
    return list(items)[-limit:]


def stamp_folder(ws):
    return Path(ws) / "health" / "application"


def prune_stamps(ws):
    folder = stamp_folder(ws)
    if not folder.is_dir():
        return
    stamps = sorted(path for path in folder.glob("*.json") if path.is_file())
    for path in stamps[:-10]:
        path.unlink()


def fresh_stamp_id(ws, moment):
    folder = stamp_folder(ws)
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        name = stamp_name(moment)
        if not (folder / f"{name}.json").exists():
            return name, moment
        moment = moment + timedelta(seconds=1)


def strip_arg(value):
    text = str(value or "").strip()
    return text.strip("'\"")


def locate_stamp(ws, given):
    text = strip_arg(given)
    if text.endswith(".json'"):
        text = text[:-1]
    rel = text[1:] if text.startswith("/") else text
    name = Path(rel).name
    if name.endswith(".json"):
        name = name[:-5]
    name = strip_arg(name)
    candidates = []
    if rel:
        candidates.append(ws / rel)
        if not rel.endswith(".json"):
            candidates.append(ws / f"{rel}.json")
    if name:
        candidates.append(ws / "health" / "application" / f"{name}.json")
    for path in candidates:
        if path.is_file():
            return path
    return candidates[-1] if candidates else ws / "health" / "application" / "missing.json"


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
            print(f"application workspace={resolved}", file=sys.stderr)
            return resolved
    print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
    print("tried " + ", ".join(str(path) for path in seen), file=sys.stderr)
    return None


def plane_block(board):
    nested = board.get("application")
    if isinstance(nested, dict) and (nested.get("current") or nested.get("probe_job") or nested.get("window")):
        return nested
    if any(key in board for key in ("probe_job", "current", "window")):
        return board
    return nested if isinstance(nested, dict) else {}


def empty_lookup():
    return {"services": [], "sites": [], "vantage_points": [], "hosts": []}


def fit_lookup(value):
    base = empty_lookup()
    if not isinstance(value, dict):
        return base
    for key in base:
        base[key] = [item for item in value.get(key) or [] if isinstance(item, str)]
    return base


def lookup_empty(lookup):
    return not any(lookup.get(key) for key in ("services", "sites", "vantage_points", "hosts"))


def change_annotations(items):
    kept = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        tags = [tag for tag in item.get("tags") or [] if isinstance(tag, str)]
        if not any(tag.startswith("change:") for tag in tags):
            continue
        kept.append({"time": item.get("time"), "tags": tags, "text": blank(item.get("text"))})
    return kept[:20]


def label_values(datasource_uid, label):
    args = {"label": label}
    if datasource_uid:
        args["datasource_uid"] = datasource_uid
    body, error = tool_body(f"label-{label}", "grafana_prometheus_labels", args)
    if error or not body:
        return []
    return [item for item in body.get("values") or [] if isinstance(item, str)]


def expected_vantages(app):
    raw = app.get("expected_vantages") if isinstance(app, dict) else None
    if isinstance(raw, list) and all(isinstance(item, str) and item.strip() for item in raw) and raw:
        return [item.strip() for item in raw]
    return list(DEFAULT_VANTAGES)


def next_measurement(row, missing_vantages, containers, hosts):
    if missing_vantages:
        return "same target from " + ",".join(missing_vantages)
    gone = [item for item in containers if item.get("state") == "gone"]
    if gone:
        return f"container {gone[0].get('name')} on {gone[0].get('host') or 'its host'}"
    blocked = [
        item
        for item in hosts
        if item.get("state") == "unreachable" or item.get("interfaces_down")
    ]
    if blocked:
        return "host " + (blocked[0].get("device") or blocked[0].get("host") or "unresolved")
    if row.get("content_ok") is None:
        return "response-body check for this target"
    return "application response from this target"


def finding_lines(probes, containers, hosts, expected):
    groups = {}
    for row in probes:
        key = (row.get("application"), row.get("environment"), row.get("target"))
        groups.setdefault(key, []).append(row)
    lines = []
    for (app_name, environment, target), rows in groups.items():
        seen = {row.get("vantage_site") for row in rows if row.get("vantage_site")}
        missing_v = [name for name in expected if name not in seen]
        related = [item for item in containers if item.get("application") == app_name]
        host_names = {item.get("host") for item in related}
        related_hosts = [item for item in hosts if item.get("host") in host_names or item.get("device") in host_names]
        for row in rows:
            content = row.get("content_ok")
            if content == 1:
                validation = "content ok"
            elif content == 0:
                validation = "content failed"
            else:
                validation = "content not measured"
            fail = row.get("fail_pct_window")
            fail_text = "failure not measured" if fail is None else f"fail {fail}% for {row.get('fail_seconds_window')}s"
            latency = row.get("latency_ms_window")
            latency_text = "window latency not measured" if latency is None else f"window latency {latency}ms"
            text = (
                f"{app_name or 'none'} env {environment or 'none'} target {target or 'none'} "
                f"from {row.get('vantage_site') or 'none'}: {row.get('state')}, "
                f"http {row.get('http_code')}, {validation}, {fail_text}, {latency_text}"
            )
            if missing_v:
                text += "; vantage missing " + ",".join(missing_v)
            if related:
                bits = []
                for item in related:
                    evidence = []
                    if isinstance(item.get("oom_events"), int) and item["oom_events"] > 0:
                        evidence.append(f"oom {item['oom_events']}")
                    if positive(item.get("cpu_throttled_s")):
                        evidence.append(f"throttled {item['cpu_throttled_s']}s")
                    ratio = pressure(item)
                    if ratio is not None:
                        evidence.append(f"mem {int(ratio)}% of limit")
                    absent = ",".join(item.get("missing") or [])
                    if absent:
                        evidence.append("missing " + absent)
                    if not evidence:
                        evidence.append("running, no constraint evidence")
                    bits.append(f"{item.get('name')}@{item.get('host')}: " + ", ".join(evidence))
                text += "; container " + " | ".join(bits)
            else:
                text += "; no container row for this application"
            if row.get("state") == "down" or content == 0:
                text += "; next " + next_measurement(row, missing_v, related, related_hosts)
            lines.append(text)
    return lines


def fit_summary(payload):
    while payload.get("findings"):
        line = json.dumps(payload, separators=(",", ":"), default=str)
        if len(line.encode("utf-8")) <= 1800:
            break
        payload["findings"] = payload["findings"][:-1]
        payload["findings_truncated"] = True
    return payload


def cmd_collect(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    prod = visit_common.load_json(ws, "inventory/prod.json")
    if prod is None:
        print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
        return 1
    exprs = load_exprs()
    if exprs is None:
        return 1
    board = visit_common.load_board(ws, "application") or {}
    app = plane_block(board)
    window = blank(app.get("window")) or "1h"
    datasource = blank(app.get("datasource_uid"))
    by_lower = prod_names(prod)
    prior_rows = [row for row in app.get("current") or [] if isinstance(row, dict)]
    prior_by_scope = {row["scope"]: row for row in prior_rows if blank(row.get("scope"))}
    now = datetime.now(timezone.utc)
    at = checked_at(now)
    budget = visit_common.Budget(240)
    failed = set()

    targets_body, targets_error = tool_body(
        "targets",
        "grafana_prometheus_targets",
        {"datasource_uid": datasource} if datasource else {},
    )
    targets = []
    if targets_error or not targets_body:
        failed.add("T")
    else:
        targets = targets_body.get("targets") or []

    threshold = latency_limit(app)
    vantages = expected_vantages(app)
    probe_job = blank(app.get("probe_job")) or ""
    discovered_job = False
    if not probe_job and "T" not in failed:
        jobs = probe_jobs(targets)
        if len(jobs) == 1:
            probe_job = jobs[0]
            discovered_job = True
        elif len(jobs) > 1:
            print("Need: probe_job\nOptions: " + ", ".join(jobs), file=sys.stderr)
            return 1

    results = {}
    for name in EXPR_ORDER:
        if budget.exhausted():
            failed.add(name)
            continue
        if name.startswith("P") and not probe_job:
            continue
        expr = exprs[name].replace("<probe_job>", probe_job).replace("<window>", window)
        payload, error = prom_series(name, expr, window, datasource)
        if error or payload is None:
            if name in OPTIONAL_EXPR:
                results[name] = {"series": []}
            else:
                failed.add(name)
            continue
        results[name] = payload

    built = []
    if "P1" in results:
        built.extend(probe_rows(results, by_lower, window))
    elif "P1" in failed:
        built.extend(keep_kind(prior_rows, "probe"))
    if "C1" in results:
        built.extend(container_rows(results, by_lower))
    elif "C1" in failed:
        built.extend(keep_kind(prior_rows, "container"))
    if "H1" in results:
        built.extend(host_rows(results, by_lower))
    elif "H1" in failed:
        built.extend(keep_kind(prior_rows, "host"))
    if "T" not in failed:
        built.extend(target_rows(targets, by_lower))
    else:
        built.extend(keep_kind(prior_rows, "target"))

    seen = {row["scope"] for row in built}
    carried = []
    for prior in prior_rows:
        if prior.get("scope") in seen:
            continue
        if prior.get("kind") == "container":
            carried.append(carry(prior, at, "gone"))
        elif prior.get("kind") == "host":
            carried.append(carry(prior, at, "unreachable"))
    if "C1" in failed:
        carried = [row for row in carried if row.get("kind") != "container"]
    if "H1" in failed:
        carried = [row for row in carried if row.get("kind") != "host"]
    for row in built + carried:
        row["at"] = row.get("at") or at
    current_rows = (built + carried)[:96]

    annotations = app.get("annotations") if isinstance(app.get("annotations"), list) else []
    if not budget.exhausted():
        ann_body, ann_error = tool_body("annotations", "grafana_annotations", {"action": "list", "timerange": window})
        if not ann_error and ann_body:
            annotations = change_annotations(ann_body.get("annotations"))

    lookup = fit_lookup(app.get("lookup"))
    if lookup_empty(lookup) and not budget.exhausted():
        lookup = {
            "services": label_values(datasource, "service"),
            "sites": label_values(datasource, "site"),
            "vantage_points": label_values(datasource, "vantage_point"),
            "hosts": label_values(datasource, "host_name"),
        }

    anchors_down = {"P1", "C1", "H1"}.issubset(failed)
    coverage = "unavailable" if anchors_down else ("partial" if failed else "complete")
    restarted = set()
    rebooted = set()
    pairs = []
    for row in current_rows:
        prior = prior_by_scope.get(row["scope"])
        field, _prior, _current = material(row, prior, threshold)
        if field:
            pairs.append((row, prior, field))
            if field == "started_epoch":
                restarted.add(row["scope"])
            if field == "boot_epoch":
                rebooted.add(row["scope"])

    first = not blank(app.get("baseline_visit_id"))
    probes = [row for row in current_rows if row["kind"] == "probe"]
    containers = [row for row in current_rows if row["kind"] == "container"]
    hosts = [row for row in current_rows if row["kind"] == "host"]
    target_list = [row for row in current_rows if row["kind"] == "target"]
    degraded = (
        any(row.get("state") == "down" or row.get("content_ok") == 0 for row in probes)
        or any(isinstance(row.get("duration_ms"), int) and row["duration_ms"] > threshold for row in probes)
        or any(isinstance(row.get("latency_ms_window"), int) and row["latency_ms_window"] > threshold for row in probes)
        or any(isinstance(row.get("oom_events"), int) and row["oom_events"] > 0 for row in containers)
        or any(positive(row.get("cpu_throttled_s")) for row in containers)
        or any((pressure(row) or 0) >= 90 for row in containers)
        or any(row.get("state") == "gone" or row["scope"] in restarted for row in containers)
        or any(
            row.get("state") == "unreachable" or row["scope"] in rebooted or row.get("interfaces_down")
            for row in hosts
        )
        or any(row.get("health") not in (None, "up") for row in target_list)
    )
    status = "unknown" if anchors_down else ("degraded" if degraded else "ok")
    delta = overall_delta(pairs, first, threshold)
    write_stamp = first or bool(pairs) or coverage != "complete"
    reading_rows = list(current_rows) if first else [row for row, _prior, _field in pairs]
    reading_rows = reading_rows[:READINGS_CAP]
    prior_for = {row["scope"]: prior for row, prior, _field in pairs}
    field_for = {row["scope"]: field for row, _prior, field in pairs}
    readings = []
    for row in reading_rows:
        item = dict(row)
        item["note"] = note_for(row, prior_for.get(row["scope"]), field_for.get(row["scope"]), first)
        readings.append(item)
    reading_scopes = {row["scope"] for row in readings}
    unchanged = 0 if first else sum(1 for row in current_rows if row["scope"] not in reading_scopes)
    public_changed = []
    if not first:
        for row, prior, field in pairs:
            if row["scope"] not in reading_scopes:
                continue
            _field, prior_value, current_value = material(row, prior, threshold)
            public_changed.append(
                {
                    "keys": list(row.get("keys") or []),
                    "field": field,
                    "prior": prior_value,
                    "current": current_value,
                    "at": row["at"],
                }
            )
    iface_down = sum(len(row.get("interfaces_down") or []) for row in hosts)
    metric = {
        "at": at,
        "scope": "estate",
        "probes": None if anchors_down else len(probes),
        "probes_down": None if anchors_down else sum(1 for row in probes if row.get("state") == "down"),
        "containers": None if anchors_down else len([row for row in containers if row.get("state") == "running"]),
        "containers_restarted": None if anchors_down else len(restarted),
        "containers_gone": None if anchors_down else sum(1 for row in containers if row.get("state") == "gone"),
        "hosts": None if anchors_down else len([row for row in hosts if row.get("state") == "up"]),
        "hosts_rebooted": None if anchors_down else len(rebooted),
        "interfaces_down": None if anchors_down else iface_down,
        "targets": None if anchors_down else len(target_list),
        "targets_down": None if anchors_down else sum(1 for row in target_list if row.get("health") != "up"),
        "change_annotations": len(annotations),
    }
    prior_watch = blank(app.get("last_visit_id"))
    baseline = blank(app.get("baseline_visit_id"))
    watch = None
    stamp_rel = None
    if write_stamp:
        if anchors_down:
            metric = {key: None if key not in ("at", "scope") else metric[key] for key in metric}
            readings = []
            unchanged = None
            public_changed = []
        watch, moment = fresh_stamp_id(ws, now)
        at = checked_at(moment)
        metric["at"] = at
        headline = "Baseline." if first else f"{len(readings)} rows moved. {unchanged or 0} board rows unchanged."
        stamp = {
            "keys": union_keys(readings) or union_keys(current_rows),
            "schema": "health-application-check/v1",
            "source": "application",
            "watch_id": watch,
            "checked_at": at,
            "ok": None if status == "unknown" else status == "ok",
            "status": status,
            "headline": headline[:500],
            "window": window,
            "coverage": {"state": coverage, "detail": "failed " + ",".join(sorted(failed)) if failed else "T through H4"},
            "metrics": [metric],
            "readings": readings,
            "unchanged": unchanged,
            "baseline_ref": None if first or not baseline else f"health/application/{baseline}.json",
            "vs_prior": {
                "prior_watch_id": None if first else prior_watch,
                "delta": "first" if first else delta,
                "changed": [] if first else public_changed[:READINGS_CAP],
            },
        }
        concerns = []
        for row in current_rows:
            if row["kind"] == "probe" and row.get("state") == "down" and row.get("application"):
                concerns.append({"type": "application", "name": row["application"]})
            if row["kind"] == "container" and (row.get("state") == "gone" or row["scope"] in restarted) and row.get("application"):
                concerns.append({"type": "application", "name": row["application"]})
            if row["kind"] == "host" and row.get("device") and (
                row.get("state") == "unreachable" or row["scope"] in rebooted or row.get("interfaces_down")
            ):
                concerns.append({"type": "device", "name": row["device"]})
        if concerns:
            stamp["concerns"] = concerns[:8]
        try:
            visit_common.validate(stamp, CHECK_SCHEMA)
        except ValueError as exc:
            print(f"stamp schema: {exc}", file=sys.stderr)
            return 1
        stamp_rel = f"health/application/{watch}.json"
        path = Path(ws) / stamp_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        prune_stamps(ws)
        if first:
            baseline = watch

    series = [row for row in app.get("series") or [] if isinstance(row, dict)]
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
    visits = [item for item in (fit_visit(row) for row in app.get("visits") or []) if item]
    visits.append(visit)
    new_board = {
        "keys": union_keys(current_rows),
        "schema": "health-metadata-application/v1",
        "updated_at": at,
        "source_agent": "health-application",
        "application": {
            "probe_job": probe_job or None,
            "window": window,
            "latency_threshold_ms": threshold,
            "expected_vantages": vantages,
            "lookup": lookup,
            "last_visit_id": watch if write_stamp else prior_watch,
            "last_collected_at": at,
            "baseline_visit_id": baseline if baseline else (watch if first and write_stamp else None),
            "current": current_rows if not anchors_down else prior_rows[:96],
            "annotations": annotations[:20],
            "series": ring(series),
            "visits": ring(visits),
        },
    }
    if datasource:
        new_board["application"]["datasource_uid"] = datasource
    raw_prov = board.get("provenance") if isinstance(board.get("provenance"), dict) else {}
    if raw_prov.get("application") == "user":
        new_board["provenance"] = {"application": "user"}
    elif discovered_job or raw_prov.get("application") == "discovered":
        new_board["provenance"] = {"application": "discovered"}
    try:
        visit_common.validate(new_board, BOARD_SCHEMA)
    except ValueError as exc:
        print(f"board schema: {exc}", file=sys.stderr)
        return 1
    try:
        visit_common.save_board(ws, "application", new_board)
    except OSError as exc:
        print(f"board: {exc}", file=sys.stderr)
        return 1

    needs = []
    if write_stamp and not first:
        for row, prior, field in pairs:
            if not is_worse(row, prior, field, threshold) and field not in ("http_code", "cpu_pct"):
                continue
            if not row.get("keys"):
                continue
            _field, prior_value, current_value = material(row, prior, threshold)
            needs.append({"keys": row["keys"], "field": field, "prior": prior_value, "current": current_value})
    down_n = sum(1 for row in probes if row.get("state") == "down")
    print(
        visit_common.summary(
            fit_summary({
                "plane": "application",
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
                "last_visit_id": new_board["application"]["last_visit_id"],
                "last_collected_at": new_board["application"]["last_collected_at"],
                "findings": finding_lines(probes, containers, hosts, vantages),
                "board": (
                    f"{len(probes)} probes ({down_n} down), {len(containers)} containers, "
                    f"{len(hosts)} hosts, {len(target_list)} targets"
                ),
            })
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
    print(visit_common.summary({"plane": "application", "stamp": str(rel), "annotated": True}))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="Application health visit")
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
