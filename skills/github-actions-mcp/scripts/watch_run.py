#!/usr/bin/env python3
"""Watch one GitHub Actions run and write the operation record.

watch runs under execution_type mcp_orchestration. It lists the run for
the commit, checks that run once, and returns. A running result writes
nothing. The agent calls the same command again with --run-id.

  python3 <skill>/scripts/watch_run.py watch --workspace <file_explorer> \\
      --workflow apply.yml --ref dev --sha <sha>
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace-handoff" / "scripts"))

try:
    import visit_common  # noqa: E402
    import github_common  # noqa: E402
    from github_common import call_tool, flatten, parse_report, poll_run, read_logs, report_in  # noqa: E402
except ImportError:
    print(
        '{"error": "visit_common missing; attach the workspace-handoff skill"}',
        file=sys.stderr,
    )
    sys.exit(1)

SKILL = Path(__file__).resolve().parent.parent
RUN_SCHEMA = SKILL / "schemas" / "operation-run.schema.json"
WORKFLOWS = {"apply.yml", "test.yml"}
REFS = {"dev", "main"}
STATUS = {"pass": "ok", "fail": "failed", "unknown": "unknown"}


def emit(payload):
    print(json.dumps(payload, separators=(",", ":"), default=str))


def stamp_name(moment):
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


def checked_at(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def run_rows(body):
    found = []

    def walk(node):
        if isinstance(node, dict):
            parts = node.get("_parts")
            if isinstance(parts, list):
                for part in parts:
                    walk(part)
                return
            sha = node.get("sha") or node.get("head_sha") or node.get("headSha")
            run_id = node.get("id") if node.get("id") is not None else node.get("run_id")
            if sha and run_id is not None and not node.get("jobs_url"):
                found.append(node)
            for key in ("runs", "workflow_runs", "workflowRuns", "data"):
                if key in node:
                    walk(node[key])
            return
        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(flatten(body))
    return found


def sha_hit(row, sha):
    asked = (sha or "").strip().lower()
    if len(asked) < 7:
        return None
    for key in ("sha", "head_sha", "headSha"):
        value = str(row.get(key) or "").strip().lower()
        if value and (value == asked or value.startswith(asked) or asked.startswith(value)):
            return str(row.get(key) or row.get("sha") or row.get("head_sha") or "").strip()
    return None


def find_run_by_sha(workflow, ref, sha):
    """List up to three times. Same 5 second gap as dispatch_and_find. Never dispatches."""
    budget = visit_common.Budget(30)
    last = "no run for that sha"
    for attempt in range(3):
        if attempt:
            if budget.left() < 5:
                break
            time.sleep(5)
        body, err = call_tool(
            "github_list_action_runs",
            {"workflow": workflow, "branch": ref, "limit": 5},
        )
        if err:
            last = err
            continue
        matches = []
        for row in run_rows(body):
            full = sha_hit(row, sha)
            if full:
                matches.append((row, full))
        if not matches:
            last = "no run for that sha"
            continue
        ids = {str(row.get("id") or row.get("run_id")) for row, _full in matches}
        if len(ids) > 1:
            return None, None, None, "sha prefix matched more than one run"
        row, full = matches[0]
        run_id = str(row.get("id") or row.get("run_id"))
        url = row.get("html_url") or row.get("htmlUrl") or ""
        return run_id, url, full, None
    return None, None, None, last


def judge_live(parsed):
    if not parsed.get("live_present"):
        if not parsed.get("static_present"):
            return "unknown", "no network test report"
        return "unknown", "no live block"
    live = parsed.get("live_counts") or {}
    if int(live.get("fail") or 0) or int(live.get("error") or 0):
        return "fail", None
    return "pass", None


def marker_line(text, parsed):
    cleaned = github_common.clean_log(text or "")
    for block in github_common.report_blocks(cleaned):
        _banner, mode, _lab, _requested = github_common.header_bits(block)
        if mode != "live":
            continue
        for line in block.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped[:500]
    live = parsed.get("live_counts") or {}
    static = parsed.get("static_counts") or {}
    line = "live pass=%s fail=%s error=%s" % (
        live.get("pass", 0), live.get("fail", 0), live.get("error", 0),
    )
    if parsed.get("static_present"):
        line += " static fail=%s" % static.get("fail", 0)
    return line[:500]


def write_run(workspace, moment, result, ref, sha, workflow, run_id, html_url, marker):
    payload = {
        "schema": "operation-run/v1",
        "updated_at": checked_at(moment),
        "source_agent": "github-pipeline-monitor",
        "status": STATUS[result],
        "headline": (marker or result)[:240],
        "next_action": None,
        "operation": "workflow_watch",
        "git": {"ref": ref, "commit_sha": sha},
        "workflow": {
            "name": workflow,
            "run_id": str(run_id) if run_id else None,
            "html_url": html_url or None,
            "marker": marker,
        },
        "result": result,
        "keys": [],
    }
    visit_common.validate(payload, RUN_SCHEMA)
    path = Path(workspace) / "operational" / "runs" / ("%s.json" % stamp_name(moment))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return "operational/runs/%s" % path.name


def finish(result, workflow, ref, sha, run_id, html_url, marker, wrote, reason=None, phase=None, github_status=None):
    payload = {
        "result": result,
        "workflow": workflow,
        "ref": ref,
        "sha": sha,
        "run_id": run_id,
        "html_url": html_url or "",
        "marker": marker,
        "wrote": wrote,
    }
    if result == "running":
        payload = {
            "result": "running",
            "run_id": run_id,
            "html_url": html_url or "",
            "github_status": github_status or "unreadable",
        }
        if phase:
            payload["phase"] = phase
    elif reason and result == "unknown":
        payload["reason"] = reason
    emit(payload)


def execute(args):
    moment = datetime.now(timezone.utc)
    workflow = args.workflow
    ref = args.ref
    sha = (args.sha or "").strip()
    if workflow not in WORKFLOWS or ref not in REFS or not sha:
        reason = "workflow, ref, and sha are required"
        wrote = None
        try:
            wrote = write_run(args.workspace, moment, "unknown", ref or None, sha or None, workflow or None, None, None, None)
        except ValueError as exc:
            reason = str(exc)
        finish("unknown", workflow, ref, sha, None, "", None, wrote, reason=reason)
        return
    run_id = (args.run_id or "").strip()
    html_url = ""
    full = sha
    if not run_id:
        run_id, html_url, full, err = find_run_by_sha(workflow, ref, sha)
        if err or not run_id:
            wrote = write_run(args.workspace, moment, "unknown", ref, sha, workflow, None, None, None)
            finish("unknown", workflow, ref, sha, None, "", None, wrote, reason=err or "no run for that sha")
            return
    html_url, jobs, err, phase, status, run_body = poll_run(run_id, ref)
    if err == "running":
        finish("running", workflow, ref, full or sha, run_id, html_url, None, None, phase=phase, github_status=status)
        return
    if err:
        wrote = write_run(args.workspace, moment, "unknown", ref, full or sha, workflow, run_id, html_url, None)
        finish("unknown", workflow, ref, full or sha, run_id, html_url, None, wrote, reason=err)
        return
    text, log_err = read_logs(jobs, run_id, run_body)
    if log_err or not report_in(text):
        reason = log_err or "job log had no network test report"
        wrote = write_run(args.workspace, moment, "unknown", ref, full or sha, workflow, run_id, html_url, None)
        finish("unknown", workflow, ref, full or sha, run_id, html_url, None, wrote, reason=reason)
        return
    parsed = parse_report(text)
    result, reason = judge_live(parsed)
    marker = marker_line(text, parsed)
    wrote = write_run(args.workspace, moment, result, ref, full or sha, workflow, run_id, html_url, marker)
    finish(result, workflow, ref, full or sha, run_id, html_url, marker, wrote, reason=reason)


def main():
    parser = argparse.ArgumentParser(description="Watch apply.yml or test.yml once")
    sub = parser.add_subparsers(dest="command", required=True)
    watch = sub.add_parser("watch")
    watch.add_argument("--workspace", required=True)
    watch.add_argument("--workflow", required=True)
    watch.add_argument("--ref", required=True)
    watch.add_argument("--sha", default="")
    watch.add_argument("--run-id", default="")
    args = parser.parse_args()
    if args.command == "watch":
        execute(args)


if __name__ == "__main__":
    main()
