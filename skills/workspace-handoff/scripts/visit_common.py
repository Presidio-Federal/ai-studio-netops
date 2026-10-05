#!/usr/bin/env python3
"""Shared helpers for a nurse visit script.

MCP tools are callable only from execute_command with
execution_type mcp_orchestration, via hai_mcp.call_mcp. The outer
envelope is the same for every server. result is server-specific.
unwrap_iosxe is the Health Device probe from 2026-10-03.
unwrap_splunk is the Health Monitor probe from 2026-10-05.
unwrap_grafana uses that same outer envelope and pivots the Grafana
13 frame body seen from /api/ds/query on 2026-10-05.
unwrap_snow stays unimplemented until a pasted probe shows the shape.
"""
import json
import sys
import time
from pathlib import Path


class Budget:
    """Wall clock for one orchestration run. The MCP token lasts 5 minutes."""

    def __init__(self, seconds=240):
        self.deadline = time.monotonic() + seconds

    def left(self):
        return self.deadline - time.monotonic()

    def exhausted(self):
        return self.left() <= 0


def mcp_call(tool, args, retries=1):
    """Call one attached MCP tool. Returns the raw envelope.

    ImportError means this process is not mcp_orchestration. One retry
    when the envelope says success false. Never reads or prints the
    environment.
    """
    try:
        from hai_mcp import call_mcp
    except ImportError:
        print(
            '{"error": "hai_mcp unavailable; run with execution_type mcp_orchestration"}',
            file=sys.stderr,
        )
        sys.exit(1)
    last = None
    for attempt in range(retries + 1):
        last = call_mcp(tool, args)
        if isinstance(last, dict) and last.get("success"):
            return last
        if attempt < retries:
            continue
    return last if isinstance(last, dict) else {"success": False, "error": "empty envelope"}


def unwrap_iosxe(envelope):
    """Return (payload, error) for iosxe_restconf_get.

    result is a 2-item list. result[0] is a JSON string with raw
    newlines, parsed with strict=False. data is the HTTP body, parsed
    the same way. A 200 whose body is HTML is the CML UI, not the
    device. 204 and 404 are returned as errors so the caller can treat
    BGP's empty answer apart from a transport failure. result[1] is
    ignored.
    """
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
    try:
        code = int(inner.get("status_code") or 0)
    except (TypeError, ValueError):
        return None, "status not an int"
    if code in (204, 404):
        return None, f"status {code}"
    if not (200 <= code < 300):
        return None, f"status {code}"
    data = inner.get("data", "")
    if isinstance(data, str) and data.lstrip().startswith("<"):
        return None, "html body (missing/wrong port)"
    if isinstance(data, str) and data.strip() == "":
        return None, "empty body"
    try:
        payload = json.loads(data, strict=False) if isinstance(data, str) else data
    except json.JSONDecodeError:
        return None, "data not json"
    return payload, None


def unwrap_splunk(envelope):
    """Return (payload, error) for splunk_search.

    Probe 2026-10-05. result is a 2-item list. result[0] is a JSON
    string with raw newlines, parsed with strict=False. The object is
    {ok, results, result_count, truncated}. results is a list of row
    objects. result[1] is a connector_references artifact and is
    ignored. truncated true means the search hit its cap.
    """
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
        return None, "splunk ok false"
    if not isinstance(inner.get("results"), list):
        return None, "results not a list"
    return inner, None


def _grafana_frame_rows(frame):
    """Pivot one Grafana data frame into row dicts.

    Grafana 13 /api/ds/query returns columns in schema.fields and
    parallel arrays in data.values. Checked 2026-10-05 against the
    Network Telemetry datasource: F1 columns are source, exporter_name,
    exporter_site, bytes, flows, last_at.
    """
    if not isinstance(frame, dict):
        return []
    fields = (frame.get("schema") or {}).get("fields") or []
    values = (frame.get("data") or {}).get("values") or []
    names = [field.get("name") for field in fields if isinstance(field, dict)]
    if not names or not values:
        return []
    width = min(len(column) for column in values)
    rows = []
    for index in range(width):
        row = {}
        for column, name in enumerate(names):
            if name and column < len(values):
                row[name] = values[column][index]
        rows.append(row)
    return rows


def _grafana_frames(inner):
    frames = []
    errors = []
    if isinstance(inner.get("frames"), list):
        frames.extend(inner["frames"])
    results = inner.get("results")
    if isinstance(results, dict):
        for block in results.values():
            if not isinstance(block, dict):
                continue
            if block.get("error"):
                errors.append(str(block["error"])[:200])
            frames.extend(block.get("frames") or [])
    return frames, errors


def unwrap_grafana(envelope):
    """Return (payload, error) for grafana_query_influx.

    Outer envelope matches the 2026-10-05 Splunk probe: result[0] is a
    JSON string, result[1] is ignored. The inner body is a Grafana
    query result: results.<ref>.frames[] with columnar values, pivoted
    into rows. A series[].rows[] list is still accepted.
    """
    if not isinstance(envelope, dict) or not envelope.get("success"):
        err = None if not isinstance(envelope, dict) else envelope.get("error")
        return None, err or "success false"
    outer = envelope.get("result")
    raw = outer[0] if isinstance(outer, list) and outer else outer
    try:
        inner = json.loads(raw, strict=False) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return None, "result[0] not json"
    if isinstance(inner, list):
        inner = {"series": inner}
    if not isinstance(inner, dict):
        return None, "inner envelope not an object"
    if inner.get("ok") is False:
        return None, "grafana ok false"
    rows = []
    frames, errors = _grafana_frames(inner)
    if errors and not frames:
        return None, errors[0]
    for frame in frames:
        rows.extend(_grafana_frame_rows(frame))
    series = inner.get("series")
    if series is None and isinstance(inner.get("data"), dict):
        series = inner["data"].get("series")
    if isinstance(series, list):
        for item in series:
            if isinstance(item, dict) and isinstance(item.get("rows"), list):
                rows.extend(item["rows"])
            elif isinstance(item, dict) and "source" in item and "frames" not in item:
                rows.append(item)
    if isinstance(inner.get("results"), list) and not rows:
        rows = [item for item in inner["results"] if isinstance(item, dict)]
    if not rows and not frames and not series and not isinstance(inner.get("results"), list):
        keys = ",".join(sorted(inner.keys())[:12])
        return None, f"grafana rows not found ({keys})"
    return {"rows": rows, "truncated": bool(inner.get("truncated"))}, None


def unwrap_snow(envelope):
    raise NotImplementedError("see docs/mcp-index.md Calling tools from a skill script")


def load_json(ws, rel):
    path = Path(ws) / rel
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_board(ws, plane):
    return load_json(ws, f"health/metadata-{plane}.json")


def save_board(ws, plane, board):
    path = Path(ws) / f"health/metadata-{plane}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    return path


def validate(instance, schema_path):
    """Raise ValueError with the first schema errors. jsonschema is preinstalled."""
    import jsonschema

    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        lines = []
        for err in errors[:8]:
            where = "/".join(str(p) for p in err.path) or "(root)"
            lines.append(f"{where}: {err.message}")
        raise ValueError("; ".join(lines))


def summary(payload):
    """One JSON line. The nurse reads the last stdout line, so print this last."""
    line = json.dumps(payload, separators=(",", ":"), default=str)
    if len(line.encode("utf-8")) > 2048:
        payload = dict(payload)
        notes = list(payload.get("needs_note") or [])
        payload["needs_note"] = notes[:8]
        payload["needs_note_truncated"] = True
        line = json.dumps(payload, separators=(",", ":"), default=str)
    return line


def annotate(stamp_path, headline, notes, schema_path):
    """Set headline and reading notes. No MCP. notes maps '+'-joined keys to text."""
    path = Path(stamp_path)
    with path.open(encoding="utf-8") as fh:
        stamp = json.load(fh)
    stamp["headline"] = headline
    unmatched = set(notes)
    for reading in stamp.get("readings") or []:
        key = "+".join(reading.get("keys") or [])
        if key in notes and notes[key]:
            reading["note"] = notes[key]
            unmatched.discard(key)
    if unmatched:
        print("annotate unmatched keys: " + ", ".join(sorted(unmatched)), file=sys.stderr)
    validate(stamp, schema_path)
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return path
