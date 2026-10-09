#!/usr/bin/env python3
"""Shared helpers for a nurse visit script.

MCP tools are callable only from execute_command with
execution_type mcp_orchestration, via hai_mcp.call_mcp. The outer
envelope is the same for every server. result is server-specific.
unwrap_iosxe is the Health Device probe from 2026-10-03.
unwrap_splunk is the Health Monitor probe from 2026-10-05.
unwrap_grafana uses that same outer envelope and pivots the Grafana
13 frame body seen from /api/ds/query on 2026-10-05.
unwrap_snow parses snow_query_table: {ok, rows}. Cells are the
query_table_tool shape, checked against the Table API on 2026-10-09.
unwrap_github reads github_list_files, github_get_file, and
github_put_file. The tool dicts are from github-mcp server.py on
2026-10-09. The outer list wrap is the one the Actions scripts use.
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

    ImportError means this process is not mcp_orchestration. A raise
    from call_mcp is a failed envelope, not a traceback. Tool-not-found
    is not retried. One retry when the envelope says success false.
    Never reads or prints the environment.
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
        try:
            last = call_mcp(tool, args)
        except Exception as exc:
            text = str(exc).split("Available tools:")[0].strip()
            last = {"success": False, "error": text[:200] or "call_mcp raised"}
            if "not found" in text.lower():
                return last
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
    """Return (payload, error) for snow_query_table.

    Outer envelope matches the 2026-10-05 probes: result[0] is a JSON
    string, result[1] is ignored. The tool body is {ok, rows, error}.
    rows are already serialized by query_table_tool: a cell is a string,
    or {sys_id, display} when the stored value and the display differ.
    Checked 2026-10-09 against the Table API with display_value=all:
    dates differ (value is UTC), choice fields differ (display is the
    label), and equal cells stay plain strings. An unknown field name
    is omitted and the GET still returns 200.
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
        return None, str(inner.get("error") or "snow ok false")[:200]
    rows = inner.get("rows")
    if rows is None and isinstance(inner.get("result"), list):
        rows = inner["result"]
    if not isinstance(rows, list):
        return None, "rows not a list"
    return {"rows": rows, "returned": len(rows)}, None


def _github_tool_dict(envelope):
    """Return the GitHub tool dict inside a hai_mcp envelope.

    call_mcp returns {success, result}. result is a list. result[0] is
    the tool dict or a JSON string of it. result[1] is an artifact and
    is ignored. A bare tool dict is accepted so a caller can pass either
    shape. The tool dict uses ok, not success.
    """
    if not isinstance(envelope, dict):
        return None, "envelope not an object"
    if "ok" in envelope and "success" not in envelope:
        return envelope, None
    if not envelope.get("success"):
        err = envelope.get("error")
        return None, str(err or "success false")[:200]
    outer = envelope.get("result")
    raw = outer[0] if isinstance(outer, list) and outer else outer
    if raw is None:
        return None, "empty result"
    if isinstance(raw, str):
        try:
            raw = json.loads(raw, strict=False)
        except json.JSONDecodeError:
            return None, "result[0] not json"
    if not isinstance(raw, dict):
        return None, "inner envelope not an object"
    return raw, None


def unwrap_github(envelope):
    """Return (payload, error) for the GitHub file tools.

    Tool bodies read 2026-10-09 from github-mcp server.py and
    tools/github_list_files_tool.py, github_get_file_tool.py,
    github_put_file_tool.py. Each tool returns one dict.

    github_list_files: entries[] of name, path, type, size, sha,
    html_url, plus count. sha on an entry is the blob sha.
    github_get_file: content (utf-8 text, or base64), encoding, sha.
    No commit_sha. A directory path is ok false.
    github_put_file: created, sha (new blob), commit_sha, html_url.
    The body does not include the file text.
    """
    inner, err = _github_tool_dict(envelope)
    if err:
        return None, err
    if inner.get("ok") is not True:
        return None, str(inner.get("error") or "github ok false")[:200]
    if "entries" in inner and not isinstance(inner.get("entries"), list):
        return None, "entries not a list"
    return inner, None


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
    """Set headline and row notes. No MCP. notes maps '+'-joined keys to text.

    Readings (device, syslog, Grafana) and threads (ServiceNow) both
    carry keys and a note. A stamp uses one of those lists.
    """
    path = Path(stamp_path)
    with path.open(encoding="utf-8") as fh:
        stamp = json.load(fh)
    stamp["headline"] = headline
    unmatched = set(notes)
    for bucket in ("readings", "threads"):
        for reading in stamp.get(bucket) or []:
            if not isinstance(reading, dict):
                continue
            key = "+".join(reading.get("keys") or [])
            if key in notes and notes[key]:
                reading["note"] = notes[key]
                unmatched.discard(key)
    if unmatched:
        print("annotate unmatched keys: " + ", ".join(sorted(unmatched)), file=sys.stderr)
    validate(stamp, schema_path)
    path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return path
