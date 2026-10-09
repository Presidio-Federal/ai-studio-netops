#!/usr/bin/env python3
"""ServiceNow health visit. One command collects, diffs, and writes the board.

collect runs under execution_type mcp_orchestration. annotate runs under
standard and only edits headline and thread notes. The queries and the
material rules are references/query.md and references/metadata.md.

The agent copies the path Studio shows for this file. Do not hardcode it.

  python3 <skill>/scripts/visit_servicenow.py collect --workspace <file_explorer>
  python3 <skill>/scripts/visit_servicenow.py annotate --workspace <file_explorer> \\
      --stamp health/servicenow/<stamp>.json --headline "..." --note "incident:NUMBER=..."
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
CHECK_SCHEMA = SCHEMA_DIR / "health-servicenow-check.schema.json"
BOARD_SCHEMA = SCHEMA_DIR / "health-metadata-servicenow.schema.json"
KEY_RE = re.compile(r"^(device|interface|site|service|test|control|incident|change):[^ ]+$")
CLOSED = {"resolved", "closed", "canceled", "cancelled"}
INCIDENT_FIELDS = (
    "number,short_description,state,active,urgency,priority,opened_at,"
    "sys_updated_on,resolved_at,close_code,close_notes,rfc,cmdb_ci,business_service"
)
CHANGE_FIELDS = (
    "number,short_description,state,active,urgency,priority,opened_at,"
    "sys_updated_on,closed_at,close_code,close_notes,cmdb_ci,type"
)
SLOT_NEEDLES = (
    ("device", "device", None),
    ("interface", "interface", None),
    ("ip", "ip", "description"),
    ("service", "service", None),
)
DIFF_FIELDS = ("state", "urgency", "device", "interface", "ip", "service", "rfc", "issue")
ROW_FIELDS = (
    "scope",
    "type",
    "number",
    "keys",
    "state",
    "active",
    "urgency",
    "priority",
    "opened_at",
    "updated_at",
    "resolved_at",
    "issue",
    "close_code",
    "close_notes",
    "rfc",
    "ci",
    "service",
    "device",
    "interface",
    "ip",
)


def stamp_name(moment):
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


def checked_at(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def since_text(moment):
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def blank(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def strip_arg(value):
    text = str(value or "").strip()
    return text.strip("'\"")


def cell_pair(value):
    """Stored value and display. MCP uses sys_id/display; the Table API uses value/display_value."""
    if isinstance(value, dict):
        if "sys_id" in value or "display" in value:
            return value.get("sys_id"), value.get("display")
        if "value" in value or "display_value" in value:
            return value.get("value"), value.get("display_value")
    return value, value


def text_cell(value):
    stored, display = cell_pair(value)
    chosen = display if display not in (None, "") else stored
    return blank(chosen)


def time_cell(value):
    """Dates take the stored member. It is UTC. Display is the instance user's local time."""
    stored, display = cell_pair(value)
    raw = stored if stored not in (None, "") else display
    text = blank(raw)
    if not text:
        return None
    if len(text) >= 19 and text[10] == " ":
        return text[:10] + "T" + text[11:19] + "Z"
    if text.endswith("Z") and "T" in text:
        return text[:20] if len(text) >= 20 else text
    parsed = text.replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(parsed)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bool_cell(value):
    stored, display = cell_pair(value)
    raw = display if display not in (None, "") else stored
    return str(raw).strip().lower() in ("true", "1", "yes")


def first_sentence(value):
    text = text_cell(value)
    if not text:
        return None
    text = " ".join(text.split())
    for index, char in enumerate(text):
        if char in ".!?" and (index + 1 == len(text) or text[index + 1] == " "):
            return text[: index + 1]
    return text


def parse_moment(value):
    text = blank(value)
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0)


def whole_word(text, term):
    if not text or not term:
        return False
    pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
    return pattern.search(text) is not None


def closed_state(state):
    return (state or "").strip().lower() in CLOSED


def urgency_rank(value):
    match = re.match(r"(\d+)", str(value or "").strip())
    return int(match.group(1)) if match else None


def priority_high(value):
    return bool(re.match(r"^[12]( |$)", str(value or "").strip()))


def snow_query(label, table, query, fields):
    """One retry. A tool-not-found error is not retried."""
    payload, error = None, "no attempt"
    started = time.monotonic()
    for attempt in range(2):
        envelope = visit_common.mcp_call(
            "snow_query_table",
            {"table": table, "query": query, "fields": fields, "limit": 50},
            retries=0,
        )
        payload, error = visit_common.unwrap_snow(envelope)
        if error is None or "not found" in str(error).lower():
            break
    elapsed = time.monotonic() - started
    shown = "ok" if error is None else str(error)[:120]
    print(
        f"snow call={label} elapsed_s={elapsed:.3f} result={shown}",
        file=sys.stderr,
    )
    return payload, error


def entity_columns(fields):
    if not isinstance(fields, dict):
        return []
    columns = []
    for slot in ("device", "interface", "ip", "service"):
        name = blank(fields.get(slot))
        if name and name not in columns:
            columns.append(name)
    return columns


def with_columns(base, columns):
    if not columns:
        return base
    return base + "," + ",".join(columns)


def discover_fields(rows):
    found = {"device": None, "interface": None, "ip": None, "service": None}
    for row in rows:
        if not isinstance(row, dict):
            continue
        element = text_cell(row.get("element"))
        label = text_cell(row.get("column_label"))
        haystacks = [item.lower() for item in (element, label) if item]
        if not element:
            continue
        for slot, needle, blocked in SLOT_NEEDLES:
            if found[slot]:
                continue
            if blocked and any(blocked in item for item in haystacks):
                continue
            if any(needle in item for item in haystacks):
                found[slot] = element
    return found


def scope_terms(prod, marker, match_terms):
    terms = []
    for device in prod.get("devices") or []:
        if not isinstance(device, dict) or device.get("agent_access") is not True:
            continue
        name = blank(device.get("name"))
        if name and name not in terms:
            terms.append(name)
    if marker and marker not in terms:
        terms.append(marker)
    for term in match_terms or []:
        text = blank(term)
        if text and text not in terms and "^" not in text and "=" not in text:
            terms.append(text)
    return [term for term in terms if "^" not in term and "=" not in term]


def scope_query(terms, device_field, since):
    groups = []
    for term in terms:
        parts = [f"short_descriptionLIKE{term}", f"descriptionLIKE{term}"]
        if device_field:
            parts.append(f"{device_field}={term}")
        groups.append("^OR".join(parts))
    scope = "^OR".join(groups)
    return f"active=true^ORsys_updated_on>={since}^{scope}"


def prod_names(prod):
    names = []
    for device in prod.get("devices") or []:
        if isinstance(device, dict) and blank(device.get("name")):
            names.append(device["name"])
    return names


def service_index(registry):
    if not isinstance(registry, dict):
        return []
    rows = []
    for service in registry.get("services") or []:
        if not isinstance(service, dict):
            continue
        name = blank(service.get("name"))
        if not name:
            continue
        aliases = [name]
        for alias in service.get("aliases") or []:
            text = blank(alias)
            if text and text.lower() not in {item.lower() for item in aliases}:
                aliases.append(text)
        rows.append((name, aliases))
    return rows


def resolve_service(row_service, business, issue, services):
    if row_service:
        return row_service
    if business:
        return business
    for name, aliases in services:
        if any(whole_word(issue, alias) for alias in aliases):
            return name
    return None


def registry_spelling(value, services):
    if not value:
        return None
    for name, _aliases in services:
        if name.lower() == value.lower():
            return name
    return None


def device_keys(device, issue, names):
    if device:
        for name in names:
            if name.lower() == device.lower():
                return [f"device:{name}"]
    found = []
    for name in names:
        if whole_word(issue, name):
            key = f"device:{name}"
            if key not in found:
                found.append(key)
    return found


def build_keys(kind, number, device, interface, service, rfc, issue, names, services):
    keys = [f"{kind}:{number}"]
    devices = device_keys(device, issue, names)
    keys.extend(devices)
    if interface and len(devices) == 1:
        device_name = devices[0].split(":", 1)[1]
        keys.append(f"interface:{device_name}/{interface}")
    spelled = registry_spelling(service, services)
    if spelled:
        keys.append(f"service:{spelled}")
    if rfc:
        keys.append(f"change:{rfc}")
    kept = []
    for key in keys:
        if key not in kept and KEY_RE.match(key):
            kept.append(key)
        if len(kept) == 8:
            break
    return kept


def build_row(raw, kind, fields, names, services):
    if not isinstance(raw, dict):
        return None
    number = text_cell(raw.get("number"))
    issue = text_cell(raw.get("short_description"))
    state = text_cell(raw.get("state"))
    opened = time_cell(raw.get("opened_at"))
    updated = time_cell(raw.get("sys_updated_on"))
    if not number or not issue or not state or not opened or not updated:
        return None
    if kind == "incident":
        resolved = time_cell(raw.get("resolved_at"))
        rfc = text_cell(raw.get("rfc"))
        business = text_cell(raw.get("business_service"))
    else:
        resolved = time_cell(raw.get("closed_at"))
        rfc = None
        business = None
    device = text_cell(raw.get(fields.get("device"))) if fields.get("device") else None
    interface = text_cell(raw.get(fields.get("interface"))) if fields.get("interface") else None
    ip = text_cell(raw.get(fields.get("ip"))) if fields.get("ip") else None
    typed_service = text_cell(raw.get(fields.get("service"))) if fields.get("service") else None
    service = resolve_service(typed_service, business, issue, services)
    row = {
        "scope": f"{kind}:{number}",
        "type": kind,
        "number": number,
        "keys": build_keys(kind, number, device, interface, service, rfc, issue, names, services),
        "state": state,
        "active": bool_cell(raw.get("active")),
        "urgency": text_cell(raw.get("urgency")),
        "priority": text_cell(raw.get("priority")),
        "opened_at": opened,
        "updated_at": updated,
        "resolved_at": resolved,
        "issue": issue,
        "close_code": text_cell(raw.get("close_code")),
        "close_notes": first_sentence(raw.get("close_notes")),
        "rfc": rfc,
        "ci": text_cell(raw.get("cmdb_ci")),
        "service": service,
        "device": device,
        "interface": interface,
        "ip": ip,
    }
    return row


def change_item(row, field, prior, current):
    return {
        "keys": list(row.get("keys") or []),
        "field": field,
        "prior": prior,
        "current": current,
        "at": row["updated_at"],
    }


def diff_row(row, prior):
    if prior is None:
        return [change_item(row, "row", None, row["state"])]
    items = []
    for field in DIFF_FIELDS:
        if prior.get(field) != row.get(field):
            items.append(change_item(row, field, prior.get(field), row.get(field)))
    if not items and prior.get("updated_at") != row.get("updated_at"):
        items.append(change_item(row, "updated", prior.get("updated_at"), row.get("updated_at")))
    return items


def is_worse(item, row, prior):
    if item["field"] == "row":
        return bool(row.get("active"))
    if item["field"] == "state" and prior is not None:
        return closed_state(prior.get("state")) and not closed_state(row.get("state"))
    if item["field"] == "urgency" and prior is not None:
        old = urgency_rank(prior.get("urgency"))
        new = urgency_rank(row.get("urgency"))
        return old is not None and new is not None and new < old
    return False


def is_better(item, row, prior):
    return (
        item["field"] == "state"
        and prior is not None
        and not closed_state(prior.get("state"))
        and closed_state(row.get("state"))
    )


def overall_delta(pairs, first):
    if first:
        return "first"
    if not pairs:
        return "unchanged"
    if any(is_worse(item, row, prior) for row, prior, item in pairs):
        return "worse"
    if any(is_better(item, row, prior) for row, prior, item in pairs):
        return "better"
    return "changed"


def days_open(opened, at):
    start = parse_moment(opened)
    end = parse_moment(at)
    if not start or not end:
        return None
    return max(0, int((end - start).total_seconds() // 86400))


def note_for(row, prior, fields, first, at):
    age = days_open(row["opened_at"], at)
    age_text = f"open {age} days" if age is not None else "open"
    attached = []
    if row.get("device"):
        attached.append(f"device {row['device']}")
    else:
        attached.append("no device")
    if row.get("rfc"):
        attached.append(f"change {row['rfc']}")
    else:
        attached.append("no change")
    tail = "; ".join([age_text, *attached])
    if first or prior is None:
        moved = "New" if prior is None and not first else "Baseline"
        return f"{moved}. {tail}."
    if fields == ["updated"]:
        return f"Updated. {tail}."
    shown = ", ".join(fields[:4])
    return f"Moved {shown}. {tail}."


def finding_line(row):
    issue = row["issue"][:60]
    device = row.get("device") or "none"
    rfc = row.get("rfc") or "none"
    urgency = row.get("urgency") or "none"
    return (
        f"{row['number']} {row['state']} ({urgency}): {issue}"
        f" — open since {row['opened_at']}; device {device}; change {rfc}"
    )


def union_keys(rows):
    found = []
    for row in rows:
        for key in row.get("keys") or []:
            if key not in found and KEY_RE.match(key):
                found.append(key)
    return found


def ring(items, limit=10):
    return list(items)[-limit:]


def fit_row(row):
    if not isinstance(row, dict):
        return None
    if row.get("type") not in ("incident", "change"):
        return None
    if not blank(row.get("scope")) or not blank(row.get("number")) or not blank(row.get("issue")):
        return None
    if not blank(row.get("state")) or not blank(row.get("opened_at")) or not blank(row.get("updated_at")):
        return None
    if not isinstance(row.get("active"), bool):
        return None
    keys = [key for key in (row.get("keys") or []) if isinstance(key, str) and KEY_RE.match(key)]
    if not keys:
        return None
    fitted = {field: row.get(field) for field in ROW_FIELDS}
    fitted["keys"] = keys[:8]
    return fitted


def fit_metric(row):
    if not isinstance(row, dict) or row.get("scope") != "lab" or not blank(row.get("at")):
        return None
    fields = ("at", "scope", "rows", "open_incidents", "open_p1p2", "open_changes", "resolved_rows", "typed_rows")
    return {field: row.get(field) for field in fields}


def fit_visit(row):
    if not isinstance(row, dict):
        return None
    if not blank(row.get("checked_at")) or not blank(row.get("since")):
        return None
    if row.get("status") not in ("ok", "unknown"):
        return None
    if row.get("coverage") not in ("complete", "partial", "unavailable"):
        return None
    if row.get("delta") not in ("first", "unchanged", "worse", "better", "changed"):
        return None
    if not isinstance(row.get("stamp_written"), bool):
        return None
    fields = ("watch_id", "checked_at", "status", "coverage", "delta", "stamp_written", "since")
    return {field: row.get(field) for field in fields}


def trim_current(rows):
    rows = list(rows)
    if len(rows) <= 32:
        return rows

    def oldest(row):
        return row.get("updated_at") or ""

    inactive = sorted((row for row in rows if not row.get("active")), key=oldest)
    kept = [row for row in rows if row.get("active")]
    while inactive and len(kept) + len(inactive) > 32:
        inactive.pop(0)
    rows = kept + inactive
    if len(rows) <= 32:
        return rows
    rows.sort(key=oldest)
    return rows[-32:]


def stamp_folder(ws):
    return Path(ws) / "health" / "servicenow"


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
            print(f"servicenow workspace={resolved}", file=sys.stderr)
            return resolved
    print('{"error": "inventory/prod.json missing"}', file=sys.stderr)
    print("tried " + ", ".join(str(path) for path in seen), file=sys.stderr)
    return None


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
        candidates.append(ws / "health" / "servicenow" / f"{name}.json")
    for path in candidates:
        if path.is_file():
            return path
    return candidates[-1] if candidates else ws / "health" / "servicenow" / "missing.json"


def plane_block(board):
    if not isinstance(board, dict):
        return {}
    nested = board.get("servicenow")
    if isinstance(nested, dict):
        return nested
    return {}


def marker_from(prod):
    title = blank(prod.get("lab_title"))
    if title:
        return title
    source = prod.get("source")
    if isinstance(source, dict):
        return blank(source.get("name"))
    return None


def null_metric(at):
    return {
        "at": at,
        "scope": "lab",
        "rows": None,
        "open_incidents": None,
        "open_p1p2": None,
        "open_changes": None,
        "resolved_rows": None,
        "typed_rows": None,
    }


def metric_for(rows, at, changes_known):
    incidents = [row for row in rows if row["type"] == "incident"]
    changes = [row for row in rows if row["type"] == "change"]
    open_incidents = sum(1 for row in incidents if row["active"])
    return {
        "at": at,
        "scope": "lab",
        "rows": len(rows),
        "open_incidents": open_incidents,
        "open_p1p2": sum(1 for row in incidents if row["active"] and priority_high(row.get("priority"))),
        "open_changes": sum(1 for row in changes if row["active"]) if changes_known else None,
        "resolved_rows": sum(1 for row in rows if not row["active"]),
        "typed_rows": sum(1 for row in rows if row.get("device")),
    }


def concerns_for(rows):
    found = []
    for row in rows:
        if row["type"] == "incident" and row["active"] and priority_high(row.get("priority")):
            found.append({"type": "incident", "name": row["number"]})
        if len(found) == 8:
            break
    return found


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def board_shell(snow, at, current, series, visits, collected, visit_id, baseline, provenance):
    return {
        "keys": union_keys(current),
        "schema": "health-metadata-servicenow/v2",
        "updated_at": at,
        "source_agent": "health-servicenow",
        "servicenow": {
            "marker": snow["marker"],
            "match_terms": list(snow.get("match_terms") or []),
            "lookback_days": snow["lookback_days"],
            "entity_fields": snow["entity_fields"],
            "last_visit_id": visit_id,
            "last_collected_at": collected,
            "baseline_visit_id": baseline,
            "current": current,
            "series": ring(series),
            "visits": ring(visits),
        },
        "provenance": provenance,
    }


def save_checked(ws, board, stamp, stamp_rel):
    visit_common.validate(stamp, CHECK_SCHEMA)
    if stamp_rel:
        write_json(Path(ws) / stamp_rel, stamp)
        prune_stamps(ws)
    visit_common.validate(board, BOARD_SCHEMA)
    visit_common.save_board(ws, "servicenow", board)


def prepare_snow(board, prod):
    snow = dict(plane_block(board))
    provenance = dict(board.get("provenance") or {}) if isinstance(board, dict) else {}
    marker = blank(snow.get("marker"))
    if not marker:
        marker = marker_from(prod)
        if marker:
            provenance["servicenow"] = "discovered"
    lookback = snow.get("lookback_days")
    if not isinstance(lookback, int) or not 1 <= lookback <= 365:
        lookback = 30
    match_terms = [blank(term) for term in (snow.get("match_terms") or [])]
    match_terms = [term for term in match_terms if term]
    fields = snow.get("entity_fields") if isinstance(snow.get("entity_fields"), dict) else None
    snow["marker"] = marker
    snow["lookback_days"] = lookback
    snow["match_terms"] = match_terms
    snow["entity_fields"] = fields
    return snow, provenance


def cmd_collect(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    prod = visit_common.load_json(ws, "inventory/prod.json")
    if not isinstance(prod, dict):
        print('{"error": "inventory/prod.json unreadable"}', file=sys.stderr)
        return 1
    board = visit_common.load_board(ws, "servicenow") or {}
    services = visit_common.load_json(ws, "inventory/services.json")
    snow, provenance = prepare_snow(board, prod)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    at = checked_at(now)
    if not snow["marker"]:
        return write_unavailable(ws, board, snow, provenance, at, "prod.json has no lab_title or source.name")

    fields_known = isinstance(snow.get("entity_fields"), dict)
    if not fields_known:
        payload, error = snow_query(
            "dictionary",
            "sys_dictionary",
            "name=incident^elementSTARTSWITHu_",
            "element,column_label,internal_type",
        )
        snow["entity_fields"] = discover_fields((payload or {}).get("rows") or [])
        if provenance.get("entity_fields") != "user":
            provenance["entity_fields"] = "discovered"
        if error:
            print(f"snow dictionary: {error}", file=sys.stderr)

    since_moment = now - timedelta(days=snow["lookback_days"])
    if blank(snow.get("baseline_visit_id")) and parse_moment(snow.get("last_collected_at")):
        since_moment = parse_moment(snow.get("last_collected_at")) - timedelta(days=1)
    since = since_text(since_moment)
    terms = scope_terms(prod, snow["marker"], snow["match_terms"])
    if not terms:
        return write_unavailable(ws, board, snow, provenance, at, "no scope terms")
    device_field = blank((snow.get("entity_fields") or {}).get("device"))
    query = scope_query(terms, device_field, since)
    columns = entity_columns(snow.get("entity_fields") or {})

    incident_payload, incident_error = snow_query("incident", "incident", query, with_columns(INCIDENT_FIELDS, columns))
    if incident_error:
        return write_unavailable(ws, board, snow, provenance, at, f"incident query failed: {incident_error}")

    change_fields = with_columns(CHANGE_FIELDS, columns)
    change_payload, change_error = snow_query("change", "change_request", query, change_fields)
    if change_error and columns:
        change_payload, change_error = snow_query("change", "change_request", query, CHANGE_FIELDS)
    if change_error is None and columns:
        sample = (change_payload or {}).get("rows") or []
        if sample and any(column not in sample[0] for column in columns):
            change_payload, change_error = snow_query("change", "change_request", query, CHANGE_FIELDS)

    incident_raw = list((incident_payload or {}).get("rows") or [])
    changes_known = change_error is None
    change_raw = list((change_payload or {}).get("rows") or []) if changes_known else []
    coverage = "complete"
    detail = "incident + change_request"
    if change_error:
        coverage = "partial"
        detail = f"change_request failed: {str(change_error)[:160]}"
    elif len(incident_raw) >= 50 or len(change_raw) >= 50:
        coverage = "partial"
        detail = "a query returned 50 rows, the cap; no second page"
    built = []
    skipped = 0
    fetched = [("incident", row) for row in incident_raw]
    if changes_known:
        fetched.extend(("change", row) for row in change_raw)
    for kind, raw in fetched:
        row = build_row(raw, kind, snow["entity_fields"], prod_names(prod), service_index(services))
        if row is None:
            skipped += 1
            continue
        built = [kept for kept in built if kept["scope"] != row["scope"]]
        built.append(row)
    if skipped:
        detail = (detail + f"; skipped {skipped} rows missing number, title, or time").strip()

    return finish_collect(
        ws, board, snow, provenance, at, since, built, coverage, detail, changes_known, now
    )


def finish_collect(ws, board, snow, provenance, at, since, built, coverage, detail, changes_known, now):
    prior_rows = [row for row in (plane_block(board).get("current") or []) if fit_row(row)]
    prior_by = {row["scope"]: row for row in prior_rows}
    first = not blank(snow.get("baseline_visit_id"))
    pairs = []
    for row in built:
        prior = prior_by.get(row["scope"])
        for item in diff_row(row, prior):
            pairs.append((row, prior, item))
    public_changed = [item for _row, _prior, item in pairs][:32]
    delta = overall_delta(pairs, first)
    write_stamp = first or bool(public_changed) or coverage != "complete"
    by_scope = {}
    for row, prior, item in pairs:
        by_scope.setdefault(row["scope"], (row, prior, []))[2].append(item["field"])
    threads = []
    if write_stamp:
        chosen = built if first else [row for row, _prior, _fields in by_scope.values()]
        for row in chosen[:32]:
            prior = prior_by.get(row["scope"])
            fields = by_scope.get(row["scope"], (row, prior, []))[2]
            thread = dict(row)
            thread["note"] = note_for(row, prior, fields, first, at)
            threads.append(thread)
    replaced = {thread["scope"] for thread in threads}
    unchanged = 0 if first else sum(1 for row in prior_rows if row["scope"] not in replaced)
    if not write_stamp:
        unchanged = len(prior_rows)
    metric = metric_for(built, at, changes_known)
    status = "ok"
    watch = None
    stamp_rel = None
    if write_stamp:
        watch, moment = fresh_stamp_id(ws, now)
        at = checked_at(moment)
        metric["at"] = at
        for thread in threads:
            thread["note"] = note_for(
                thread,
                prior_by.get(thread["scope"]),
                by_scope.get(thread["scope"], (thread, None, []))[2],
                first,
                at,
            )
        baseline = blank(snow.get("baseline_visit_id"))
        stamp = {
            "keys": union_keys(threads),
            "schema": "health-servicenow-check/v3",
            "source": "servicenow",
            "watch_id": watch,
            "checked_at": at,
            "ok": True,
            "status": status,
            "headline": headline_for(threads, unchanged, first, coverage),
            "window": since,
            "coverage": {"state": coverage, "detail": detail[:300]},
            "metrics": [metric],
            "threads": threads,
            "unchanged": unchanged if not first else 0,
            "baseline_ref": f"health/servicenow/{baseline}.json" if baseline else None,
            "vs_prior": {
                "prior_watch_id": blank(snow.get("last_visit_id")),
                "delta": delta,
                "changed": [] if first else public_changed,
            },
            "concerns": concerns_for(built),
        }
        stamp_rel = f"health/servicenow/{watch}.json"
    current = merge_current(prior_rows, built)
    series = [row for row in (plane_block(board).get("series") or []) if fit_metric(row)]
    series.append(metric)
    visits = [row for row in (plane_block(board).get("visits") or []) if fit_visit(row)]
    visits.append(
        {
            "watch_id": watch,
            "checked_at": at,
            "status": status,
            "coverage": coverage,
            "delta": delta if write_stamp else "unchanged",
            "stamp_written": bool(write_stamp),
            "since": since,
        }
    )
    collected = at
    visit_id = watch if write_stamp else blank(snow.get("last_visit_id"))
    baseline = blank(snow.get("baseline_visit_id")) or (watch if write_stamp else None)
    new_board = board_shell(snow, at, current, series, visits, collected, visit_id, baseline, provenance)
    try:
        if write_stamp:
            save_checked(ws, new_board, stamp, stamp_rel)
        else:
            visit_common.validate(new_board, BOARD_SCHEMA)
            visit_common.save_board(ws, "servicenow", new_board)
    except (ValueError, OSError) as exc:
        print(f"write: {exc}", file=sys.stderr)
        return 1
    needs = []
    if write_stamp:
        for thread in threads[:8]:
            prior = prior_by.get(thread["scope"])
            fields = by_scope.get(thread["scope"], (thread, prior, []))[2]
            needs.append(
                {
                    "keys": thread["keys"],
                    "number": thread["number"],
                    "field": fields[0] if fields else "row",
                    "prior": None if prior is None else prior.get(fields[0]) if fields and fields[0] != "row" else (None if prior is None else prior.get("state")),
                    "current": thread["state"] if not fields or fields[0] in ("row", "state") else thread.get(fields[0]),
                    "opened_at": thread["opened_at"],
                    "device": thread.get("device"),
                    "rfc": thread.get("rfc"),
                }
            )
    open_rows = sum(1 for row in current if row.get("active"))
    print(
        visit_common.summary(
            {
                "plane": "servicenow",
                "watch_id": watch,
                "stamp": stamp_rel,
                "status": status,
                "coverage": coverage,
                "since": since,
                "delta": delta if write_stamp else "unchanged",
                "unchanged": unchanged if not first else 0,
                "needs_note": needs,
                "board_rows": len(current),
                "open": open_rows,
                "last_visit_id": new_board["servicenow"]["last_visit_id"],
                "findings": [finding_line(thread) for thread in threads[:8]],
            }
        )
    )
    return 0


def headline_for(threads, unchanged, first, coverage):
    if first:
        return f"Baseline. {len(threads)} in-scope rows. {unchanged} rows unchanged."
    if not threads:
        return f"Collection {coverage}. No moved rows. {unchanged} rows unchanged."
    numbers = ", ".join(thread["number"] for thread in threads[:4])
    return f"{len(threads)} tickets moved ({numbers}). {unchanged} rows unchanged."


def merge_current(prior_rows, built):
    by_scope = {row["scope"]: row for row in prior_rows}
    for row in built:
        by_scope[row["scope"]] = {field: row[field] for field in ROW_FIELDS}
    return trim_current(list(by_scope.values()))


def write_unavailable(ws, board, snow, provenance, at, reason):
    print(f"servicenow unavailable: {reason}", file=sys.stderr)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if not blank(snow.get("marker")):
        print(visit_common.summary({
            "plane": "servicenow",
            "watch_id": None,
            "stamp": None,
            "status": "unknown",
            "coverage": "unavailable",
            "since": None,
            "delta": "unchanged",
            "unchanged": None,
            "needs_note": [],
            "board_rows": 0,
            "open": 0,
            "last_visit_id": None,
            "findings": [],
            "error": str(reason)[:200],
        }))
        return 0
    if not isinstance(snow.get("entity_fields"), dict):
        snow["entity_fields"] = {"device": None, "interface": None, "ip": None, "service": None}
    if not isinstance(snow.get("lookback_days"), int):
        snow["lookback_days"] = 30
    snow["match_terms"] = list(snow.get("match_terms") or [])
    watch, moment = fresh_stamp_id(ws, now)
    at = checked_at(moment)
    since_moment = now - timedelta(days=snow["lookback_days"])
    if parse_moment(plane_block(board).get("last_collected_at")):
        since_moment = parse_moment(plane_block(board).get("last_collected_at")) - timedelta(days=1)
    since = since_text(since_moment)
    metric = null_metric(at)
    baseline = blank(plane_block(board).get("baseline_visit_id"))
    prior_watch = blank(plane_block(board).get("last_visit_id"))
    stamp = {
        "keys": [],
        "schema": "health-servicenow-check/v3",
        "source": "servicenow",
        "watch_id": watch,
        "checked_at": at,
        "ok": None,
        "status": "unknown",
        "headline": "Incident query failed. No ticket rows this visit.",
        "window": since,
        "coverage": {"state": "unavailable", "detail": str(reason)[:200]},
        "metrics": [metric],
        "threads": [],
        "unchanged": None,
        "baseline_ref": f"health/servicenow/{baseline}.json" if baseline else None,
        "vs_prior": {"prior_watch_id": prior_watch, "delta": "unchanged", "changed": []},
    }
    prior_rows = [row for row in (plane_block(board).get("current") or []) if fit_row(row)]
    series = [row for row in (plane_block(board).get("series") or []) if fit_metric(row)]
    series.append(metric)
    visits = [row for row in (plane_block(board).get("visits") or []) if fit_visit(row)]
    visits.append(
        {
            "watch_id": watch,
            "checked_at": at,
            "status": "unknown",
            "coverage": "unavailable",
            "delta": "unchanged",
            "stamp_written": True,
            "since": since,
        }
    )
    new_board = board_shell(
        snow,
        at,
        prior_rows[:32],
        series,
        visits,
        plane_block(board).get("last_collected_at") if isinstance(plane_block(board).get("last_collected_at"), str) else None,
        watch,
        baseline,
        provenance,
    )
    stamp_rel = f"health/servicenow/{watch}.json"
    try:
        save_checked(ws, new_board, stamp, stamp_rel)
    except (ValueError, OSError) as exc:
        print(f"write: {exc}", file=sys.stderr)
        return 1
    print(
        visit_common.summary(
            {
                "plane": "servicenow",
                "watch_id": watch,
                "stamp": stamp_rel,
                "status": "unknown",
                "coverage": "unavailable",
                "since": since,
                "delta": "unchanged",
                "unchanged": None,
                "needs_note": [],
                "board_rows": len(prior_rows),
                "open": sum(1 for row in prior_rows if row.get("active")),
                "last_visit_id": watch,
                "findings": [],
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
    print(visit_common.summary({"plane": "servicenow", "stamp": str(rel), "annotated": True}))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="ServiceNow health visit")
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
