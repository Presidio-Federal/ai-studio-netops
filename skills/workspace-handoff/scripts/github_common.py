#!/usr/bin/env python3
"""GitHub Actions helpers shared by the compliance runner and Pipeline Monitor.

Lifted unchanged from compliance-test-runner scripts/run_suite.py.
call_tool uses visit_common.mcp_call. poll_run reads a run once and
does not sleep.
"""
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import visit_common  # noqa: E402


MARKER = "# Network test report"
HEADER = re.compile(r"(PASSED|FAILED)\s+·\s+(live|static)\b", re.IGNORECASE)
COUNTS = re.compile(
    r"(?:counts_ran|static):\s+pass=(\d+)\s+fail=(\d+)\s+error=(\d+)\s+skip=(\d+)"
)
ROW = re.compile(
    r"^-\s+(PASS|FAIL|ERROR|SKIP)\s+`([^`]+)`\s+·\s+(\S+)(?:\s+—\s+(.*))?$"
)
NA_ROW = re.compile(r"^-\s+`([^`]+)`\s+·\s+(.+?)\s+—\s+(.*)$")
FAILED = re.compile(r"Failed:\s+(\S+)\s+([A-Za-z0-9_.-]+):\s*(.*)$")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\s?")
STATIC_RULE = re.compile(r"test_static_rule\[([^:\]]+)(?:::[^:\]]+)*::([^\]]+)\]")
RESULT_JSON = re.compile(r"NETWORK_TEST_RESULT_JSON=(\{.*\})")
KEY_RE = re.compile(r"^(device|interface|site|service|test|control|incident|change):[^ ]+$")


def coerce_part(raw):
    if isinstance(raw, str):
        text = raw.strip()
        if text[:1] in "{[":
            try:
                return json.loads(text, strict=False)
            except json.JSONDecodeError:
                return raw
        return raw
    return raw


def unwrap_body(envelope):
    """Keep every result part. The report is often not in result[0].

    github_get_action_run returns {ok, run: {jobs: [{id, name, status, conclusion, html_url}]}}.
    github_get_action_job_logs returns {ok, log}. Those dicts use ok, not success.
    """
    if isinstance(envelope, dict) and envelope.get("ok") is True and (
        "run" in envelope or "log" in envelope
    ):
        return envelope, None
    if not isinstance(envelope, dict) or not envelope.get("success"):
        err = None if not isinstance(envelope, dict) else envelope.get("error")
        return None, (str(err or "success false"))[:200]
    outer = envelope.get("result")
    if isinstance(outer, list):
        parts = [coerce_part(item) for item in outer]
        if len(parts) == 1:
            return parts[0], None
        return {"_parts": parts}, None
    if outer is None:
        return None, "empty result"
    return coerce_part(outer), None


def keys_hint(body):
    if isinstance(body, dict):
        return ",".join(sorted(str(key) for key in body.keys())[:12])
    if isinstance(body, list):
        return "list:%d" % len(body)
    return type(body).__name__


def payload_hint(body):
    """One line of the get-run shape. _parts alone hides where the job id sits."""
    node = flatten(body)
    parts = node.get("_parts") if isinstance(node, dict) else None
    if not isinstance(parts, list):
        return keys_hint(node)
    bits = []
    for index, part in enumerate(parts[:4]):
        if isinstance(part, dict):
            bits.append("p%d=%s" % (index, ",".join(list(part.keys())[:8])))
            run = part.get("run") if isinstance(part.get("run"), dict) else None
            if run is None and isinstance(part.get("data"), dict):
                run = part["data"].get("run") if isinstance(part["data"].get("run"), dict) else part["data"]
            if isinstance(run, dict):
                bits.append("run=%s" % ",".join(list(run.keys())[:12]))
                jobs = run.get("jobs")
                if isinstance(jobs, list):
                    bits.append("jobs=list:%d" % len(jobs))
                elif jobs is not None:
                    bits.append("jobs=%s" % type(jobs).__name__)
        elif isinstance(part, str):
            bits.append("p%d=str:%d" % (index, len(part)))
        elif isinstance(part, list):
            bits.append("p%d=list:%d" % (index, len(part)))
        else:
            bits.append("p%d=%s" % (index, type(part).__name__))
    return " ".join(bits)[:300]


def call_tool(tool, args):
    return unwrap_body(visit_common.mcp_call(tool, args, retries=1))


def check_id(rendered):
    text = str(rendered or "").strip()
    if "/" in text:
        return text.rsplit("/", 1)[-1]
    return text


def row_keys(check, device):
    keys = ["test:%s" % check_id(check), "device:%s" % device]
    return [key for key in keys if KEY_RE.match(key)]


def empty_counts():
    return {"pass": 0, "fail": 0, "error": 0, "skip": 0}


def add_counts(left, right):
    return {name: left[name] + right[name] for name in ("pass", "fail", "error", "skip")}


def parse_counts(text):
    match = COUNTS.search(text or "")
    if not match:
        return None
    return {
        "pass": int(match.group(1)),
        "fail": int(match.group(2)),
        "error": int(match.group(3)),
        "skip": int(match.group(4)),
    }


def header_bits(text):
    match = HEADER.search(text or "")
    banner = match.group(1).upper() if match else None
    mode = match.group(2).lower() if match else None
    lab = None
    lab_match = re.search(r"lab=(dev|prod)\b", text or "")
    if lab_match:
        lab = lab_match.group(1)
    requested = []
    req = re.search(r"requested=([^·\n]+)", text or "")
    if req and req.group(1).strip() not in ("", "lab-inventory"):
        requested = [part.strip() for part in req.group(1).split(",") if part.strip()]
    return banner, mode, lab, requested


def static_failures(text):
    rows = []
    seen = set()
    for line in (text or "").splitlines():
        match = FAILED.search(line.strip())
        if not match:
            continue
        device, check, detail = match.group(1), match.group(2), match.group(3).strip()
        identity = (device, check)
        if identity in seen:
            continue
        seen.add(identity)
        keys = row_keys(check, device)
        if len(keys) < 2:
            continue
        rows.append({
            "status": "FAIL",
            "plane": "static",
            "check": "static/%s" % check,
            "device": device,
            "keys": keys,
            "detail": detail[:500],
        })
    return rows


def live_rows(text):
    ran = []
    not_applicable = []
    gaps = []
    section = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.startswith("ran:"):
            section = "ran"
            continue
        if line.startswith("not_applicable:"):
            section = "na"
            continue
        if line.startswith("gaps:"):
            section = "gaps"
            if line != "gaps:" and "none" not in line.lower():
                gaps.append(line.split(":", 1)[-1].strip())
            continue
        if line.startswith("==") or line.startswith("##["):
            break
        if section == "ran":
            match = ROW.match(line)
            if not match:
                continue
            status, check, device, detail = match.groups()
            if re.match(r"\d+/\d+$", device):
                gaps.append("live results rolled up for %s" % check)
                continue
            keys = row_keys(check, device)
            if len(keys) < 2:
                continue
            row = {
                "status": status,
                "plane": "live",
                "check": check,
                "device": device,
                "keys": keys,
            }
            if detail and status in {"FAIL", "ERROR", "SKIP"}:
                row["detail"] = detail[:500]
            ran.append(row)
        elif section == "na":
            if line in ("- none", "none"):
                continue
            match = NA_ROW.match(line)
            if not match:
                continue
            check, devices, reason = match.groups()
            for device in [part.strip() for part in devices.split(",") if part.strip()]:
                keys = row_keys(check, device)
                if len(keys) < 2:
                    continue
                not_applicable.append({
                    "check": check,
                    "device": device,
                    "reason": reason[:500],
                    "keys": keys,
                })
        elif section == "gaps" and line.startswith("- "):
            gaps.append(line[2:].strip())
    return ran, not_applicable, gaps


def clean_log(text):
    """Drop the GitHub log timestamp and color codes so the report lines match."""
    lines = []
    for raw in (text or "").splitlines():
        lines.append(STAMP.sub("", ANSI.sub("", raw)))
    return "\n".join(lines)


def result_json(text):
    match = RESULT_JSON.search(text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def static_rows_from_json(data):
    rows = []
    seen = set()
    for item in data.get("failed_checks") or []:
        match = STATIC_RULE.search(str(item))
        if not match:
            continue
        device, check = match.group(1), match.group(2)
        if (device, check) in seen:
            continue
        seen.add((device, check))
        keys = row_keys(check, device)
        if len(keys) < 2:
            continue
        rows.append({
            "status": "FAIL",
            "plane": "static",
            "check": "static/%s" % check,
            "device": device,
            "keys": keys,
            "detail": str(item)[:500],
        })
    return rows


def report_blocks(text):
    if not text or MARKER not in text:
        return []
    blocks = []
    for part in text.split(MARKER)[1:]:
        chunk = MARKER + part
        cut = len(chunk)
        for marker in ("\n== ", "\n##["):
            at = chunk.find(marker)
            if at != -1:
                cut = min(cut, at)
        blocks.append(chunk[:cut])
    return blocks


def parse_report(text):
    """Return planes, rows, and whether the static compliance block was present.

    `NETWORK_TEST_RESULT_JSON` is the result the emit step prints. The
    `# Network test report` blocks are the same result split by plane.
    Use the blocks when they are in the log. Use the JSON when a block is not.
    """
    text = clean_log(text)
    static_text = ""
    live_text = ""
    lab = None
    requested = []
    for block in report_blocks(text):
        banner, mode, block_lab, block_requested = header_bits(block)
        if block_lab:
            lab = block_lab
        if block_requested:
            requested = block_requested
        if mode == "static":
            static_text = block
        elif mode == "live":
            live_text = block
    # Pytest failure lines sit above the static marker, so search the whole log.
    static_rows = static_failures(text) if static_text else []
    live_ran, not_applicable, gaps = live_rows(live_text)
    static_counts = parse_counts(static_text) if static_text else None
    live_counts = parse_counts(live_text) if live_text else None
    if live_counts is None and live_ran:
        live_counts = empty_counts()
        for row in live_ran:
            key = {"PASS": "pass", "FAIL": "fail", "ERROR": "error", "SKIP": "skip"}[row["status"]]
            live_counts[key] += 1
    na_match = re.search(r"counts_na:\s+(\d+)", live_text or "")
    tested = []
    tested_match = re.search(r"devices_tested:\s*(.+)", live_text or "")
    if tested_match and tested_match.group(1).strip() not in ("", "(none)"):
        tested = [part.strip() for part in tested_match.group(1).split(",") if part.strip()]
    parsed = {
        "lab": lab,
        "requested": requested,
        "devices_tested": tested,
        "static_present": bool(static_text),
        "live_present": bool(live_text),
        "static_counts": static_counts,
        "live_counts": live_counts,
        "static_rows": static_rows,
        "live_rows": live_ran,
        "not_applicable": not_applicable,
        "gaps": gaps,
        "counts_na": int(na_match.group(1)) if na_match else len(not_applicable),
    }
    data = result_json(text)
    if lab is None:
        lab_match = re.search(r"lab=(dev|prod)\b", text or "")
        if lab_match:
            lab = lab_match.group(1)
            parsed["lab"] = lab
    if data and not static_text:
        parsed["static_rows"] = static_rows_from_json(data)
        parsed["static_present"] = True
        if not live_text:
            parsed["static_counts"] = {
                "pass": int(data.get("pass") or 0),
                "fail": int(data.get("fail") or 0),
                "error": int(data.get("error") or 0),
                "skip": int(data.get("skip") or 0),
            }
            parsed["gaps"] = list(parsed["gaps"]) + [
                "plane split was not in this log; pass=%s fail=%s are the emit totals, and failed_checks are the static failures" % (
                    data.get("pass"), data.get("fail"),
                )
            ]
        else:
            live_pass = int((parsed["live_counts"] or {}).get("pass") or 0)
            parsed["static_counts"] = {
                "pass": max(0, int(data.get("pass") or 0) - live_pass),
                "fail": len(parsed["static_rows"]) or int(data.get("fail") or 0),
                "error": int(data.get("error") or 0),
                "skip": int(data.get("skip") or 0),
            }
    return parsed


def run_ids(body):
    rows = None
    if isinstance(body, dict) and isinstance(body.get("_parts"), list):
        found = []
        for part in body["_parts"]:
            found.extend(run_ids(part))
        return found
    if isinstance(body, list):
        rows = body
    elif isinstance(body, dict):
        for key in ("workflow_runs", "runs", "workflowRuns"):
            if isinstance(body.get(key), list):
                rows = body[key]
                break
        if rows is None and isinstance(body.get("data"), (dict, list)):
            return run_ids(body["data"])
        if rows is None and body.get("id"):
            rows = [body]
    if rows is None:
        return []
    found = []
    for row in rows:
        if isinstance(row, dict) and row.get("id") is not None:
            found.append(str(row["id"]))
    return found


def run_url(body, run_id):
    rows = []
    if isinstance(body, dict):
        for key in ("workflow_runs", "runs"):
            if isinstance(body.get(key), list):
                rows = body[key]
        if body.get("id") is not None:
            rows = rows or [body]
        data = body.get("data")
        if isinstance(data, dict):
            return run_url(data, run_id)
    elif isinstance(body, list):
        rows = body
    for row in rows:
        if isinstance(row, dict) and str(row.get("id")) == str(run_id):
            return row.get("html_url") or row.get("htmlUrl") or ""
    return ""


def flatten(node, depth=0):
    """Parse JSON strings the MCP wraps inside text or result fields."""
    if depth > 6:
        return node
    if isinstance(node, str):
        text = node.strip()
        if text[:1] in "{[" and len(text) < 500000:
            try:
                return flatten(json.loads(text, strict=False), depth + 1)
            except json.JSONDecodeError:
                return node
        return node
    if isinstance(node, list):
        return [flatten(item, depth + 1) for item in node[:40]]
    if isinstance(node, dict):
        return {key: flatten(item, depth + 1) for key, item in node.items()}
    return node


def collect_runs(node, runs, jobs, depth=0):
    if depth > 8 or node is None:
        return
    if isinstance(node, list):
        for item in node:
            collect_runs(item, runs, jobs, depth + 1)
        return
    if not isinstance(node, dict):
        return
    if node.get("status") or node.get("conclusion") or node.get("html_url") or node.get("htmlUrl"):
        runs.append(node)
    for key in ("jobs", "workflow_jobs", "workflowJobs"):
        value = node.get(key)
        if isinstance(value, list):
            jobs.extend(item for item in value if isinstance(item, dict))
    for value in node.values():
        if isinstance(value, (dict, list)):
            collect_runs(value, runs, jobs, depth + 1)


def pick_run(runs, run_id):
    matches = [
        row for row in runs
        if str(row.get("id") or row.get("run_id") or "") == str(run_id)
    ]
    for row in reversed(matches):
        if row.get("status") or row.get("conclusion"):
            return row
    if matches:
        return matches[-1]
    return {}


def read_run(body, run_id):
    runs = []
    jobs = []
    collect_runs(flatten(body), runs, jobs)
    run = pick_run(runs, run_id)
    if not jobs:
        _ignored, jobs = split_jobs(body if isinstance(body, dict) else {})
    return run, jobs


def github_status(run):
    status = str((run or {}).get("status") or "").lower()
    conclusion = str((run or {}).get("conclusion") or "").lower()
    if status or conclusion:
        return conclusion and status and ("%s/%s" % (status, conclusion)) or status or conclusion
    return ""


def split_jobs(body):
    if not isinstance(body, dict):
        return {}, []
    jobs = []
    for key in ("jobs", "workflow_jobs", "workflowJobs"):
        if isinstance(body.get(key), list):
            jobs = body[key]
            break
    inner = body.get("run") or body.get("workflow_run") or body.get("workflowRun")
    if isinstance(inner, dict):
        nested, nested_jobs = split_jobs(inner)
        return nested or inner, jobs or nested_jobs
    data = body.get("data")
    if isinstance(data, dict) and not jobs:
        return split_jobs(data)
    return body, jobs


def collect_text(node, found, depth=0):
    if depth > 8 or node is None:
        return
    if isinstance(node, str):
        text = node.strip()
        if len(text) > 40:
            found.append(text)
        return
    if isinstance(node, list):
        if node and all(isinstance(item, str) for item in node[:50]):
            found.append("\n".join(node))
        for item in node[:80]:
            collect_text(item, found, depth + 1)
        return
    if isinstance(node, dict):
        for value in node.values():
            collect_text(value, found, depth + 1)


def log_text(body):
    """Pull the job log out of whatever envelope the MCP returned.

    Prefer the string that contains the report marker or the result JSON.
    A short status field must not hide the log sitting next to it.
    """
    found = []
    collect_text(flatten(body), found)
    for text in found:
        if MARKER in text or "NETWORK_TEST_RESULT_JSON=" in text:
            return text
    if not found:
        return None
    return max(found, key=len)


def job_id(job):
    if not isinstance(job, dict):
        return None
    for key in ("id", "job_id", "jobId"):
        if job.get(key) is not None:
            return str(job[key])
    return None


def step_state(step):
    if not isinstance(step, dict):
        return "absent"
    conclusion = step.get("conclusion")
    status = step.get("status")
    if conclusion == "skipped":
        return "skipped"
    if status == "in_progress":
        return "in_progress"
    if status == "completed" or conclusion in {"success", "failure", "cancelled"}:
        return "completed"
    if status in {"queued", "pending"}:
        return "queued"
    return "unknown"


DONE = {"success", "failure", "cancelled", "timed_out", "skipped", "neutral", "stale"}
SPEAK_PHASES = {"running static tests", "running live tests"}


def run_finished(run, jobs):
    """True when the workflow or every returned job has actually finished.

    Step names can say live tests are done while the run status is still
    in progress. The report waits for this, not for the phase string.
    """
    status = str((run or {}).get("status") or "").lower()
    conclusion = str((run or {}).get("conclusion") or "").lower()
    if status == "completed" or conclusion in DONE:
        return True
    if not jobs:
        return False
    for job in jobs:
        if not isinstance(job, dict):
            return False
        job_status = str(job.get("status") or "").lower()
        job_conclusion = str(job.get("conclusion") or "").lower()
        if job_status != "completed" and job_conclusion not in DONE:
            return False
    return True


def current_phase(jobs):
    """Phase from the test.yml step names on the job you ran 2026-10-06.

    Returns None when the run payload has no Static pytest / Live pyATS
    steps, so the caller keeps waiting instead of spinning the agent.
    """
    named = {}
    for job in jobs or []:
        steps = job.get("steps") if isinstance(job, dict) else None
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict) and step.get("name"):
                named[step["name"]] = step
    if "Static pytest" not in named and "Live pyATS" not in named:
        return None
    static = step_state(named.get("Static pytest"))
    live = step_state(named.get("Live pyATS"))
    if static == "in_progress":
        return "running static tests"
    if live == "in_progress":
        return "running live tests"
    if static == "completed" and live in {"queued", "unknown", "absent"}:
        return "static tests complete"
    if live == "completed":
        return "live tests complete"
    return None


def job_ids_in(body, run_id):
    """Job ids for this workflow run.

    A workflow run and a job both have id, name, and status. Take an id
    from a jobs list, or from /runs/<this run>/job/<id>. Do not take the
    id of another workflow run. Passing a run id to the log tool returns
    a short error, not the report.
    """
    found = []
    want = str(run_id)
    node = flatten(body)

    def add(value):
        text = str(value or "")
        if text.isdigit() and text != want and text not in found:
            found.append(text)

    def take_job(job):
        if not isinstance(job, dict):
            return
        if job.get("head_sha") or job.get("head_branch") or job.get("jobs_url") or job.get("sha") or job.get("branch"):
            return
        rid = str(job.get("run_id") or job.get("runId") or "")
        if rid and rid != want:
            return
        add(job.get("id") or job.get("job_id") or job.get("jobId"))

    def walk(item):
        if isinstance(item, dict):
            for key in ("jobs", "workflow_jobs", "workflowJobs"):
                value = item.get(key)
                if isinstance(value, list):
                    for job in value:
                        take_job(job)
                elif isinstance(value, dict):
                    nested = value.get("jobs")
                    if isinstance(nested, list):
                        for job in nested:
                            take_job(job)
                    elif value.get("id") or value.get("name"):
                        take_job(value)
            for value in item.values():
                walk(value)
        elif isinstance(item, list):
            for value in item:
                walk(value)
        elif isinstance(item, str):
            for match in re.finditer(r"/runs/(\d+)/job/(\d+)", item):
                if match.group(1) == want:
                    add(match.group(2))

    walk(node)
    return found


def observe_run(run_id, ref):
    """Read one run. The list tool has no jobs, so it cannot stand in for this call.

    github_get_action_run requires run_id as an integer. A string is a
    schema error, and the list fallback then looks like a run with no job id.
    """
    try:
        rid = int(str(run_id).strip())
    except (TypeError, ValueError):
        return {}, [], "error", None, "run_id is not an integer"
    body, err = call_tool("github_get_action_run", {"run_id": rid})
    if err:
        return {}, [], "error", None, err
    run, jobs = read_run(body, run_id)
    status = github_status(run)
    if not status:
        return run, jobs, "unreadable", body, "github_get_action_run had no status (%s)" % payload_hint(body)
    return run, jobs, status, body, None


def poll_run(run_id, ref):
    """One read. A finished run is returned so the caller writes the visit.

    A run that is still going comes back immediately. This function does
    not sleep and does not poll.
    """
    run, jobs, status, body, get_err = observe_run(run_id, ref)
    html_url = (run.get("html_url") or run.get("htmlUrl") or "") if isinstance(run, dict) else ""
    if get_err:
        return html_url, jobs, get_err, None, status, body
    phase = current_phase(jobs)
    if run_finished(run, jobs):
        return html_url, jobs, None, phase, status or "completed", body
    if phase in SPEAK_PHASES:
        return html_url, jobs, "running", phase, status, body
    return html_url, jobs, "running", None, status, body


def report_in(text):
    return bool(text) and (
        MARKER in text or "NETWORK_TEST_RESULT_JSON=" in text or "· static ·" in text or "· live ·" in text
    )


def read_logs(jobs, run_id, body):
    """Read the report. It may already be in the get-run payload, or in the job log."""
    embedded = log_text(body) if body is not None else None
    if report_in(embedded):
        return embedded, None
    ids = []
    for job in jobs or []:
        if isinstance(job, dict) and not (job.get("sha") or job.get("branch") or job.get("jobs_url")):
            jid = str(job.get("id") or job.get("job_id") or "")
            if jid.isdigit() and jid != str(run_id) and jid not in ids:
                ids.append(jid)
    for jid in job_ids_in(body, run_id):
        if jid not in ids:
            ids.append(jid)
    if not ids:
        return "", "run payload had no job id (%s)" % payload_hint(body)
    chunks = []
    errors = []
    for jid in ids[:3]:
        fetched, err = call_tool("github_get_action_job_logs", {"job_id": int(jid), "tail_lines": 20000})
        if err:
            errors.append(err)
            continue
        text = log_text(fetched)
        if text:
            chunks.append(text)
    joined = "\n".join(chunks)
    if report_in(joined):
        return joined, None
    if errors and not chunks:
        return "", "job log: %s" % errors[0]
    if not report_in(joined):
        return joined, "job log had no network test report (%d chars, jobs=%s)" % (len(joined), ",".join(ids) or "none")
    return joined, None
