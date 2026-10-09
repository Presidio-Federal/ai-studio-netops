#!/usr/bin/env python3
"""Apply change.prescription to inventory/configs on dev.

submit runs under execution_type mcp_orchestration. It lists, gets,
edits, and puts. The config body stays in this process. The agent
reads the last stdout line.

  python3 <skill>/scripts/submit_change.py submit --workspace <file_explorer>

--dry-run --fixture <file> edits that file in memory. No MCP and no write.
"""
import argparse
import difflib
import json
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
RUN_SCHEMA = (
    SKILL.parent / "github-actions-mcp" / "schemas" / "operation-run.schema.json"
)
CONFIG_DIR = "inventory/configs"
REF = "dev"
OPS = {"ensure_present", "ensure_absent", "replace"}


def emit(payload):
    print(json.dumps(payload, separators=(",", ":"), default=str))


def stamp_name(moment):
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


def checked_at(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None, "state file not found"
    except json.JSONDecodeError as exc:
        return None, "state JSON: %s" % exc
    if not isinstance(data, dict):
        return None, "state must be an object"
    return data, None


def prescription_of(state):
    change = state.get("change") if isinstance(state, dict) else None
    if not isinstance(change, dict):
        return None, "change missing"
    raw = change.get("prescription")
    if not isinstance(raw, dict):
        return None, "change.prescription missing"
    operation = raw.get("operation")
    if operation not in OPS:
        return None, "operation is not ensure_present, ensure_absent, or replace"
    targets = raw.get("targets")
    if (
        not isinstance(targets, list)
        or not targets
        or any(not isinstance(item, str) or not item.strip() for item in targets)
        or len(targets) != len(set(targets))
    ):
        return None, "targets must be unique hostnames"
    lines = raw.get("lines")
    old = raw.get("old_lines")
    if not isinstance(lines, list) or any(not isinstance(item, str) or "\n" in item or "\r" in item for item in lines):
        return None, "lines must be single config lines"
    if not isinstance(old, list) or any(not isinstance(item, str) or "\n" in item or "\r" in item for item in old):
        return None, "old_lines must be single config lines"
    if operation == "replace" and not old:
        return None, "replace requires old_lines"
    if not lines:
        return None, "lines required"
    scope = raw.get("scope")
    placement = raw.get("placement")
    if not isinstance(scope, str) or not scope.strip():
        return None, "scope required"
    if not isinstance(placement, str) or not placement.strip():
        return None, "placement required"
    return raw, None


def batch_open(state):
    pr = state.get("pr") if isinstance(state.get("pr"), dict) else {}
    release = state.get("release") if isinstance(state.get("release"), dict) else {}
    number = pr.get("number")
    return bool(number) and pr.get("merged") is not True and release.get("status") == "pending"


def newline_of(text):
    return "\r\n" if "\r\n" in text else "\n"


def split_text(text):
    newline = newline_of(text)
    trailing = text.endswith("\n")
    return text.splitlines(), newline, trailing


def join_text(parts, newline, trailing):
    body = newline.join(parts)
    if trailing and (body or parts):
        body += newline
    elif trailing and not parts:
        body = newline
    return body


def is_header(line):
    if line == "" or line.lstrip() != line:
        return False
    return line.strip() != "!"


def blocks(parts):
    found = []
    index = 0
    while index < len(parts):
        if is_header(parts[index]):
            end = index + 1
            while end < len(parts) and parts[end] != parts[end].lstrip():
                end += 1
            found.append((index, end))
            index = end
        else:
            index += 1
    return found


def scope_span(parts, scope):
    """Return (start, end) exclusive end, or an error. global uses (None, None)."""
    if scope == "global":
        return None, None, None
    matches = []
    for start, end in blocks(parts):
        header = parts[start]
        if header == scope:
            matches.append((start, end))
        elif scope == "line vty" and header.startswith("line vty"):
            matches.append((start, end))
    if not matches:
        return None, None, "scope not found"
    if len(matches) > 1:
        return None, None, "scope matched more than one block"
    return matches[0][0], matches[0][1], None


def in_scope(parts, scope, index, start, end):
    if scope == "global":
        return is_header(parts[index])
    return start <= index < end


def parse_placement(placement):
    if placement in {"end", "start"}:
        return placement, None, None
    for kind in ("after ", "before "):
        if placement.startswith(kind):
            anchor = placement[len(kind):]
            if not anchor:
                return None, None, "placement anchor is empty"
            return kind.strip(), anchor, None
    return None, None, "placement must be end, start, after <line>, or before <line>"


def anchor_index(parts, scope, start, end, anchor):
    hits = [
        index
        for index, line in enumerate(parts)
        if line == anchor and in_scope(parts, scope, index, start, end)
    ]
    if not hits:
        return None, "placement anchor not in scope"
    if len(hits) > 1:
        return None, "placement anchor matched more than one line"
    return hits[0], None


def insert_at(parts, scope, start, end, placement):
    kind, anchor, err = parse_placement(placement)
    if err:
        return None, err
    if kind == "start":
        if scope == "global":
            return 0, None
        return start + 1, None
    if kind == "end":
        if scope == "global":
            for index, line in enumerate(parts):
                if line == "end" and is_header(line):
                    return index, None
            return len(parts), None
        return end, None
    index, err = anchor_index(parts, scope, start, end, anchor)
    if err:
        return None, err
    if kind == "after":
        return index + 1, None
    return index, None


def apply_edit(text, raw):
    parts, newline, trailing = split_text(text)
    scope = raw["scope"].strip()
    start, end, err = scope_span(parts, scope)
    if err:
        return None, err
    operation = raw["operation"]
    lines = list(raw["lines"])
    if scope != "global":
        for line in lines:
            if line == line.lstrip():
                return None, "block line must keep its indent"
        if operation == "ensure_absent" and any(line == parts[start] for line in lines):
            return None, "refusing to delete the block header"
    else:
        for line in lines:
            if line != line.lstrip() or not line.strip():
                return None, "global line must be a column-0 command"

    if operation == "ensure_present":
        missing = []
        for line in lines:
            present = any(
                parts[index] == line and in_scope(parts, scope, index, start, end)
                for index in range(len(parts))
            )
            if not present and line not in missing:
                missing.append(line)
        if not missing:
            return text, None
        position, err = insert_at(parts, scope, start, end, raw["placement"].strip())
        if err:
            return None, err
        parts[position:position] = missing
        return join_text(parts, newline, trailing), None

    if operation == "ensure_absent":
        kept = []
        removed = False
        for index, line in enumerate(parts):
            if line in lines and in_scope(parts, scope, index, start, end):
                removed = True
                continue
            kept.append(line)
        if not removed:
            return text, None
        return join_text(kept, newline, trailing), None

    old = list(raw["old_lines"])
    region = range(len(parts)) if scope == "global" else range(start, end)
    hits = []
    region = list(region)
    for offset in range(len(region) - len(old) + 1):
        indexes = region[offset:offset + len(old)]
        if [parts[index] for index in indexes] == old:
            if scope == "global" and any(not is_header(parts[index]) for index in indexes):
                continue
            hits.append(indexes[0])
    if len(hits) > 1:
        return None, "old_lines matched more than once"
    if not hits:
        new_hits = []
        for offset in range(len(region) - len(lines) + 1):
            indexes = region[offset:offset + len(lines)]
            if [parts[index] for index in indexes] == lines:
                new_hits.append(indexes[0])
        if len(new_hits) == 1:
            return text, None
        return None, "old_lines not in scope"
    position = hits[0]
    parts[position:position + len(old)] = lines
    return join_text(parts, newline, trailing), None


def interface_of(device, scope):
    if not scope.startswith("interface "):
        return None
    name = scope.split(" ", 1)[1].strip()
    if not name or " " in name or "/" in device or " " in device:
        return None
    return "%s/%s" % (device, name)


def stem_of(entry):
    name = entry.get("name") or Path(str(entry.get("path") or "")).name
    return Path(str(name)).stem


def resolve_targets(entries, targets):
    files = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("type", "file") == "file" and entry.get("path")
    ]
    resolved = []
    for target in targets:
        matches = [entry for entry in files if stem_of(entry) == target]
        if not matches:
            return None, "no listed path for %s" % target
        if len(matches) > 1:
            return None, "more than one listed path for %s" % target
        resolved.append((target, matches[0]["path"]))
    return resolved, None


def unified(path, before, after):
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
        )
    )
    if len(diff) > 4000:
        return diff[:4000] + "\n... truncated\n"
    return diff


def write_run(workspace, moment, result, devices, files, interfaces, commit_sha, summary):
    status = {
        "submitted": "ok",
        "no_change": "no_change",
        "blocked": "blocked",
        "failed": "failed",
    }[result]
    keys = []
    for device in devices:
        key = "device:%s" % device
        if key not in keys:
            keys.append(key)
    for interface in interfaces:
        key = "interface:%s" % interface
        if key not in keys:
            keys.append(key)
    payload = {
        "schema": "operation-run/v1",
        "updated_at": checked_at(moment),
        "source_agent": "github-gitops-change",
        "status": status,
        "headline": summary[:240] or result,
        "next_action": None,
        "operation": "config_change",
        "git": {"ref": REF, "commit_sha": commit_sha},
        "workflow": {"name": None, "run_id": None, "html_url": None, "marker": None},
        "result": result,
        "devices": devices,
        "files": files,
        "interfaces": interfaces,
        "summary": summary[:1000],
        "keys": keys,
    }
    visit_common.validate(payload, RUN_SCHEMA)
    path = Path(workspace) / "operational" / "runs" / ("%s.json" % stamp_name(moment))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return "operational/runs/%s" % path.name


def finish(started, result, devices, files, interfaces, commit_sha, wrote, batch, reason=None, diff=None):
    payload = {
        "result": result,
        "commit_sha": commit_sha,
        "devices": devices,
        "files": files,
        "interfaces": interfaces,
        "wrote": wrote,
        "batch": batch,
        "elapsed_s": round(time.monotonic() - started, 3),
    }
    if reason:
        payload["reason"] = reason
    if diff is not None:
        payload["dry_run"] = True
        payload["diff"] = diff
    emit(payload)


def call(tool, args):
    body, err = visit_common.unwrap_github(visit_common.mcp_call(tool, args, retries=1))
    return body, err


def live_done(args, moment, started, result, devices, files, interfaces, commit_sha, batch, reason=None):
    summary = reason or result
    wrote = None
    try:
        wrote = write_run(
            args.workspace, moment, result, devices, files, interfaces, commit_sha, summary
        )
    except ValueError as exc:
        reason = "%s; %s" % (reason, exc) if reason else str(exc)
        result = "failed"
    show = reason if result in {"blocked", "failed"} else None
    return finish(
        started, result, devices, files, interfaces, commit_sha, wrote, batch, reason=show
    )


def live(args, state, raw, batch, started, moment):
    listed, err = call("github_list_files", {"path": CONFIG_DIR, "ref": REF})
    if err:
        return live_done(args, moment, started, "failed", [], [], [], None, batch, reason=err)
    entries = listed.get("entries") if isinstance(listed, dict) else None
    if not isinstance(entries, list):
        return live_done(args, moment, started, "failed", [], [], [], None, batch, reason="entries not a list")
    resolved, err = resolve_targets(entries, raw["targets"])
    if err:
        return live_done(args, moment, started, "blocked", list(raw["targets"]), [], [], None, batch, reason=err)
    fetched = []
    for device, path in resolved:
        body, err = call("github_get_file", {"path": path, "ref": REF})
        if err:
            return live_done(args, moment, started, "blocked", list(raw["targets"]), [], [], None, batch, reason=err)
        content = body.get("content") if isinstance(body, dict) else None
        sha = body.get("sha") if isinstance(body, dict) else None
        if not isinstance(content, str) or not isinstance(sha, str) or not sha:
            return live_done(
                args, moment, started, "failed", list(raw["targets"]), [], [], None, batch,
                reason="get file had no content or sha",
            )
        edited, edit_err = apply_edit(content, raw)
        if edit_err:
            return live_done(args, moment, started, "blocked", list(raw["targets"]), [], [], None, batch, reason=edit_err)
        fetched.append((device, path, sha, content, edited))
    changed = [item for item in fetched if item[3] != item[4]]
    devices = [item[0] for item in changed]
    files = [item[1] for item in changed]
    interfaces = []
    for device, _path, _sha, _before, _after in changed:
        interface = interface_of(device, raw["scope"].strip())
        if interface:
            interfaces.append(interface)
    if not changed:
        return live_done(
            args, moment, started, "no_change", [], [], [], None, batch,
            reason="no_change %s" % raw["scope"].strip(),
        )
    message = "%s %s on %s" % (raw["operation"], raw["scope"].strip(), ", ".join(devices))
    message = message[:120]
    commit_sha = None
    for device, path, sha, _before, edited in changed:
        body, err = call(
            "github_put_file",
            {"path": path, "content": edited, "message": message, "ref": REF, "sha": sha},
        )
        if err:
            return live_done(args, moment, started, "failed", devices, files, interfaces, commit_sha, batch, reason=err)
        commit_sha = body.get("commit_sha") if isinstance(body, dict) else None
        if not isinstance(commit_sha, str) or not commit_sha:
            return live_done(
                args, moment, started, "failed", devices, files, interfaces, None, batch,
                reason="put file had no commit_sha",
            )
    return live_done(
        args, moment, started, "submitted", devices, files, interfaces, commit_sha, batch,
        reason="submitted %s" % message,
    )


def dry(args, raw, batch, started):
    if len(raw["targets"]) != 1:
        return finish(started, "blocked", list(raw["targets"]), [], [], None, None, batch, reason="dry-run fixture is one target", diff="")
    try:
        text = Path(args.fixture).read_text(encoding="utf-8")
    except OSError as exc:
        return finish(started, "failed", list(raw["targets"]), [], [], None, None, batch, reason=str(exc), diff="")
    edited, err = apply_edit(text, raw)
    device = raw["targets"][0]
    if err:
        return finish(started, "blocked", [device], [], [], None, None, batch, reason=err, diff="")
    interface = interface_of(device, raw["scope"].strip())
    interfaces = [interface] if interface and edited != text else []
    if edited == text:
        return finish(started, "no_change", [device], [], [], None, None, batch, diff="")
    label = Path(args.fixture).name
    return finish(
        started,
        "submitted",
        [device],
        [label],
        interfaces,
        None,
        None,
        batch,
        diff=unified(label, text, edited),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--state", default="state/network-ops.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fixture")
    args = parser.parse_args()
    started = time.monotonic()
    moment = datetime.now(timezone.utc)
    if args.command != "submit":
        emit({"result": "failed", "reason": "command must be submit"})
        return
    if args.dry_run and not args.fixture:
        emit({"result": "failed", "reason": "dry-run requires --fixture"})
        return
    if args.fixture and not args.dry_run:
        emit({"result": "failed", "reason": "--fixture is only valid with --dry-run"})
        return
    state_path = Path(args.state)
    if not state_path.is_absolute():
        state_path = Path(args.workspace) / args.state
    state, err = load_state(state_path)
    if err:
        emit({"result": "blocked", "reason": err})
        return
    raw, err = prescription_of(state)
    if err:
        emit({"result": "blocked", "reason": err})
        return
    batch = batch_open(state)
    if args.dry_run:
        dry(args, raw, batch, started)
        return
    live(args, state, raw, batch, started, moment)


if __name__ == "__main__":
    main()
