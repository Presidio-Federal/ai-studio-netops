#!/usr/bin/env python3
"""Build state/compliance.json from the visits already on disk.

assess runs under execution_type standard. It does not call MCP. It
folds the intel and test series, scores the three planes, carries
findings, and writes the chart. Opinion fields are placeholders.

annotate replaces the opinion, the trend narrative, and the plan.
The agent does not rewrite the chart.

  python3 <skill>/scripts/assess_chart.py assess --workspace <file_explorer>
  python3 <skill>/scripts/assess_chart.py annotate --workspace <file_explorer> \\
      --opinion "..." --why "..." --plan "..."
"""
import argparse
import json
import sys
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

SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "compliance-state.schema.json"
KEY_RE_PREFIXES = ("device:", "interface:", "site:", "service:", "test:", "control:", "incident:", "change:")
TESTED_METHOD = "verified_tests / (verified_tests + failing_tests); SKIP and N/A excluded"
DEVICE_METHOD = "pass / (pass + fail + error) device-check rows; SKIP and N/A excluded"
FRAMEWORK_METHOD = "covered / (covered + partial + gap + unwired); not_applicable excluded"


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp_text(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value):
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


def load(ws, rel):
    path = Path(ws) / rel
    if not path.is_file():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), rel
    except json.JSONDecodeError:
        return None, rel


def pct(numerator, denominator):
    if not denominator:
        return None
    return round(100.0 * numerator / denominator, 1)


def typed_keys(keys):
    found = []
    for key in keys or []:
        if isinstance(key, str) and key.startswith(KEY_RE_PREFIXES) and " " not in key[key.find(":") + 1:] and key not in found:
            found.append(key)
    return found


def key_of(keys, prefix):
    for key in keys or []:
        if isinstance(key, str) and key.startswith(prefix):
            return key.split(":", 1)[1]
    return None


def chain_new(ws, folder, start, stop_id, require_environment=False):
    """Metrics newer than stop_id, oldest first. The stop stamp is not copied again."""
    points = []
    seen = set()
    current = start
    while current and current not in seen and current != stop_id and len(points) < 10:
        seen.add(current)
        doc, _rel = load(ws, "%s/%s.json" % (folder, current))
        if not doc:
            break
        metrics = doc.get("metrics")
        if not isinstance(metrics, dict) or not metrics.get("at") or not metrics.get("scope"):
            break
        if require_environment and "environment" not in metrics:
            break
        points.append(metrics)
        current = (doc.get("vs_prior") or {}).get("prior_visit_id")
    points.reverse()
    return points


def merge_points(prior_points, new_points):
    merged = []
    seen = set()
    for point in list(prior_points or []) + list(new_points or []):
        if not isinstance(point, dict) or not point.get("at") or not point.get("scope"):
            continue
        ident = point.get("visit_id") or (point.get("at"), point.get("scope"), point.get("environment"))
        if ident in seen:
            continue
        seen.add(ident)
        merged.append(point)
    merged.sort(key=lambda point: point.get("at") or "")
    return merged[-10:]


def freshness_of(checked_at, moment):
    observed = parse_time(checked_at)
    if observed is None:
        return {"state": "missing", "observed_at": None, "ttl_hours": 24}
    state = "stale" if moment >= observed + timedelta(hours=24) else "current"
    return {"state": state, "observed_at": stamp_text(observed), "ttl_hours": 24}


def group_rows(rows):
    by_test = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        test = key_of(row.get("keys"), "test:")
        if not test:
            continue
        by_test.setdefault(test, []).append(row)
    return by_test


def score_tests(by_test):
    verified = failing = skipped = na_only = 0
    for rows in by_test.values():
        statuses = [row.get("status") for row in rows]
        if any(status in {"FAIL", "ERROR"} for status in statuses):
            failing += 1
        elif any(status == "PASS" for status in statuses):
            verified += 1
        elif any(status == "SKIP" for status in statuses):
            skipped += 1
        else:
            na_only += 1
    return verified, failing, skipped, na_only


def device_counts(visit):
    counts = ((visit or {}).get("results") or {}).get("counts_ran") or {}
    if not isinstance(counts, dict) or not counts:
        return 0, 0
    passed = int(counts.get("pass") or 0)
    failing = int(counts.get("fail") or 0) + int(counts.get("error") or 0)
    return passed, failing


def framework_counts(coverage):
    counts = (coverage or {}).get("counts") or {}
    return {name: int(counts.get(name) or 0) for name in ("covered", "partial", "gap", "unwired", "not_applicable")}


def direction_of(test_delta, fw_current, fw_prior):
    plus = minus = False
    if test_delta == "better":
        plus = True
    elif test_delta == "worse":
        minus = True
    elif test_delta == "mixed":
        plus = minus = True
    if fw_current is not None and fw_prior is not None:
        if fw_current > fw_prior:
            plus = True
        elif fw_current < fw_prior:
            minus = True
    if test_delta == "first" and fw_prior is None:
        return "first"
    if plus and not minus:
        return "improving"
    if minus and not plus:
        return "worsening"
    if plus and minus:
        return "mixed"
    return "unchanged"


def prefix_for(direction):
    return {
        "improving": "Improving",
        "worsening": "Worsening",
        "mixed": "Mixed",
        "unchanged": "Unchanged",
        "first": "Baseline",
    }.get(direction, "Unchanged")


def finding_identity(finding):
    kind = finding.get("kind")
    keys = finding.get("keys") or []
    if kind == "test_failure":
        return ("test_failure", key_of(keys, "test:"))
    return (kind, key_of(keys, "control:"))


def row_keys_for_test(test, rows):
    keys = ["test:%s" % test]
    for row in rows:
        if row.get("status") in {"FAIL", "ERROR"}:
            for key in typed_keys(row.get("keys")):
                if key not in keys:
                    keys.append(key)
    return keys[:16]


def coverage_status(coverage, control):
    for row in (coverage or {}).get("rows") or []:
        if not isinstance(row, dict):
            continue
        if row.get("nist_id") == control or "control:%s" % control in (row.get("keys") or []):
            return row.get("status")
    return None


def build_findings(prior_findings, by_test, coverage, primary, intel_visit, moment, prior_analyzed):
    primary_at = (primary or {}).get("checked_at") or stamp_text(moment)
    intel_at = (intel_visit or {}).get("checked_at") or primary_at
    primary_ref = "compliance/testing/%s.json" % primary.get("visit_id") if primary and primary.get("visit_id") else "compliance/coverage.json"
    intel_ref = "compliance/intel/%s.json" % intel_visit.get("visit_id") if intel_visit and intel_visit.get("visit_id") else "compliance/coverage.json"
    carried = []
    seen = set()
    for old in prior_findings or []:
        if not isinstance(old, dict):
            continue
        identity = finding_identity(old)
        if not identity[1]:
            continue
        seen.add(identity)
        status = old.get("status") or "open"
        kind, name = identity
        item = dict(old)
        if kind == "test_failure":
            rows = by_test.get(name) or []
            failing = [row for row in rows if row.get("status") in {"FAIL", "ERROR"}]
            if failing:
                if status == "remediated":
                    item["status"] = "regressed"
                    item["resolved_at"] = None
                    item["next_owner"] = "Network Ops"
                item["keys"] = row_keys_for_test(name, rows)
                devices = sorted({row.get("device") for row in failing if row.get("device")})
                fixed = sorted({
                    item.get("device")
                    for item in ((primary or {}).get("vs_prior") or {}).get("newly_passing") or []
                    if isinstance(item, dict) and item.get("test") == name and item.get("device")
                })
                if fixed:
                    item["summary"] = "fixed on %s since %s; still failing on %s" % (
                        ", ".join(fixed),
                        ((primary or {}).get("vs_prior") or {}).get("prior_visit_id") or "the prior visit",
                        ", ".join(devices) or "a device",
                    )
                else:
                    item["summary"] = "%s still failing on %s" % (name, ", ".join(devices) or "a device")
                item["source_refs"] = [primary_ref]
            elif rows and all(row.get("status") == "PASS" for row in rows):
                item["status"] = "remediated"
                item["resolved_at"] = primary_at
                item["next_owner"] = "none"
                item["summary"] = "%s now passes" % name
                item["source_refs"] = [primary_ref]
            elif status == "remediated":
                resolved = parse_time(item.get("resolved_at"))
                if resolved and moment >= resolved + timedelta(days=7):
                    continue
        elif kind == "missing_control":
            state = coverage_status(coverage, name)
            if state == "covered":
                item["status"] = "remediated"
                item["resolved_at"] = intel_at
                item["next_owner"] = "none"
                item["summary"] = "%s is covered" % name
            elif status == "remediated" and state in {"gap", "partial", "unwired"}:
                item["status"] = "regressed"
                item["resolved_at"] = None
                item["next_owner"] = "operator"
                item["summary"] = "%s is %s again" % (name, state)
            elif status == "remediated":
                resolved = parse_time(item.get("resolved_at"))
                if resolved and moment >= resolved + timedelta(days=7):
                    continue
        if not item.get("first_seen"):
            item["first_seen"] = prior_analyzed or primary_at
        if item.get("status") != "remediated":
            item["resolved_at"] = None
        elif not item.get("resolved_at"):
            item["resolved_at"] = primary_at
        carried.append(item)
    for test, rows in by_test.items():
        if ("test_failure", test) in seen:
            continue
        if any(row.get("status") in {"FAIL", "ERROR"} for row in rows):
            devices = sorted({row.get("device") for row in rows if row.get("status") in {"FAIL", "ERROR"} and row.get("device")})
            carried.append({
                "kind": "test_failure",
                "status": "open",
                "severity": "high",
                "summary": "%s failing on %s" % (test, ", ".join(devices) or "a device"),
                "keys": row_keys_for_test(test, rows),
                "first_seen": primary_at,
                "resolved_at": None,
                "source_refs": [primary_ref],
                "next_owner": "Network Ops",
            })
        elif ("evidence_gap", test) not in seen and any(row.get("status") == "SKIP" for row in rows) and not any(row.get("status") == "PASS" for row in rows):
            carried.append({
                "kind": "evidence_gap",
                "status": "open",
                "severity": "medium",
                "summary": "%s did not run" % test,
                "keys": ["test:%s" % test][:16],
                "first_seen": primary_at,
                "resolved_at": None,
                "source_refs": [primary_ref],
                "next_owner": "Compliance Test",
            })
    for row in (coverage or {}).get("rows") or []:
        if not isinstance(row, dict) or row.get("status") not in {"gap", "unwired", "partial"}:
            continue
        control = row.get("nist_id") or key_of(row.get("keys"), "control:")
        if not control or ("missing_control", control) in seen:
            continue
        seen.add(("missing_control", control))
        keys = typed_keys(row.get("keys")) or ["control:%s" % control]
        carried.append({
            "kind": "missing_control",
            "status": "open",
            "severity": "medium",
            "summary": "%s is %s" % (control, row.get("status")),
            "keys": keys[:16],
            "first_seen": intel_at,
            "resolved_at": None,
            "source_refs": [intel_ref],
            "next_owner": "operator",
        })
    for candidate in (intel_visit or {}).get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        control = key_of(candidate.get("keys"), "control:")
        if not control or ("missing_control", control) in seen:
            continue
        if coverage_status(coverage, control) == "covered":
            continue
        seen.add(("missing_control", control))
        keys = typed_keys(candidate.get("keys")) or ["control:%s" % control]
        carried.append({
            "kind": "missing_control",
            "status": "open",
            "severity": "medium",
            "summary": "%s is an intelligence candidate" % control,
            "keys": keys[:16],
            "first_seen": intel_at,
            "resolved_at": None,
            "source_refs": [intel_ref],
            "next_owner": "operator",
        })
    rank = {"regressed": 0, "open": 1, "remediated": 2}
    carried.sort(key=lambda item: rank.get(item.get("status"), 9))
    return carried[:20]


def plan_for(findings, fresh_intel, fresh_test):
    if fresh_test.get("state") != "current":
        return "Compliance Test: run the compliance suite."
    if fresh_intel.get("state") != "current":
        return "Compliance Intelligence: run the scan."
    if any(item.get("status") in {"open", "regressed"} and item.get("kind") == "test_failure" for item in findings):
        return "Network Ops: review the failed checks."
    if any(item.get("status") in {"open", "regressed"} and item.get("kind") == "missing_control" for item in findings):
        return "Operator selects a missing control, then Compliance Author."
    return "none"


def status_of(fresh_intel, fresh_test, findings, fw, tested, dispatched):
    usable = fresh_intel.get("state") != "missing" or fresh_test.get("state") != "missing"
    if not usable:
        return "unknown"
    if fresh_intel.get("state") == "stale" or fresh_test.get("state") == "stale" or dispatched:
        return "stale_chart"
    if any(item.get("status") in {"open", "regressed"} and item.get("kind") == "test_failure" for item in findings):
        return "degraded"
    if tested["skipped_tests"] or fw["partial"] or fw["gap"] or fw["unwired"] or fresh_intel.get("state") == "missing" or fresh_test.get("state") == "missing":
        return "partial"
    return "ok"


def chart_status_testing(visit, tested):
    if not visit:
        return "unknown"
    if tested["failing_tests"]:
        return "degraded"
    if tested["skipped_tests"]:
        return "partial"
    if tested["denominator"] == 0:
        return "unknown"
    return "ok"


def build(ws, mode, dispatched_names):
    moment = now_utc()
    read = []
    meta_intel, rel = load(ws, "compliance/metadata-intel.json")
    if rel:
        read.append(rel)
    meta_test, rel = load(ws, "compliance/metadata-testing.json")
    if rel:
        read.append(rel)
    coverage, rel = load(ws, "compliance/coverage.json")
    if rel:
        read.append(rel)
    intel_state, rel = load(ws, "compliance/intel.json")
    if rel:
        read.append(rel)
    prior, rel = load(ws, "state/compliance.json")
    if rel:
        read.append(rel)

    intel_id = (meta_intel or {}).get("last_visit_id")
    intel_visit = None
    if intel_id:
        intel_visit, rel = load(ws, "compliance/intel/%s.json" % intel_id)
        if rel:
            read.append(rel)
    prior_series = (prior or {}).get("series") or {}
    prior_intel = prior_series.get("intel") or {}
    prior_intel_wm = prior_intel.get("watermark")
    intel_points = merge_points(
        prior_intel.get("points"),
        chain_new(ws, "compliance/intel", intel_id, prior_intel_wm, require_environment=False) if intel_id and intel_id != prior_intel_wm else [],
    )

    by_env = (meta_test or {}).get("last_visit_by_environment") or {}
    if not isinstance(by_env, dict):
        by_env = {}
    if not by_env and (meta_test or {}).get("last_visit_id"):
        only, _rel = load(ws, "compliance/testing/%s.json" % meta_test["last_visit_id"])
        lab = ((only or {}).get("environment") or {}).get("live_lab")
        if lab in {"dev", "prod"}:
            by_env = {lab: meta_test["last_visit_id"]}
    prior_testing = prior_series.get("testing") or {}
    prior_wms = prior_testing.get("watermarks")
    if not isinstance(prior_wms, dict):
        prior_wms = {"dev": None, "prod": None}
        legacy = prior_testing.get("watermark")
        if isinstance(legacy, str) and legacy:
            legacy_doc, _rel = load(ws, "compliance/testing/%s.json" % legacy)
            legacy_lab = ((legacy_doc or {}).get("metrics") or {}).get("environment")
            if legacy_lab in {"dev", "prod"}:
                prior_wms[legacy_lab] = legacy
    watermarks = {"dev": None, "prod": None}
    visits = {}
    new_test_points = []
    for lab in ("prod", "dev"):
        visit_id = by_env.get(lab)
        if not visit_id:
            continue
        head, rel = load(ws, "compliance/testing/%s.json" % visit_id)
        if rel:
            read.append(rel)
        if not head:
            continue
        visits[lab] = head
        watermarks[lab] = head.get("visit_id") or visit_id
        if visit_id != prior_wms.get(lab):
            new_test_points.extend(chain_new(ws, "compliance/testing", visit_id, prior_wms.get(lab), require_environment=True))
    test_points = merge_points(prior_testing.get("points"), new_test_points)

    primary_lab = "prod" if visits.get("prod") else ("dev" if visits.get("dev") else None)
    primary = visits.get(primary_lab) if primary_lab else None
    by_test = group_rows(((primary or {}).get("results") or {}).get("ran"))
    visit_metrics = (primary or {}).get("metrics") or {}
    if isinstance(visit_metrics.get("verified_tests"), int) and isinstance(visit_metrics.get("failing_tests"), int):
        verified = int(visit_metrics["verified_tests"])
        failing = int(visit_metrics["failing_tests"])
        skipped = int(visit_metrics.get("skipped_tests") or 0)
        na_only = int(visit_metrics.get("not_applicable") or 0)
        tested_percent = visit_metrics.get("tested_posture_pct")
        if tested_percent is None:
            tested_percent = pct(verified, verified + failing)
    else:
        verified, failing, skipped, _na_only = score_tests(by_test)
        tested_percent = pct(verified, verified + failing)
    passed, device_failing = device_counts(primary)
    device_percent = pct(passed, passed + device_failing)
    fw = framework_counts(coverage)
    fw_percent = pct(fw["covered"], fw["covered"] + fw["partial"] + fw["gap"] + fw["unwired"])

    prior_test_wm = prior_wms.get(primary_lab) if primary_lab else None
    nothing_new = bool(prior) and intel_id == prior_intel_wm and (not primary_lab or watermarks.get(primary_lab) == prior_test_wm)

    vs = (primary or {}).get("vs_prior") or {}
    test_delta = vs.get("delta") if vs.get("delta") in {"first", "unchanged", "worse", "better", "mixed"} else "first"
    prior_trend = (prior or {}).get("trend_analysis") or {}
    prior_scores = (prior or {}).get("scores") or {}
    if not prior:
        fw_prior = None
    elif intel_id != prior_intel_wm:
        fw_prior = ((prior_scores.get("framework_coverage") or {}).get("percent"))
    else:
        fw_prior = ((prior_trend.get("scores") or {}).get("framework_coverage") or {}).get("prior")
    delta = vs.get("metrics_delta")
    if isinstance(delta, dict) and tested_percent is not None and isinstance(delta.get("tested_posture_pct"), (int, float)):
        tested_prior = round(float(tested_percent) - float(delta["tested_posture_pct"]), 1)
    else:
        tested_prior = None
    if isinstance(delta, dict) and device_percent is not None and isinstance(delta.get("device_check_pass_pct"), (int, float)):
        device_prior = round(float(device_percent) - float(delta["device_check_pass_pct"]), 1)
    else:
        device_prior = None
    if nothing_new and prior_trend.get("direction"):
        direction = prior_trend.get("direction")
        flips = list(prior_trend.get("flips") or [])
        newly_passing = int(prior_trend.get("newly_passing") or 0)
        newly_failing = int(prior_trend.get("newly_failing") or 0)
        still_failing = int(prior_trend.get("still_failing") or 0)
        since = prior_trend.get("since_visit_id")
        trend_scores = prior_trend.get("scores") or {}
        tested_prior = ((trend_scores.get("tested_posture") or {}).get("prior"))
        device_prior = ((trend_scores.get("device_checks") or {}).get("prior"))
        fw_prior = ((trend_scores.get("framework_coverage") or {}).get("prior"))
    else:
        direction = direction_of(test_delta, fw_percent, fw_prior)
        newly_failing_items = [item for item in (vs.get("newly_failing") or []) if isinstance(item, dict)]
        newly_passing_items = [item for item in (vs.get("newly_passing") or []) if isinstance(item, dict)]
        flips = []
        at = (primary or {}).get("checked_at") or stamp_text(moment)
        for item, way in [(item, "worse") for item in newly_failing_items] + [(item, "better") for item in newly_passing_items]:
            keys = typed_keys(item.get("keys"))
            if not keys or not item.get("test") or not item.get("device"):
                continue
            if item.get("from") not in {"PASS", "FAIL", "ERROR"} or item.get("to") not in {"PASS", "FAIL", "ERROR"}:
                continue
            if primary_lab not in {"dev", "prod"}:
                continue
            flips.append({
                "environment": primary_lab,
                "test": item["test"],
                "device": item["device"],
                "from": item["from"],
                "to": item["to"],
                "direction": way,
                "at": at,
                "keys": keys[:16],
            })
        flips = flips[:20]
        newly_passing = len(newly_passing_items)
        newly_failing = len(newly_failing_items)
        still_failing = int(vs.get("still_failing") or 0)
        since = vs.get("prior_visit_id")

    findings = build_findings(
        (prior or {}).get("findings") or [],
        by_test,
        coverage,
        primary,
        intel_visit,
        moment,
        (prior or {}).get("analyzed_at"),
    )
    fresh_intel = freshness_of((intel_visit or {}).get("checked_at"), moment) if intel_visit else {"state": "missing", "observed_at": None, "ttl_hours": 24}
    fresh_test = freshness_of((primary or {}).get("checked_at"), moment) if primary else {"state": "missing", "observed_at": None, "ttl_hours": 24}
    dispatched = [{"plane": name, "agent": "Compliance Intelligence" if name == "intel" else "Compliance Test", "invoked_at": stamp_text(moment)} for name in dispatched_names if name in {"intel", "testing"}]
    status = status_of(
        fresh_intel,
        fresh_test,
        findings,
        fw,
        {"skipped_tests": skipped, "failing_tests": failing},
        dispatched,
    )
    plan = plan_for(findings, fresh_intel, fresh_test)
    opinion = "Pending assessment."
    if nothing_new:
        narrative = "No new evidence since %s." % (watermarks.get(primary_lab) or intel_id or "the prior chart")
    else:
        narrative = "%s in %s. +%d fixed, -%d regressed, %d still failing." % (
            prefix_for(direction), primary_lab or "no lab", newly_passing, newly_failing, still_failing
        )
    def shown(value):
        return "n/a" if value is None else ("%s%%" % value)

    objective = "Tested posture %s -> %s, device checks %s -> %s, framework coverage %s -> %s (%s)." % (
        shown(tested_prior),
        shown(tested_percent),
        shown(device_prior),
        shown(device_percent),
        shown(fw_prior),
        shown(fw_percent),
        primary_lab or "none",
    )
    lead = next((item["summary"] for item in findings if item.get("status") in {"open", "regressed"}), "")
    headline = "%s: %s%s" % (prefix_for(direction), objective, ("; " + lead) if lead else "")
    keys = []
    for finding in findings:
        for key in finding.get("keys") or []:
            if key not in keys:
                keys.append(key)

    def consult_testing():
        if not primary:
            return None
        return {
            "visit_id": primary.get("visit_id") or "unknown",
            "observed_at": primary.get("checked_at") or stamp_text(moment),
            "status": chart_status_testing(primary, {"failing_tests": failing, "skipped_tests": skipped, "denominator": verified + failing}),
            "trend": test_delta if test_delta in {"first", "unchanged", "worse", "better", "mixed"} else "unchanged",
            "trend_note": narrative,
            "impression": opinion,
            "evidence_for": [item["summary"] for item in findings if item["kind"] == "test_failure" and item["status"] != "remediated"][:8],
            "evidence_against": [item["summary"] for item in findings if item["status"] == "remediated"][:8],
            "source_ref": "compliance/testing/%s.json" % (primary.get("visit_id") or "unknown"),
        }

    def consult_intel():
        if not intel_visit:
            return None
        gap_n = fw["gap"] + fw["partial"] + fw["unwired"]
        return {
            "visit_id": intel_visit.get("visit_id") or intel_id,
            "observed_at": intel_visit.get("checked_at") or stamp_text(moment),
            "status": "partial" if gap_n else "ok",
            "trend": ((intel_visit.get("vs_prior") or {}).get("delta") if ((intel_visit.get("vs_prior") or {}).get("delta") in {"first", "unchanged", "worse", "better", "mixed"}) else "unchanged"),
            "trend_note": "Framework coverage %s%%." % (fw_percent if fw_percent is not None else "n/a"),
            "impression": opinion,
            "evidence_for": ["%d covered" % fw["covered"]][:8],
            "evidence_against": ["%d gap, %d partial, %d unwired" % (fw["gap"], fw["partial"], fw["unwired"])][:8],
            "source_ref": "compliance/intel/%s.json" % (intel_visit.get("visit_id") or intel_id),
        }

    chart = {
        "keys": keys,
        "schema": "compliance-state/v2",
        "updated_at": stamp_text(moment),
        "source_agent": "compliance",
        "status": status,
        "headline": headline[:500],
        "next_action": plan,
        "mode": mode,
        "analyzed_at": stamp_text(moment),
        "coverage": {
            "intel": "complete" if intel_visit else "unavailable",
            "testing": "complete" if primary and not skipped else ("partial" if primary else "unavailable"),
        },
        "freshness": {"intel": fresh_intel, "testing": fresh_test},
        "consults": {"intel": consult_intel(), "testing": consult_testing()},
        "series": {
            "intel": {"window": 10, "watermark": intel_id, "points": intel_points[-10:]},
            "testing": {"window": 10, "watermarks": watermarks, "points": test_points},
        },
        "scores": {
            "environment": primary_lab,
            "tested_posture": {
                "percent": tested_percent,
                "verified_tests": verified,
                "failing_tests": failing,
                "skipped_tests": skipped,
                "not_applicable_tests": na_only,
                "denominator": verified + failing,
                "method": TESTED_METHOD,
            },
            "device_checks": {
                "percent": device_percent,
                "passed": passed,
                "failing": device_failing,
                "denominator": passed + device_failing,
                "method": DEVICE_METHOD,
            },
            "framework_coverage": {
                "percent": fw_percent,
                "covered": fw["covered"],
                "partial": fw["partial"],
                "gap": fw["gap"],
                "unwired": fw["unwired"],
                "not_applicable": fw["not_applicable"],
                "denominator": fw["covered"] + fw["partial"] + fw["gap"] + fw["unwired"],
                "method": FRAMEWORK_METHOD,
            },
        },
        "findings": findings,
        "assessment": {
            "noncompliant": [item["summary"] for item in findings if item["kind"] == "test_failure" and item["status"] != "remediated"][:10],
            "compliant": [item["summary"] for item in findings if item["status"] == "remediated"][:10],
            "gaps": [item["summary"] for item in findings if item["kind"] in {"missing_control", "evidence_gap"} and item["status"] != "remediated"][:10],
            "contradictions": [],
            "opinion": opinion,
        },
        "trend_analysis": {
            "direction": direction,
            "environment": primary_lab,
            "since_visit_id": since,
            "scores": {
                "tested_posture": {"prior": tested_prior, "current": tested_percent},
                "device_checks": {"prior": device_prior, "current": device_percent},
                "framework_coverage": {"prior": fw_prior, "current": fw_percent},
            },
            "newly_passing": newly_passing,
            "newly_failing": newly_failing,
            "still_failing": still_failing,
            "flips": flips,
            "narrative": narrative,
        },
        "soap": {
            "subjective": "Chart from the latest intelligence and test visits.",
            "objective": objective,
            "assessment": opinion,
            "plan": plan,
        },
        "dispatched": dispatched,
        "read": read[:30],
    }
    summary = {
        "result": status,
        "mode": mode,
        "environment": primary_lab,
        "direction": direction,
        "tested": tested_percent,
        "tested_prior": tested_prior,
        "devices": device_percent,
        "devices_prior": device_prior,
        "coverage": fw_percent,
        "coverage_prior": fw_prior,
        "newly_passing": newly_passing,
        "newly_failing": newly_failing,
        "still_failing": still_failing,
        "open": sum(1 for item in findings if item["status"] == "open"),
        "regressed": sum(1 for item in findings if item["status"] == "regressed"),
        "remediated": sum(1 for item in findings if item["status"] == "remediated"),
        "freshness": {"intel": fresh_intel["state"], "testing": fresh_test["state"]},
        "plan": plan,
        "needs_opinion": True,
        "open_findings": [item["summary"] for item in findings if item.get("status") in {"open", "regressed"}][:5],
        "flips": ["%s %s on %s" % (flip["test"], flip["to"], flip["device"]) for flip in flips[:5]],
        "wrote": "state/compliance.json",
    }
    return chart, summary


def write_chart(ws, chart):
    visit_common.validate(chart, SCHEMA)
    path = Path(ws) / "state" / "compliance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chart, indent=2) + "\n", encoding="utf-8")


def cmd_assess(args):
    dispatched = [part.strip() for part in (args.dispatched or "").split(",") if part.strip()]
    chart, summary = build(args.workspace, args.mode, dispatched)
    try:
        write_chart(args.workspace, chart)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(visit_common.summary(summary))
    return 0


def cmd_annotate(args):
    path = Path(args.workspace) / "state" / "compliance.json"
    if not path.is_file():
        print("state/compliance.json not found", file=sys.stderr)
        return 1
    chart = json.loads(path.read_text(encoding="utf-8"))
    opinion = args.opinion.strip()
    why = args.why.strip()
    plan = args.plan.strip()
    direction = (chart.get("trend_analysis") or {}).get("direction") or "unchanged"
    headline = (args.headline or "").strip() or ("%s: %s" % (prefix_for(direction), opinion))
    chart["headline"] = headline[:500]
    chart["assessment"]["opinion"] = opinion
    chart["trend_analysis"]["narrative"] = why
    chart["soap"]["assessment"] = opinion
    chart["soap"]["plan"] = plan
    chart["next_action"] = plan
    for name in ("intel", "testing"):
        consult = (chart.get("consults") or {}).get(name)
        if isinstance(consult, dict):
            consult["impression"] = opinion
    try:
        visit_common.validate(chart, SCHEMA)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    path.write_text(json.dumps(chart, indent=2) + "\n", encoding="utf-8")
    print(visit_common.summary({"result": chart.get("status"), "annotated": True, "wrote": "state/compliance.json"}))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Build the compliance chart")
    sub = parser.add_subparsers(dest="command", required=True)
    assess = sub.add_parser("assess")
    assess.add_argument("--workspace", required=True)
    assess.add_argument("--mode", default="assess-now", choices=["assess-now", "refresh-then-assess"])
    assess.add_argument("--dispatched", default="")
    note = sub.add_parser("annotate")
    note.add_argument("--workspace", required=True)
    note.add_argument("--opinion", required=True)
    note.add_argument("--why", required=True)
    note.add_argument("--plan", required=True)
    note.add_argument("--headline", default="")
    args = parser.parse_args()
    if args.command == "assess":
        sys.exit(cmd_assess(args))
    if args.command == "annotate":
        sys.exit(cmd_annotate(args))


if __name__ == "__main__":
    main()
