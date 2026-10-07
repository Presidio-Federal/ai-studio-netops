#!/usr/bin/env python3
"""Dispatch test.yml, poll, and write the testing records.

run executes under execution_type mcp_orchestration. The script triggers
the workflow, waits, parses every # Network test report in the job log,
and writes the workspace files. A compliance suite keeps mode=live: that
job prints a static report and then a live report. The agent reads the
last stdout line and does not call the GitHub tools itself.

The log shape is the one test.yml printed on 2026-10-06
(run 37511296683): a static block with `static: pass= fail= error= skip=`
and pytest `Failed: <device> <check-id>:` lines, then a live block with
`counts_ran:` and `- PASS `suite/check` · device` rows.

  python3 <skill>/scripts/run_suite.py run --workspace <file_explorer> \\
      --environment prod --suites compliance --allow-all true \\
      --production-authorized true --reason adhoc
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
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

SKILL = Path(__file__).resolve().parent.parent
RUN_SCHEMA = SKILL / "schemas" / "testing-run.schema.json"
STATE_SCHEMA = SKILL / "schemas" / "testing-state.schema.json"
VISIT_SCHEMA = SKILL / "schemas" / "compliance-test-visit.schema.json"
META_SCHEMA = SKILL / "schemas" / "compliance-test-metadata.schema.json"

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


def stamp_name(moment):
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


def checked_at(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def pct(numerator, denominator):
    if not denominator:
        return None
    return round(100.0 * numerator / denominator, 1)


def unwrap_body(envelope):
    if not isinstance(envelope, dict) or not envelope.get("success"):
        err = None if not isinstance(envelope, dict) else envelope.get("error")
        return None, (str(err or "success false"))[:200]
    outer = envelope.get("result")
    raw = outer[0] if isinstance(outer, list) and outer else outer
    if isinstance(raw, (dict, list)):
        return raw, None
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text, strict=False), None
            except json.JSONDecodeError:
                return raw, None
        return raw, None
    return None, "empty result"


def keys_hint(body):
    if isinstance(body, dict):
        return ",".join(sorted(str(key) for key in body.keys())[:12])
    if isinstance(body, list):
        return "list:%d" % len(body)
    return type(body).__name__


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

    The two `# Network test report` blocks are the detail. They sit hundreds
    of lines above the end of the job log. The last lines carry
    `NETWORK_TEST_RESULT_JSON`, which is what a short log tail actually
    contains. Use that when the blocks were not in the text.
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
                "per-check report was above the log tail; totals are NETWORK_TEST_RESULT_JSON pass=%s fail=%s" % (
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
            parsed["gaps"] = list(parsed["gaps"]) + [
                "static pass count was above the log tail; static failures are from NETWORK_TEST_RESULT_JSON"
            ]
    return parsed


def union_keys(rows):
    found = []
    for row in rows:
        for key in row.get("keys") or []:
            if key not in found and KEY_RE.match(key):
                found.append(key)
    return found


def pair_of(row):
    test = None
    device = row.get("device")
    for key in row.get("keys") or []:
        if key.startswith("test:") and test is None:
            test = key.split(":", 1)[1]
        if key.startswith("device:") and not device:
            device = key.split(":", 1)[1]
    return test, device


def group_tests(rows):
    by_test = {}
    for row in rows:
        test, _device = pair_of(row)
        if not test:
            continue
        by_test.setdefault(test, []).append(row["status"])
    verified = failing = skipped = 0
    for statuses in by_test.values():
        if any(status in {"FAIL", "ERROR"} for status in statuses):
            failing += 1
        elif any(status == "PASS" for status in statuses):
            verified += 1
        elif any(status == "SKIP" for status in statuses):
            skipped += 1
    return verified, failing, skipped


def judge_status(compliance, parsed, live_counts, static_counts):
    if not parsed["live_present"] and not parsed["static_present"]:
        return "UNKNOWN"
    if compliance and not parsed["static_present"]:
        return "UNKNOWN"
    planes = [live_counts or empty_counts()]
    if compliance:
        planes.append(static_counts or empty_counts())
    fails = sum(plane["fail"] + plane["error"] for plane in planes)
    passes = sum(plane["pass"] for plane in planes)
    skips = sum(plane["skip"] for plane in planes)
    if fails and passes:
        return "MIXED"
    if fails:
        return "FAIL"
    if passes and skips:
        return "MIXED"
    if passes:
        return "PASS"
    if skips:
        return "FAIL"
    return "UNKNOWN"


def risk_for(status, lab, parsed):
    if status == "UNKNOWN":
        return "UNKNOWN", "unknown", "No network test report in the job log.", ["no marker"]
    live = parsed["live_counts"] or empty_counts()
    static = parsed["static_counts"] or empty_counts()
    failed = live["fail"] + live["error"] + static["fail"] + static["error"]
    skipped = live["skip"] + static["skip"]
    if failed:
        level, push = "HIGH", "do_not_push"
        verdict = "A check failed."
    elif skipped:
        level, push = "MEDIUM", "proceed_with_caution"
        verdict = "Passed with skip gaps."
    else:
        level, push = "LOW", "proceed_with_caution"
        verdict = "In-scope checks passed."
    if lab != "prod":
        push = "proceed_with_caution" if push != "do_not_push" and push != "unknown" else push
        if push == "proceed":
            push = "proceed_with_caution"
    why = []
    if static["fail"] or static["error"]:
        why.append("static fail=%d error=%d" % (static["fail"], static["error"]))
    if live["fail"] or live["error"]:
        why.append("live fail=%d error=%d" % (live["fail"], live["error"]))
    if skipped:
        why.append("skip=%d" % skipped)
    if not why:
        why.append(verdict)
    return level, push, verdict, why


def metrics_of(moment, visit_id, lab, counts, rows, counts_na, planes):
    verified, failing, skipped = group_tests(rows)
    total = counts["pass"] + counts["fail"] + counts["error"]
    return {
        "at": checked_at(moment),
        "scope": "suite:compliance",
        "visit_id": visit_id,
        "environment": lab,
        "pass": counts["pass"],
        "fail": counts["fail"],
        "error": counts["error"],
        "skip": counts["skip"],
        "not_applicable": counts_na,
        "verified_tests": verified,
        "failing_tests": failing,
        "skipped_tests": skipped,
        "tested_posture_pct": pct(verified, verified + failing),
        "device_check_pass_pct": pct(counts["pass"], total),
        "planes": {
            "live": plane_metrics(planes["live"]),
            "static": plane_metrics(planes["static"]),
        },
    }


def plane_metrics(counts):
    total = counts["pass"] + counts["fail"] + counts["error"]
    return {
        "pass": counts["pass"],
        "fail": counts["fail"],
        "error": counts["error"],
        "skip": counts["skip"],
        "device_check_pass_pct": pct(counts["pass"], total),
    }


def index_rows(rows):
    found = {}
    for row in rows:
        test, device = pair_of(row)
        if test and device:
            found[(test, device)] = row
    return found


def vs_prior(prior, current_rows, metrics):
    if not prior:
        return {
            "prior_visit_id": None,
            "delta": "first",
            "newly_passing": [],
            "newly_failing": [],
            "still_failing": 0,
            "metrics_delta": None,
        }
    prior_rows = index_rows((prior.get("results") or {}).get("ran") or [])
    current = index_rows(current_rows)
    newly_passing = []
    newly_failing = []
    still = 0
    for identity, row in prior_rows.items():
        if row.get("status") not in {"FAIL", "ERROR"}:
            continue
        now = current.get(identity)
        if now is None or now.get("status") == "SKIP":
            continue
        if now.get("status") == "PASS":
            newly_passing.append(flip(identity, row.get("status"), "PASS", now))
        elif now.get("status") in {"FAIL", "ERROR"}:
            still += 1
    for identity, row in current.items():
        if row.get("status") not in {"FAIL", "ERROR"}:
            continue
        old = prior_rows.get(identity)
        if old and old.get("status") == "PASS":
            newly_failing.append(flip(identity, "PASS", row.get("status"), row))
    if newly_passing and not newly_failing:
        delta = "better"
    elif newly_failing and not newly_passing:
        delta = "worse"
    elif newly_passing and newly_failing:
        delta = "mixed"
    else:
        delta = "unchanged"
    prior_metrics = prior.get("metrics") or {}
    return {
        "prior_visit_id": prior.get("visit_id"),
        "delta": delta,
        "newly_passing": newly_passing[:100],
        "newly_failing": newly_failing[:100],
        "still_failing": still,
        "metrics_delta": {
            "verified_tests": metrics["verified_tests"] - int(prior_metrics.get("verified_tests") or 0),
            "failing_tests": metrics["failing_tests"] - int(prior_metrics.get("failing_tests") or 0),
            "tested_posture_pct": subtract_pct(metrics["tested_posture_pct"], prior_metrics.get("tested_posture_pct")),
            "device_check_pass_pct": subtract_pct(metrics["device_check_pass_pct"], prior_metrics.get("device_check_pass_pct")),
        },
    }


def flip(identity, origin, dest, row):
    test, device = identity
    return {
        "test": test,
        "device": device,
        "from": origin,
        "to": dest,
        "keys": list(row.get("keys") or []),
    }


def subtract_pct(current, prior):
    if current is None or prior is None:
        return None
    return round(float(current) - float(prior), 1)


def load_json(path):
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def prior_visit(workspace, lab):
    meta_path = Path(workspace) / "compliance" / "metadata-testing.json"
    meta = load_json(meta_path) or {}
    by_env = meta.get("last_visit_by_environment")
    other = {"dev": None, "prod": None}
    prior_id = None
    if isinstance(by_env, dict):
        other["dev"] = by_env.get("dev")
        other["prod"] = by_env.get("prod")
        prior_id = by_env.get(lab)
    elif meta.get("last_visit_id"):
        candidate = load_json(Path(workspace) / "compliance" / "testing" / ("%s.json" % meta["last_visit_id"]))
        candidate_lab = ((candidate or {}).get("environment") or {}).get("live_lab")
        if candidate_lab == lab:
            prior_id = meta["last_visit_id"]
        if candidate_lab in ("dev", "prod"):
            other[candidate_lab] = meta["last_visit_id"]
    prior = None
    if prior_id:
        prior = load_json(Path(workspace) / "compliance" / "testing" / ("%s.json" % prior_id))
    return meta, other, prior


def prune_visits(workspace, newest, keep=10):
    current = newest
    chain = []
    seen = set()
    while current and current not in seen and len(chain) < keep + 5:
        seen.add(current)
        chain.append(current)
        visit = load_json(Path(workspace) / "compliance" / "testing" / ("%s.json" % current))
        current = ((visit or {}).get("vs_prior") or {}).get("prior_visit_id")
    for old in chain[keep:]:
        path = Path(workspace) / "compliance" / "testing" / ("%s.json" % old)
        if path.is_file():
            path.unlink()


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def headline_for(status, lab, suites, live_counts, static_counts):
    live = live_counts or empty_counts()
    text = "%s on %s suites=%s live pass=%d fail=%d" % (
        status, lab, ",".join(suites), live["pass"], live["fail"]
    )
    if static_counts:
        text += " static pass=%d fail=%d" % (static_counts["pass"], static_counts["fail"])
    return text[:240]


def next_action_for(status):
    if status == "FAIL" or status == "MIXED":
        return "Review the failed checks before treating this lab as compliant."
    if status == "UNKNOWN":
        return "The job log had no usable network test report."
    return "No failed checks."


def build_records(args, moment, run_id, html_url, parsed):
    suites = [part.strip() for part in (args.suites or "").split(",") if part.strip()]
    compliance = "compliance" in suites
    lab = parsed["lab"] or args.environment
    if lab not in ("dev", "prod"):
        lab = args.environment if args.environment in ("dev", "prod") else "dev"
    live_counts = parsed["live_counts"] or empty_counts()
    static_counts = parsed["static_counts"] if parsed["static_present"] else (empty_counts() if compliance else None)
    rows = list(parsed["live_rows"])
    if compliance:
        rows.extend(parsed["static_rows"])
    status = judge_status(compliance, parsed, live_counts, static_counts)
    if compliance and not parsed["static_present"]:
        parsed["gaps"] = list(parsed["gaps"]) + ["static report block was not in the job log"]
    level, push, verdict, why = risk_for(status, lab, parsed)
    visit_id = stamp_name(moment)
    counts = add_counts(live_counts, static_counts or empty_counts()) if compliance else live_counts
    requested = [part.strip() for part in (args.devices or "").split(",") if part.strip()] or parsed["requested"]
    scanned = parsed["devices_tested"] or parsed["requested"] or requested
    results = {
        "counts_ran": counts,
        "counts_na": parsed["counts_na"],
        "ran": rows,
        "not_applicable": parsed["not_applicable"],
        "gaps": parsed["gaps"],
    }
    if compliance:
        results["counts_by_plane"] = {
            "live": live_counts,
            "static": static_counts or empty_counts(),
        }
    run_record = {
        "keys": union_keys(rows + parsed["not_applicable"]),
        "version": 1,
        "updated_at": checked_at(moment),
        "source_agent": "compliance-test",
        "status": status,
        "headline": headline_for(status, lab, suites, live_counts, static_counts if compliance else None),
        "next_action": next_action_for(status),
        "github_run_id": str(run_id),
        "github_run_url": html_url or "",
        "environment": {
            "live_lab": lab,
            "lab_role": "production" if lab == "prod" else "digital_twin",
            "note": "Production evidence" if lab == "prod" else "Proposal validation only",
        },
        "scope": {
            "devices_requested": requested,
            "devices_scanned": scanned,
            "suites": suites or ["compliance"],
            "tags": [part.strip() for part in (args.tags or "").split(",") if part.strip()],
        },
        "results": results,
        "risk": {
            "level": level,
            "push_to_prod": push,
            "verdict": verdict,
            "why": why,
        },
    }
    rel = "operational/testing/%s.json" % visit_id
    run_record["local_path"] = rel
    state = {
        "keys": [],
        "schema": "testing-state/v1",
        "updated_at": checked_at(moment),
        "source_agent": "compliance-test",
        "status": status,
        "headline": run_record["headline"],
        "run": {
            "run_id": str(run_id),
            "html_url": html_url or None,
            "live_lab": lab,
            "mode": "live" if args.mode != "static" else "static",
            "suites": suites,
        },
        "risk": {"level": level, "push_to_prod": push, "note": verdict},
        "latest": rel,
        "gaps": parsed["gaps"][:20],
        "next_action": next_action_for(status),
        "failing_devices": sorted({row["device"] for row in rows if row["status"] in {"FAIL", "ERROR"}}),
    }
    visit = None
    meta = None
    if compliance:
        _old_meta, other, prior = prior_visit(args.workspace, lab)
        visit_metrics = metrics_of(
            moment, visit_id, lab, counts, rows, parsed["counts_na"],
            {"live": live_counts, "static": static_counts or empty_counts()},
        )
        visit = {
            "keys": run_record["keys"],
            "schema": "compliance-test-visit/v3",
            "visit_id": visit_id,
            "checked_at": checked_at(moment),
            "source_agent": "compliance-test",
            "status": status,
            "headline": run_record["headline"],
            "next_action": next_action_for(status),
            "github_run_id": str(run_id),
            "github_run_url": html_url or "unknown",
            "environment": run_record["environment"],
            "scope": run_record["scope"],
            "results": results,
            "risk": {
                "level": level,
                "push_to_prod": push,
                "verdict": verdict,
                "why": why,
            },
            "metrics": visit_metrics,
            "vs_prior": vs_prior(prior, rows, visit_metrics),
        }
        other[lab] = visit_id
        meta = {
            "keys": [],
            "schema": "compliance-test-metadata/v2",
            "source_agent": "compliance-test",
            "last_visit_id": visit_id,
            "last_collected_at": checked_at(moment),
            "last_visit_by_environment": {"dev": other.get("dev"), "prod": other.get("prod")},
        }
    return rel, run_record, state, visit, meta


def summary_payload(status, run_id, html_url, lab, suites, parsed, level, push, wrote, delta, passing, failing, still):
    payload = {
        "result": status,
        "run_id": str(run_id) if run_id else None,
        "html_url": html_url,
        "environment": lab,
        "suites": suites,
        "live": parsed["live_counts"] or empty_counts(),
        "na": parsed["counts_na"],
        "risk": level,
        "push_to_prod": push,
        "wrote": wrote,
        "gaps": parsed["gaps"][:8],
    }
    if parsed["static_present"] or "compliance" in suites:
        payload["static"] = parsed["static_counts"] or empty_counts()
    if delta:
        payload["delta"] = delta
        payload["newly_passing"] = passing
        payload["newly_failing"] = failing
        payload["still_failing"] = still
        payload["prior_visit_id"] = None
    return payload


def emit(payload):
    print(visit_common.summary(payload))


def run_ids(body):
    rows = None
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
    for row in reversed(runs):
        if (row.get("html_url") or row.get("htmlUrl") or row.get("run_number") is not None) and (
            row.get("status") or row.get("conclusion")
        ):
            return row
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


def workflow_inputs(args):
    suites = args.suites or ""
    compliance = "compliance" in [part.strip() for part in suites.split(",")]
    mode = "live" if compliance else (args.mode or "live")
    inputs = {
        "mode": mode,
        "environment": "none" if mode == "static" else args.environment,
        "devices": args.devices or "",
        "tags": args.tags or "",
        "suites": suites,
        "policies": "",
        "reason": args.reason or "adhoc",
    }
    if mode == "static" or compliance:
        inputs["scan_dir"] = "inventory/configs"
    devices = [part for part in (args.devices or "").split(",") if part.strip()]
    tags = [part for part in (args.tags or "").split(",") if part.strip()]
    if mode != "static" and not devices and not tags:
        inputs["allow_all_devices"] = "true"
    elif args.allow_all == "true":
        inputs["allow_all_devices"] = "true"
    if args.environment == "prod" and mode != "static":
        inputs["production_authorized"] = "true" if args.production_authorized == "true" else "false"
        if inputs["production_authorized"] != "true":
            return None, "production run requires --production-authorized true"
    return inputs, None


def dispatch_and_find(args, budget):
    listed, err = call_tool(
        "github_list_action_runs",
        {"workflow": "test.yml", "branch": args.ref, "limit": 5},
    )
    before = set(run_ids(listed)) if err is None else set()
    if err:
        return None, None, err or ("runs not found (%s)" % keys_hint(listed))
    inputs, input_err = workflow_inputs(args)
    if input_err:
        return None, None, input_err
    triggered, err = call_tool(
        "github_run_action",
        {"workflow": "test.yml", "ref": args.ref, "inputs": inputs},
    )
    if err:
        return None, None, err
    direct = None
    if isinstance(triggered, dict):
        direct = triggered.get("id") or triggered.get("run_id")
        nested = triggered.get("run") or triggered.get("workflow_run")
        if isinstance(nested, dict) and nested.get("id"):
            direct = nested["id"]
    if direct:
        return str(direct), triggered.get("html_url") if isinstance(triggered, dict) else "", None
    for _attempt in range(3):
        if budget.left() < 15:
            break
        time.sleep(5)
        body, err = call_tool(
            "github_list_action_runs",
            {"workflow": "test.yml", "branch": args.ref, "limit": 5},
        )
        if err:
            continue
        fresh = [run_id for run_id in run_ids(body) if run_id not in before]
        if fresh:
            return fresh[0], run_url(body, fresh[0]), None
    return None, None, "dispatched test.yml but no new run id came back (%s)" % keys_hint(listed)


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


def observe_run(run_id, ref):
    """Read the run. Fall back to the recent-runs list when the get payload has no status."""
    body, err = call_tool("github_get_action_run", {"run_id": run_id})
    run, jobs = read_run(body, run_id) if err is None else ({}, [])
    status = github_status(run)
    if run_finished(run, jobs):
        return run, jobs, status
    if not status:
        listed, list_err = call_tool(
            "github_list_action_runs",
            {"workflow": "test.yml", "branch": ref or "main", "limit": 5},
        )
        if list_err is None:
            listed_run, listed_jobs = read_run(listed, run_id)
            listed_status = github_status(listed_run)
            if listed_status or listed_jobs:
                run = listed_run or run
                jobs = jobs or listed_jobs
                status = listed_status or status
    return run, jobs, status or ("unreadable" if err is None else "error")


def poll_run(run_id, ref):
    """One read. A finished run is returned so the caller writes the visit.

    A run that is still going comes back immediately. This function does
    not sleep and does not poll.
    """
    run, jobs, status = observe_run(run_id, ref)
    html_url = (run.get("html_url") or run.get("htmlUrl") or "") if isinstance(run, dict) else ""
    phase = current_phase(jobs)
    if run_finished(run, jobs):
        return html_url, jobs, None, phase, status or "completed"
    if phase in SPEAK_PHASES:
        return html_url, jobs, "running", phase, status
    return html_url, jobs, "running", None, status


def read_logs(jobs):
    chunks = []
    last_id = None
    for job in jobs:
        jid = job_id(job)
        if not jid:
            continue
        last_id = jid
        body, err = call_tool(
            "github_get_action_job_logs",
            {"job_id": jid, "tail_lines": 4000},
        )
        text = log_text(body) if err is None else None
        if text:
            chunks.append(text)
    joined = "\n".join(chunks)
    if chunks and MARKER not in joined and "NETWORK_TEST_RESULT_JSON=" not in joined and last_id:
        body, err = call_tool(
            "github_get_action_job_logs",
            {"job_id": last_id, "tail_lines": 8000},
        )
        text = log_text(body) if err is None else None
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def execute(args):
    if args.environment not in {"dev", "prod"}:
        emit({"result": "UNKNOWN", "reason": "environment must be dev or prod"})
        return
    if not (args.suites or "").strip():
        emit({"result": "UNKNOWN", "reason": "missing suites"})
        return
    run_id = (args.run_id or "").strip()
    html_url = ""
    if not run_id:
        budget = visit_common.Budget(30)
        run_id, html_url, err = dispatch_and_find(args, budget)
        if err:
            emit({"result": "UNKNOWN", "reason": err, "environment": args.environment, "suites": args.suites})
            return
    html_url, jobs, err, phase, status = poll_run(run_id, args.ref)
    suites = [part.strip() for part in args.suites.split(",") if part.strip()]
    if err == "running":
        payload = {
            "result": "running",
            "run_id": run_id,
            "html_url": html_url,
            "environment": args.environment,
            "suites": suites,
            "github_status": status or "unreadable",
        }
        steps = []
        for job in jobs or []:
            listed = job.get("steps") if isinstance(job, dict) else None
            if not isinstance(listed, list):
                continue
            for step in listed:
                if isinstance(step, dict) and step.get("name") in {"Static pytest", "Live pyATS"}:
                    steps.append("%s:%s" % (step["name"], step_state(step)))
        if steps:
            payload["steps"] = steps
        if phase in SPEAK_PHASES:
            payload["phase"] = phase
        emit(payload)
        return
    if err:
        emit({"result": "UNKNOWN", "reason": err, "run_id": run_id, "html_url": html_url})
        return
    text = read_logs(jobs)
    parsed = parse_report(text)
    moment = datetime.now(timezone.utc)
    rel, run_record, state, visit, meta = build_records(args, moment, run_id, html_url, parsed)
    try:
        visit_common.validate(run_record, RUN_SCHEMA)
        visit_common.validate(state, STATE_SCHEMA)
        if visit is not None:
            visit_common.validate(visit, VISIT_SCHEMA)
            visit_common.validate(meta, META_SCHEMA)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    root = Path(args.workspace)
    write_json(root / rel, run_record)
    write_json(root / "state" / "testing.json", state)
    wrote = ["state/testing.json", rel]
    delta = passing = failing = still = None
    prior_id = None
    if visit is not None:
        write_json(root / "compliance" / "testing" / ("%s.json" % visit["visit_id"]), visit)
        write_json(root / "compliance" / "metadata-testing.json", meta)
        prune_visits(args.workspace, visit["visit_id"])
        wrote.extend([
            "compliance/metadata-testing.json",
            "compliance/testing/%s.json" % visit["visit_id"],
        ])
        delta = visit["vs_prior"]["delta"]
        passing = len(visit["vs_prior"]["newly_passing"])
        failing = len(visit["vs_prior"]["newly_failing"])
        still = visit["vs_prior"]["still_failing"]
        prior_id = visit["vs_prior"]["prior_visit_id"]
    payload = summary_payload(
        run_record["status"], run_id, html_url, run_record["environment"]["live_lab"],
        suites, parsed, run_record["risk"]["level"], run_record["risk"]["push_to_prod"],
        wrote, delta, passing, failing, still,
    )
    if delta:
        payload["prior_visit_id"] = prior_id
    emit(payload)


def main():
    parser = argparse.ArgumentParser(description="Run test.yml and write the testing records")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--workspace", required=True)
    run_parser.add_argument("--environment", default="dev")
    run_parser.add_argument("--suites", default="")
    run_parser.add_argument("--devices", default="")
    run_parser.add_argument("--tags", default="")
    run_parser.add_argument("--mode", default="live")
    run_parser.add_argument("--ref", default="main")
    run_parser.add_argument("--run-id", default="")
    run_parser.add_argument("--phase", default="")
    run_parser.add_argument("--allow-all", default="false")
    run_parser.add_argument("--production-authorized", default="false")
    run_parser.add_argument("--reason", default="adhoc")
    run_parser.add_argument("--max-wait", type=int, default=40)
    run_parser.add_argument("--poll", type=int, default=5)
    args = parser.parse_args()
    if args.command == "run":
        execute(args)


if __name__ == "__main__":
    main()
