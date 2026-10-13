#!/usr/bin/env python3
"""Fold open recommendations from workspace state. No MCP.

assess runs under execution_type standard. It reads the testing visit,
active chart problems, and the network-sync watermark. The same
fingerprint writes nothing.

  python3 <skill>/scripts/recommend.py assess --workspace <file_explorer>
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace-handoff" / "scripts"))

try:
    import visit_common  # noqa: E402
except ImportError:
    print('{"error": "visit_common missing; attach the workspace-handoff skill"}', file=sys.stderr)
    sys.exit(1)

SKILL = Path(__file__).resolve().parent.parent
SCHEMA = SKILL / "schemas" / "recommendations.schema.json"
BOARD = "state/recommendations.json"


def emit(payload):
    print(json.dumps(payload, separators=(",", ":")))


def load(path):
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def device_of(key):
    if isinstance(key, str) and key.startswith("device:"):
        name = key.split(":", 1)[1].strip()
        if name and " " not in name:
            return name
    return None


def testing_rows(workspace, state):
    latest = state.get("latest") if isinstance(state, dict) else None
    if not isinstance(latest, str) or not latest:
        return [], None
    visit = load(Path(workspace) / latest)
    if not visit:
        return [], latest
    results = visit.get("results") if isinstance(visit.get("results"), dict) else {}
    grouped = {}
    for item in results.get("by_device") or []:
        if not isinstance(item, dict):
            continue
        device = item.get("device")
        if not isinstance(device, str) or not device.strip():
            continue
        for test in item.get("failing") or []:
            if isinstance(test, str) and test.strip():
                grouped.setdefault(test.strip(), []).append(device.strip())
    for row in results.get("ran") or []:
        if not isinstance(row, dict) or row.get("status") not in {"FAIL", "ERROR"}:
            continue
        device = row.get("device")
        check = row.get("check")
        if isinstance(device, str) and isinstance(check, str) and device.strip() and check.strip():
            grouped.setdefault(check.strip(), []).append(device.strip())
    rows = []
    for feature in sorted(grouped):
        devices = sorted(set(grouped[feature]))
        if devices:
            rows.append({
                "source": "testing",
                "feature": feature,
                "devices": devices,
                "peer": None,
                "problem_ref": None,
                "evidence_ref": latest,
            })
    return rows, latest


def health_rows(health):
    rows = []
    problems = health.get("problems") if isinstance(health, dict) else None
    if not isinstance(problems, list):
        return rows
    for problem in problems:
        if not isinstance(problem, dict) or problem.get("status") not in {"active", "watching"}:
            continue
        devices = []
        for key in problem.get("keys") or []:
            name = device_of(key)
            if name and name not in devices:
                devices.append(name)
        if not devices:
            continue
        problem_id = problem.get("id") if isinstance(problem.get("id"), str) else None
        rows.append({
            "source": "health",
            "feature": problem_id or "problem",
            "devices": devices,
            "peer": None,
            "problem_ref": problem_id,
            "evidence_ref": "state/health.json",
        })
    return rows


def sync_of(sync, prior_updated):
    completed = sync.get("completed_at") if isinstance(sync, dict) else None
    operation = sync.get("operation") if isinstance(sync, dict) else None
    if not isinstance(completed, str):
        completed = None
    if not isinstance(operation, str):
        operation = None
    newer = bool(completed) and (not prior_updated or completed > prior_updated)
    return {"completed_at": completed, "operation": operation, "newer": newer}


def fingerprint(sync, latest, rows):
    parts = [
        "sync:%s" % (sync.get("completed_at") or ""),
        "testing:%s" % (latest or ""),
    ]
    for row in rows:
        parts.append("%s:%s=%s" % (row["source"], row["feature"], ",".join(row["devices"])))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def keys_of(rows):
    found = []
    for row in rows:
        for device in row["devices"]:
            key = "device:%s" % device
            if key not in found:
                found.append(key)
        if row["source"] == "testing":
            key = "test:%s" % row["feature"]
            if " " not in row["feature"] and key not in found:
                found.append(key)
    return found


def assess(workspace):
    root = Path(workspace)
    testing = load(root / "state" / "testing.json")
    health = load(root / "state" / "health.json")
    sync = load(root / "state" / "network-sync.json")
    prior = load(root / BOARD)
    test_rows, latest = testing_rows(root, testing)
    rows = test_rows + health_rows(health)
    prior_updated = prior.get("updated_at") if isinstance(prior, dict) else None
    sync_row = sync_of(sync, prior_updated if isinstance(prior_updated, str) else None)
    digest = fingerprint(sync_row, latest, rows)
    if isinstance(prior, dict) and prior.get("fingerprint") == digest:
        emit({
            "result": "unchanged",
            "path": BOARD,
            "updated_at": prior.get("updated_at"),
            "rows": len(prior.get("rows") or []),
        })
        return
    moment = stamp()
    if not rows and not testing and not health:
        status = "unknown"
        headline = "No testing visit and no health chart to recommend from."
        action = None
    elif not rows:
        status = "ok"
        headline = "No failing checks and no active chart problems."
        action = None
    else:
        status = "ok"
        headline = "%d open recommendation%s." % (len(rows), "" if len(rows) == 1 else "s")
        if sync_row["newer"]:
            headline = headline[:-1] + ". Prod sync is newer than the last board."
        action = "Implement a row only when its exact line is known"
    payload = {
        "schema": "recommendations/v1",
        "updated_at": moment,
        "source_agent": "network-ops",
        "status": status,
        "headline": headline[:240],
        "next_action": action,
        "fingerprint": digest,
        "sync": sync_row,
        "rows": rows[:24],
        "keys": keys_of(rows[:24]),
    }
    visit_common.validate(payload, SCHEMA)
    path = root / BOARD
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    emit({
        "result": "wrote",
        "path": BOARD,
        "rows": len(payload["rows"]),
        "sync_newer": sync_row["newer"],
        "updated_at": moment,
    })


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    assess_parser = sub.add_parser("assess")
    assess_parser.add_argument("--workspace", required=True)
    args = parser.parse_args()
    if args.command == "assess":
        assess(args.workspace)


if __name__ == "__main__":
    main()
