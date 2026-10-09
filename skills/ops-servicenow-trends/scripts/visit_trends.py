#!/usr/bin/env python3
"""ServiceNow trend visit. One command collects, clusters, and writes the stamp.

collect runs under execution_type mcp_orchestration. annotate runs under
standard and edits the headline, theme wording, and why. It does not call
ServiceNow.

A cluster is the same category plus the same normalized short_description,
and only when the count is at least min_related_cases. fix_consistent is
true only when at least two close notes share one first sentence.
recommend is kb only in that case. Empty scope returns options unless
--schedule is set.

The agent copies the path Studio shows for this file. Do not hardcode it.

  python3 <skill>/scripts/visit_trends.py collect --workspace <file_explorer>
  python3 <skill>/scripts/visit_trends.py collect --workspace <file_explorer> --schedule
  python3 <skill>/scripts/visit_trends.py annotate --workspace <file_explorer> \\
      --stamp servicenow/trends/<stamp>.json --headline "..." \\
      --why "incident:NUMBER=<one sentence>" --theme "incident:NUMBER=<short theme>"
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
CHECK_SCHEMA = SCHEMA_DIR / "servicenow-trend.schema.json"
META_SCHEMA = SCHEMA_DIR / "servicenow-metadata-trends.schema.json"
KEY_RE = re.compile(r"^(device|interface|site|service|test|control|incident|change):[^ ]+$")
INCIDENT_FIELDS = (
    "number,short_description,state,active,category,assignment_group,"
    "assigned_to,opened_at,sys_updated_on,close_notes,cmdb_ci"
)
DISCOVERY_FIELDS = "number,short_description,category,assignment_group,active"
CALL_BUDGET = 12
RECOMMEND = {"kb", "restaff", "problem", "watch", "none"}


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


def escape_term(value):
    return str(value).replace("\\", "\\\\").replace("^", "\\^").replace("=", "\\=")


def cell_pair(value):
    if isinstance(value, dict):
        if "sys_id" in value or "display" in value:
            return value.get("sys_id"), value.get("display")
        if "value" in value or "display_value" in value:
            return value.get("value"), value.get("display_value")
    return value, value


def text_cell(value):
    stored, display = cell_pair(value)
    chosen = display if display not in (None, "") else stored
    if isinstance(chosen, dict):
        return text_cell(chosen)
    return blank(chosen)


def bool_cell(value):
    raw = text_cell(value)
    return str(raw or "").strip().lower() in ("true", "1", "yes")


def first_sentence(value):
    text = text_cell(value)
    if not text:
        return None
    text = " ".join(text.split())
    for index, char in enumerate(text):
        if char in ".!?" and (index + 1 == len(text) or text[index + 1] == " "):
            return text[: index + 1]
    return text


def norm_title(text):
    lowered = (text or "").lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())


def whole_word(text, term):
    if not text or not term:
        return False
    pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
    return pattern.search(text) is not None


def unwrap_tool(envelope):
    """Outer hai_mcp envelope, then the tool body {ok, ...}."""
    if not isinstance(envelope, dict) or not envelope.get("success"):
        err = None if not isinstance(envelope, dict) else envelope.get("error")
        return None, err or "success false"
    outer = envelope.get("result")
    raw = outer[0] if isinstance(outer, list) and outer else outer
    try:
        inner = json.loads(raw, strict=False) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return None, "result[0] not json"
    if not isinstance(inner, dict):
        return None, "inner envelope not an object"
    if inner.get("ok") is False:
        return None, str(inner.get("error") or "snow ok false")[:200]
    return inner, None


class Caller:
    def __init__(self):
        self.used = 0

    def call(self, label, tool, args):
        if self.used >= CALL_BUDGET:
            print(f"snow budget label={label}", file=sys.stderr)
            return None, "call budget"
        payload, error = None, "no attempt"
        started = time.monotonic()
        for _attempt in range(2):
            if self.used >= CALL_BUDGET:
                error = "call budget"
                break
            self.used += 1
            envelope = visit_common.mcp_call(tool, args, retries=0)
            if tool == "snow_query_table":
                payload, error = visit_common.unwrap_snow(envelope)
            else:
                payload, error = unwrap_tool(envelope)
            if error is None or "not found" in str(error).lower() or error == "call budget":
                break
        elapsed = time.monotonic() - started
        shown = "ok" if error is None else str(error)[:120]
        print(f"snow call={label} elapsed_s={elapsed:.3f} result={shown}", file=sys.stderr)
        return payload, error


def query_table(caller, label, table, query, fields):
    return caller.call(
        label,
        "snow_query_table",
        {"table": table, "query": query, "fields": fields, "limit": 50},
    )


def incident_row(raw):
    if not isinstance(raw, dict):
        return None
    number = text_cell(raw.get("number"))
    title = text_cell(raw.get("short_description"))
    if not number or not title:
        return None
    return {
        "number": number,
        "title": title,
        "norm": norm_title(title),
        "category": text_cell(raw.get("category")),
        "group": text_cell(raw.get("assignment_group")),
        "assignee": text_cell(raw.get("assigned_to")),
        "active": bool_cell(raw.get("active")),
        "close_notes": first_sentence(raw.get("close_notes")),
        "ci": text_cell(raw.get("cmdb_ci")),
    }


def scope_ready(snow):
    return bool(
        blank(snow.get("marker"))
        or list(snow.get("match_terms") or [])
        or list(snow.get("assignment_groups") or [])
        or list(snow.get("categories") or [])
    )


def or_join(parts):
    return "^OR".join(part for part in parts if part)


def term_group(terms):
    parts = []
    for term in terms:
        escaped = escape_term(term)
        parts.append(f"short_descriptionLIKE{escaped}^ORdescriptionLIKE{escaped}")
    return or_join(parts)


def scope_query(snow, since):
    window = f"active=true^ORsys_updated_on>={since}^ORopened_at>={since}"
    groups = [window]
    terms = []
    marker = blank(snow.get("marker"))
    if marker:
        terms.append(marker)
    for term in snow.get("match_terms") or []:
        text = blank(term)
        if text and text not in terms:
            terms.append(text)
    if terms:
        groups.append(term_group(terms))
    categories = [blank(item) for item in (snow.get("categories") or [])]
    categories = [item for item in categories if item]
    if categories:
        groups.append(or_join(f"categoryLIKE{escape_term(item)}" for item in categories))
    groups_named = [blank(item) for item in (snow.get("assignment_groups") or [])]
    groups_named = [item for item in groups_named if item]
    if groups_named:
        groups.append(
            or_join(f"assignment_group.nameLIKE{escape_term(item)}" for item in groups_named)
        )
    return "^".join(groups)


def prod_names(prod):
    if not isinstance(prod, dict):
        return []
    names = []
    for device in prod.get("devices") or []:
        if isinstance(device, dict) and blank(device.get("name")):
            names.append(device["name"])
    return names


def devices_for(rows, names):
    found = []
    for row in rows:
        for name in names:
            key = name
            if row.get("ci") and row["ci"].lower() == name.lower():
                key = name
            elif whole_word(row.get("title"), name):
                key = name
            else:
                continue
            if key not in found:
                found.append(key)
    return found[:8]


def cluster_rows(rows, minimum):
    grouped = {}
    for row in rows:
        if not row["norm"]:
            continue
        key = (row.get("category") or "", row["norm"])
        grouped.setdefault(key, []).append(row)
    clusters = [batch for batch in grouped.values() if len(batch) >= minimum]
    clusters.sort(key=len, reverse=True)
    return clusters[:10]


def fix_consistent(rows):
    notes = []
    for row in rows:
        note = row.get("close_notes")
        if note:
            notes.append(note.lower())
    if len(notes) < 2:
        return None
    return len(set(notes)) == 1


def recommend_for(consistent, devices, open_rows):
    if consistent is True:
        return "kb"
    if devices:
        return "problem"
    if open_rows:
        return "restaff"
    return "watch"


def theme_for(rows):
    titles = [row["title"] for row in rows if row.get("title")]
    titles.sort(key=len)
    theme = titles[0] if titles else "repeating tickets"
    return theme[:80]


def why_for(rows, consistent, recommend):
    note = "resolutions match" if consistent is True else "resolutions differ or are missing"
    return (
        f"Same title class, {len(rows)} tickets, {note}. "
        f"Recommend {recommend}."
    )


def knowledge_for(caller, theme):
    words = norm_title(theme).split()[:4]
    search = " ".join(words)
    if not search:
        return None, None, "empty theme"
    payload, error = caller.call(
        "knowledge",
        "snow_find_knowledge",
        {"search": search, "active_only": True, "limit": 5},
    )
    if error:
        return None, None, error
    articles = (payload or {}).get("articles") or []
    if not articles:
        return False, None, None
    number = text_cell((articles[0] or {}).get("number")) if isinstance(articles[0], dict) else None
    return True, number, None


def build_cluster(rows, names, kb_exists, kb_number):
    consistent = fix_consistent(rows)
    devices = devices_for(rows, names)
    open_rows = [row for row in rows if row["active"]][:8]
    recommend = recommend_for(consistent, devices, open_rows)
    examples = []
    for row in rows:
        if row["number"] not in examples:
            examples.append(row["number"])
        if len(examples) == 5:
            break
    return {
        "theme": theme_for(rows),
        "count": len(rows),
        "example_numbers": examples,
        "open_consuming": [
            {"number": row["number"], "assignee": row.get("assignee")} for row in open_rows
        ],
        "fix_consistent": consistent,
        "kb_exists": kb_exists,
        "kb_number": kb_number,
        "devices": devices,
        "recommend": recommend,
        "why": why_for(rows, consistent, recommend),
        "_rows": rows,
    }


def union_keys(clusters):
    found = []
    for cluster in clusters:
        for number in list(cluster.get("example_numbers") or []) + [
            item.get("number") for item in (cluster.get("open_consuming") or []) if isinstance(item, dict)
        ]:
            key = f"incident:{number}" if number else None
            if key and key not in found and KEY_RE.match(key):
                found.append(key)
        for name in cluster.get("devices") or []:
            key = f"device:{name}"
            if key not in found and KEY_RE.match(key):
                found.append(key)
    return found


def public_cluster(cluster):
    item = dict(cluster)
    item.pop("_rows", None)
    return item


def stamp_folder(ws):
    return Path(ws) / "servicenow" / "trends"


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
        if resolved.is_dir():
            print(f"trends workspace={resolved}", file=sys.stderr)
            return resolved
    print('{"error": "workspace directory missing"}', file=sys.stderr)
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
        candidates.append(ws / "servicenow" / "trends" / f"{name}.json")
    for path in candidates:
        if path.is_file():
            return path
    return candidates[-1] if candidates else ws / "servicenow" / "trends" / "missing.json"


def load_snow(ws):
    board = visit_common.load_json(ws, "servicenow/metadata-trends.json") or {}
    snow = board.get("servicenow") if isinstance(board.get("servicenow"), dict) else {}
    lookback = snow.get("lookback_days")
    if not isinstance(lookback, int) or not 1 <= lookback <= 90:
        lookback = 14
    minimum = snow.get("min_related_cases")
    if not isinstance(minimum, int) or not 2 <= minimum <= 20:
        minimum = 3
    cleaned = {
        "marker": blank(snow.get("marker")),
        "match_terms": [blank(item) for item in (snow.get("match_terms") or []) if blank(item)],
        "assignment_groups": [blank(item) for item in (snow.get("assignment_groups") or []) if blank(item)],
        "categories": [blank(item) for item in (snow.get("categories") or []) if blank(item)],
        "lookback_days": lookback,
        "min_related_cases": minimum,
        "last_visit_id": blank(snow.get("last_visit_id")),
        "last_collected_at": snow.get("last_collected_at") if isinstance(snow.get("last_collected_at"), str) else None,
    }
    provenance = board.get("provenance") if isinstance(board.get("provenance"), dict) else {}
    return board, cleaned, provenance


def write_metadata(ws, snow, provenance, at, prod_present, advance, watch):
    body = {
        "schema": "servicenow-metadata-trends/v1",
        "keys": [],
        "updated_at": at,
        "source_agent": "ops-servicenow-trends",
        "servicenow": {
            "marker": snow.get("marker"),
            "match_terms": list(snow.get("match_terms") or []),
            "assignment_groups": list(snow.get("assignment_groups") or []),
            "categories": list(snow.get("categories") or []),
            "lookback_days": snow["lookback_days"],
            "min_related_cases": snow["min_related_cases"],
            "last_visit_id": watch if advance else snow.get("last_visit_id"),
            "last_collected_at": at if advance else snow.get("last_collected_at"),
        },
    }
    if prod_present:
        body["inventory_ref"] = "inventory/prod.json"
    if provenance:
        body["provenance"] = {"servicenow": provenance.get("servicenow")} if provenance.get("servicenow") in ("user", "discovered") else {}
        if not body["provenance"]:
            body.pop("provenance")
    visit_common.validate(body, META_SCHEMA)
    path = Path(ws) / "servicenow" / "metadata-trends.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def prior_themes(ws, visit_id):
    if not visit_id:
        return []
    payload = visit_common.load_json(ws, f"servicenow/trends/{visit_id}.json")
    if not isinstance(payload, dict):
        return []
    themes = []
    for cluster in payload.get("clusters") or []:
        if isinstance(cluster, dict) and blank(cluster.get("theme")):
            themes.append({"theme": cluster["theme"][:80], "count": cluster.get("count"), "recommend": cluster.get("recommend")})
    return themes[:8]


def discovery_options(rows, groups):
    titles = {}
    categories = {}
    for row in rows:
        if row["norm"]:
            bucket = titles.setdefault(row["norm"], {"count": 0, "sample": row["title"], "category": row.get("category")})
            bucket["count"] += 1
            if not bucket.get("category") and row.get("category"):
                bucket["category"] = row["category"]
        if row.get("category"):
            categories[row["category"]] = categories.get(row["category"], 0) + 1
    options = []
    ranked = sorted(titles.items(), key=lambda item: item[1]["count"], reverse=True)
    for title, bucket in ranked:
        if bucket["count"] >= 2:
            options.append(f"title:{title} x{bucket['count']}")
        if len(options) == 5:
            break
    for name, count in sorted(categories.items(), key=lambda item: item[1], reverse=True)[:3]:
        options.append(f"category:{name} x{count}")
    for name in groups[:3]:
        options.append(f"group:{name}")
    return options[:8], titles, categories


def pick_slice(titles, categories):
    repeating = [bucket for bucket in titles.values() if bucket["count"] >= 2]
    if repeating:
        bucket = max(repeating, key=lambda item: item["count"])
        words = bucket["sample"].split()[:4]
        phrase = " ".join(words).strip(" -—")
        if phrase:
            return {"match_terms": [phrase[:80]]}
    if categories:
        name, _count = max(categories.items(), key=lambda item: item[1])
        return {"categories": [name]}
    return None


def emit(payload):
    print(visit_common.summary(payload))


def cmd_collect(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    _board, snow, provenance = load_snow(ws)
    prod = visit_common.load_json(ws, "inventory/prod.json")
    names = prod_names(prod)
    caller = Caller()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if not scope_ready(snow):
        payload, error = query_table(
            caller, "discover", "incident", "active=true^ORDERBYDESCsys_updated_on", DISCOVERY_FIELDS
        )
        if error:
            return write_unavailable(ws, snow, provenance, now, prod, f"discovery failed: {error}")
        rows = [incident_row(raw) for raw in (payload or {}).get("rows") or []]
        rows = [row for row in rows if row]
        group_payload, group_error = query_table(
            caller, "groups", "sys_user_group", "active=true^ORDERBYname", "name"
        )
        groups = []
        if group_error is None:
            for raw in (group_payload or {}).get("rows") or []:
                name = text_cell(raw.get("name")) if isinstance(raw, dict) else None
                if name and name not in groups:
                    groups.append(name)
        options, titles, categories = discovery_options(rows, groups)
        if not args.schedule:
            emit({
                "plane": "trends",
                "needs_scope": True,
                "options": options,
                "status": "unknown",
                "coverage": "unavailable",
                "stamp": None,
                "clusters": 0,
                "needs_note": [],
                "findings": [],
            })
            return 0
        chosen = pick_slice(titles, categories)
        if not chosen:
            return write_unavailable(ws, snow, provenance, now, prod, "no repeating class to discover")
        snow.update(chosen)
        provenance = dict(provenance)
        provenance["servicenow"] = "discovered"
        write_metadata(ws, snow, provenance, checked_at(now), isinstance(prod, dict), False, None)
    return collect_scoped(ws, snow, provenance, names, prod, caller, now)


def collect_scoped(ws, snow, provenance, names, prod, caller, now):
    since = since_text(now - timedelta(days=snow["lookback_days"]))
    payload, error = query_table(caller, "incident", "incident", scope_query(snow, since), INCIDENT_FIELDS)
    if error:
        return write_unavailable(ws, snow, provenance, now, prod, f"incident query failed: {error}")
    raw_rows = (payload or {}).get("rows") or []
    rows = [incident_row(raw) for raw in raw_rows]
    skipped = sum(1 for row in rows if row is None)
    rows = [row for row in rows if row]
    coverage = "complete"
    detail = f"{len(rows)} in-scope incidents"
    if len(raw_rows) >= 50:
        coverage = "partial"
        detail = "incident query returned 50 rows, the cap"
    if skipped:
        detail = (detail + f"; skipped {skipped} rows with no title")[:300]
    batches = cluster_rows(rows, snow["min_related_cases"])
    clusters = []
    kb_failed = False
    for batch in batches:
        if caller.used >= CALL_BUDGET:
            kb_exists, kb_number = None, None
            kb_failed = True
        else:
            kb_exists, kb_number, kb_error = knowledge_for(caller, theme_for(batch))
            if kb_error:
                kb_failed = True
        clusters.append(build_cluster(batch, names, kb_exists, kb_number))
    if kb_failed and coverage == "complete":
        coverage = "partial"
        detail = (detail + "; a knowledge find failed or the call budget was spent")[:300]
    return write_success(ws, snow, provenance, prod, now, since, rows, clusters, coverage, detail)


def write_success(ws, snow, provenance, prod, now, since, rows, clusters, coverage, detail):
    watch, moment = fresh_stamp_id(ws, now)
    at = checked_at(moment)
    open_count = sum(1 for row in rows if row["active"])
    prior = snow.get("last_visit_id")
    headline = (
        f"{len(clusters)} repeating classes from {len(rows)} in-scope incidents."
        if clusters
        else f"No class reached {snow['min_related_cases']} related cases."
    )
    public = [public_cluster(cluster) for cluster in clusters]
    stamp = {
        "schema": "servicenow-trend/v1",
        "keys": union_keys(public),
        "source": "servicenow-trends",
        "watch_id": watch,
        "checked_at": at,
        "ok": True,
        "status": "ok",
        "headline": headline,
        "prior_observation": f"servicenow/trends/{prior}.json" if prior else None,
        "scope_ref": "servicenow/metadata-trends.json",
        "coverage": {"state": coverage, "detail": detail[:300]},
        "metrics": [{
            "at": at,
            "in_scope": len(rows),
            "in_scope_open": open_count,
            "out_of_scope_open": None,
            "lookback_days": snow["lookback_days"],
            "clusters": len(public),
        }],
        "clusters": public,
    }
    try:
        visit_common.validate(stamp, CHECK_SCHEMA)
        path = Path(ws) / "servicenow" / "trends" / f"{watch}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        prune_stamps(ws)
        write_metadata(ws, snow, provenance, at, isinstance(prod, dict), True, watch)
    except (ValueError, OSError) as exc:
        print(f"write: {exc}", file=sys.stderr)
        return 1
    needs = []
    findings = []
    for cluster in public[:8]:
        example = (cluster.get("example_numbers") or [None])[0]
        needs.append({
            "example": example,
            "theme": cluster["theme"],
            "count": cluster["count"],
            "fix_consistent": cluster["fix_consistent"],
            "open": len(cluster.get("open_consuming") or []),
            "devices": cluster.get("devices") or [],
            "recommend": cluster["recommend"],
            "locked": cluster["recommend"] == "kb",
        })
        findings.append(f"{cluster['theme']} x{cluster['count']}: {cluster['recommend']}")
    emit({
        "plane": "trends",
        "needs_scope": False,
        "watch_id": watch,
        "stamp": f"servicenow/trends/{watch}.json",
        "status": "ok",
        "coverage": coverage,
        "since": since,
        "clusters": len(public),
        "in_scope": len(rows),
        "needs_note": needs,
        "findings": findings,
        "prior_themes": prior_themes(ws, prior),
        "last_visit_id": watch,
    })
    return 0


def write_unavailable(ws, snow, provenance, now, prod, reason):
    print(f"trends unavailable: {reason}", file=sys.stderr)
    watch, moment = fresh_stamp_id(ws, now)
    at = checked_at(moment)
    prior = snow.get("last_visit_id")
    stamp = {
        "schema": "servicenow-trend/v1",
        "keys": [],
        "source": "servicenow-trends",
        "watch_id": watch,
        "checked_at": at,
        "ok": None,
        "status": "unknown",
        "headline": "Trend collection failed. No clusters this visit.",
        "prior_observation": f"servicenow/trends/{prior}.json" if prior else None,
        "scope_ref": "servicenow/metadata-trends.json",
        "coverage": {"state": "unavailable", "detail": str(reason)[:200]},
        "metrics": [{
            "at": at,
            "in_scope": None,
            "in_scope_open": None,
            "out_of_scope_open": None,
            "lookback_days": snow.get("lookback_days"),
            "clusters": None,
        }],
        "clusters": [],
    }
    try:
        visit_common.validate(stamp, CHECK_SCHEMA)
        path = Path(ws) / "servicenow" / "trends" / f"{watch}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        prune_stamps(ws)
    except (ValueError, OSError) as exc:
        print(f"write: {exc}", file=sys.stderr)
        return 1
    emit({
        "plane": "trends",
        "needs_scope": False,
        "watch_id": watch,
        "stamp": f"servicenow/trends/{watch}.json",
        "status": "unknown",
        "coverage": "unavailable",
        "clusters": 0,
        "needs_note": [],
        "findings": [],
        "last_visit_id": prior,
    })
    return 0


def cluster_for_example(clusters, token):
    number = token.split(":", 1)[1] if token.startswith("incident:") else token
    for cluster in clusters:
        numbers = cluster.get("example_numbers") or []
        if number in numbers:
            return cluster
    return None


def cmd_annotate(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    stamp_path = locate_stamp(ws, args.stamp)
    if not stamp_path.is_file():
        print(f"stamp not found: {args.stamp}", file=sys.stderr)
        return 1
    with stamp_path.open(encoding="utf-8") as fh:
        stamp = json.load(fh)
    stamp["headline"] = strip_arg(args.headline)
    unmatched = []

    def apply(flag, field):
        for item in flag or []:
            item = strip_arg(item)
            if "=" not in item:
                unmatched.append(item)
                continue
            token, text = item.split("=", 1)
            token = strip_arg(token).rstrip(">")
            if token.startswith("incident:"):
                token = token.split(":", 1)[1]
            cluster = cluster_for_example(stamp.get("clusters") or [], token)
            if cluster is None:
                unmatched.append(token)
                continue
            if field == "recommend":
                choice = strip_arg(text)
                if cluster.get("recommend") == "kb":
                    print(f"recommend locked kb for {token}", file=sys.stderr)
                    continue
                if choice not in RECOMMEND or choice == "kb":
                    print(f"recommend rejected {choice}", file=sys.stderr)
                    continue
                cluster["recommend"] = choice
            else:
                written = strip_arg(text)
                if written:
                    cluster[field] = written[:240] if field == "theme" else written

    apply(args.why, "why")
    apply(args.theme, "theme")
    apply(args.recommend, "recommend")
    if unmatched:
        print("annotate unmatched: " + ", ".join(unmatched), file=sys.stderr)
    stamp["keys"] = union_keys(stamp.get("clusters") or [])
    try:
        visit_common.validate(stamp, CHECK_SCHEMA)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    stamp_path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    rel = stamp_path.relative_to(ws) if stamp_path.is_relative_to(ws) else stamp_path
    emit({"plane": "trends", "stamp": str(rel), "annotated": True})
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="ServiceNow trend visit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--workspace", required=True)
    collect.add_argument("--schedule", action="store_true")
    collect.set_defaults(func=cmd_collect)
    note = sub.add_parser("annotate")
    note.add_argument("--workspace", required=True)
    note.add_argument("--stamp", required=True)
    note.add_argument("--headline", required=True)
    note.add_argument("--why", action="append", default=[])
    note.add_argument("--theme", action="append", default=[])
    note.add_argument("--recommend", action="append", default=[])
    note.set_defaults(func=cmd_annotate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
