#!/usr/bin/env python3
"""Merge estate identity already on disk. No MCP.

assess runs under execution_type standard. It groups SoT and Sync
inventory by product id, copies Lifecycle research through, ranks
confidence, and writes state/lifecycle.json. Opinion fields stay
placeholders until annotate.

annotate sets the verdict, the operator's answers, a named SKU, the
open asks, and the plan lists. It does not recompute confidence,
coverage, or list-price totals.

  python3 <skill>/scripts/assess_estate.py assess --workspace <file_explorer> --mode estate
  python3 <skill>/scripts/assess_estate.py annotate --workspace <file_explorer> \\
      --headline "..." --understood "..." --opinion "..." --plan-opinion "..."
"""
import argparse
import json
import re
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

SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "lifecycle-estate.schema.json"
ASSET_SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "inventory-assets.schema.json"
RANK = {"low": 1, "medium": 2, "high": 3}
SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")
TASK = "Run the Modernization Lifecycle check only."
PENDING = "Pending verdict."


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


def load_json(path):
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def resolve_workspace(given):
    raw = Path(given)
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
        if resolved in seen or not resolved.is_dir():
            continue
        seen.append(resolved)
        if (resolved / "state").is_dir() or (resolved / "inventory").is_dir():
            print(f"estate workspace={resolved}", file=sys.stderr)
            return resolved
    print('{"error": "workspace directory missing"}', file=sys.stderr)
    return None


def safe_pid(pid):
    return SAFE_RE.sub("_", pid).strip("._") or "pid"


def device_keys(items):
    keys = []
    for row in items:
        for name in row.get("devices") or []:
            if not isinstance(name, str):
                continue
            text = name.strip()
            if not text or " " in text:
                continue
            key = f"device:{text}"
            if key not in keys:
                keys.append(key)
    return keys


def add_unique(bucket, value):
    if isinstance(value, str) and value.strip() and value.strip() not in bucket:
        bucket.append(value.strip())


def blank_row(pid, pid_source, source, moment):
    return {
        "pid": pid,
        "pid_source": pid_source,
        "quantity": 0,
        "devices": [],
        "roles": [],
        "platforms": [],
        "software_versions": [],
        "sample_device": None,
        "summary": "Pending verdict.",
        "source": source,
        "recommended_replacement": None,
        "selected_replacement": None,
        "selected_replacement_source": None,
        "replacement_family": None,
        "replacement_candidates": [],
        "replacement_ask": None,
        "recommended_software": None,
        "list_cost_per_unit": None,
        "total_list_cost": None,
        "currency": None,
        "end_of_sale": None,
        "end_of_support": None,
        "end_of_software_support": None,
        "end_of_security_vuln_support": None,
        "vulnerabilities": [],
        "psirts": [],
        "detail_ref": f"inventory/assets/{safe_pid(pid)}.json",
        "updated_at": stamp_text(moment),
        "expires_at": None,
        "research": {
            "eox": "missing",
            "software": "skipped",
            "psirt": "missing",
            "ccw": "skipped",
            "nvd": "skipped",
        },
    }


def finish_row(row):
    names = [name for name in row.get("devices") or [] if isinstance(name, str) and name.strip()]
    row["devices"] = names
    row["quantity"] = len(names)
    row["sample_device"] = names[0] if names else None
    versions = row.get("software_versions") or []
    research = row.setdefault("research", {})
    if not versions and research.get("software") == "missing":
        research["software"] = "skipped"
    if versions and research.get("software") == "skipped":
        research["software"] = "missing"
    if names:
        row["summary"] = f"{len(names)} devices, product id {row.get('pid')}."
    row["detail_ref"] = f"inventory/assets/{safe_pid(row.get('pid') or 'pid')}.json"
    return row


ASSET_SOURCE = {"kind": "asset", "reliability": "high", "ref": "inventory/assets/devices.json"}
DEVICES_PATH = Path("inventory") / "assets" / "devices.json"


def prod_rows(prod):
    rows = []
    if not isinstance(prod, dict):
        return rows
    for device in prod.get("devices") or []:
        if not isinstance(device, dict) or not isinstance(device.get("name"), str):
            continue
        name = device["name"].strip()
        if not name or " " in name:
            continue
        meta = device.get("source_metadata") if isinstance(device.get("source_metadata"), dict) else {}
        node = meta.get("node_definition")
        node = node.strip() if isinstance(node, str) and node.strip() else None
        rows.append({"name": name, "node_definition": node, "role": device.get("role"), "platform": device.get("platform")})
    return rows


def keep_text(value):
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def sync_assets(ws, moment):
    """Seed inventory/assets/devices.json from prod.json. Copy product_id and serial through."""
    prod = load_json(ws / "inventory" / "prod.json")
    if not isinstance(prod, dict):
        return None
    prior = load_json(ws / DEVICES_PATH)
    if prior is None:
        prior = load_json(ws / "inventory" / "assets.json")
    kept = {}
    if isinstance(prior, dict):
        for row in prior.get("devices") or []:
            if isinstance(row, dict) and isinstance(row.get("name"), str):
                kept[row["name"]] = row
    devices = []
    for incoming in prod_rows(prod):
        old = kept.get(incoming["name"]) or {}
        devices.append({
            "name": incoming["name"],
            "node_definition": incoming["node_definition"],
            "serial": keep_text(old.get("serial")),
            "product_id": keep_text(old.get("product_id")),
        })
    doc = {
        "schema": "inventory-assets/v1",
        "keys": [f"device:{row['name']}" for row in devices],
        "updated_at": stamp_text(moment),
        "source_agent": "modernization-analysis",
        "devices": devices,
    }
    path = ws / DEVICES_PATH
    visit_common.validate(doc, ASSET_SCHEMA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def stamped_map(assets):
    found = {}
    if not isinstance(assets, dict):
        return found
    for row in assets.get("devices") or []:
        if not isinstance(row, dict):
            continue
        pid = keep_text(row.get("product_id"))
        name = row.get("name")
        if pid and isinstance(name, str):
            found[name] = pid
    return found


def group_add(groups, pid, pid_source, source, hostname, role, platform, version):
    row = groups.get(pid)
    if row is None:
        row = {
            "pid": pid,
            "pid_source": pid_source,
            "source": source,
            "devices": [],
            "roles": [],
            "platforms": [],
            "software_versions": [],
        }
        groups[pid] = row
    elif RANK[source["reliability"]] > RANK[row["source"]["reliability"]]:
        row["source"] = source
        row["pid_source"] = pid_source
    add_unique(row["devices"], hostname)
    add_unique(row["roles"], role)
    add_unique(row["platforms"], platform)
    add_unique(row["software_versions"], version)


def evidence_groups(ws, verbal, upload, assets):
    groups = {}
    stamped = stamped_map(assets)
    sot = load_json(ws / "inventory" / "infra-sot.json")
    prod = load_json(ws / "inventory" / "prod.json")
    sot_names = set()
    if isinstance(sot, dict):
        for device in sot.get("devices") or []:
            if not isinstance(device, dict) or not isinstance(device.get("name"), str):
                continue
            name = device["name"]
            pid = device.get("device_type")
            if not isinstance(pid, str) or not pid.strip():
                pid = None
            sot_names.add(name)
            if name in stamped:
                group_add(groups, stamped[name], "asset", ASSET_SOURCE, name, device.get("role"), pid, device.get("software_version"))
                continue
            if pid is None:
                continue
            group_add(
                groups,
                pid.strip(),
                "netbox",
                {"kind": "cmdb", "reliability": "medium", "ref": "inventory/infra-sot.json"},
                name,
                device.get("role"),
                pid.strip(),
                device.get("software_version"),
            )
    if isinstance(prod, dict):
        for incoming in prod_rows(prod):
            name = incoming["name"]
            if name in stamped:
                group_add(groups, stamped[name], "asset", ASSET_SOURCE, name, incoming.get("role"), incoming.get("node_definition"), None)
                continue
            if name in sot_names:
                continue
            pid = incoming.get("node_definition")
            if not pid:
                continue
            group_add(
                groups,
                pid,
                "device_type",
                {"kind": "inventory", "reliability": "medium", "ref": "inventory/prod.json"},
                name,
                incoming.get("role"),
                incoming.get("platform"),
                None,
            )
    for kind, rows in (("verbal", verbal), ("upload", upload)):
        for hostname, pid in rows:
            group_add(
                groups,
                pid,
                kind,
                {"kind": kind, "reliability": "low", "ref": "operator"},
                hostname,
                None,
                None,
                None,
            )
    kinds = set()
    if isinstance(sot, dict):
        kinds.add("cmdb")
    if isinstance(prod, dict):
        kinds.add("inventory")
    if verbal:
        kinds.add("verbal")
    if upload:
        kinds.add("upload")
    return groups, kinds


def row_stale(row, now, stamped=None):
    if stamped is not None and row.get("pid") not in stamped:
        return False
    research = row.get("research") if isinstance(row.get("research"), dict) else {}
    if research.get("eox") == "missing":
        return True
    exp = parse_time(row.get("expires_at"))
    if exp is not None and now >= exp:
        return True
    versions = row.get("software_versions") or []
    if versions and research.get("software") == "missing":
        return True
    if row.get("selected_replacement") and not row.get("list_cost_per_unit") and research.get("ccw") != "unavailable":
        return True
    return False


def confidence(items, now, stamped=None):
    if not items:
        return "unknown", "unknown"
    ranks = [RANK.get((row.get("source") or {}).get("reliability"), 0) for row in items]
    worst = min(ranks) if ranks else 0
    identity = {1: "low", 2: "medium", 3: "high"}.get(worst, "unknown")
    if any(row_stale(row, now, stamped) for row in items):
        return identity, "stale"
    if all((row.get("research") or {}).get("eox") in {None, "missing"} for row in items):
        return identity, "unknown"
    filled = 0
    for row in items:
        research = row.get("research") or {}
        if research.get("eox") in {"complete", "unavailable"} and research.get("psirt") in {"complete", "unavailable"}:
            filled += 1
    if filled == len(items):
        return identity, "high"
    if filled:
        return identity, "medium"
    return identity, "low"


def estate_status(items, guidance, now, stamped=None):
    if not items:
        return "unknown"
    if any(row_stale(row, now, stamped) for row in items):
        return "stale"
    if guidance.get("objectives_status") != "stated":
        return "partial"
    return "ok"


def roll_cost(items):
    priced = 0
    unpriced = 0
    total = 0.0
    currency = None
    any_price = False
    for row in items:
        qty = int(row.get("quantity") or 0)
        unit = row.get("list_cost_per_unit")
        if unit in (None, ""):
            unpriced += qty
            continue
        try:
            amount = float(unit)
        except (TypeError, ValueError):
            unpriced += qty
            continue
        any_price = True
        priced += qty
        total += amount * qty
        if row.get("currency"):
            currency = row.get("currency")
    return {
        "currency": currency if any_price else None,
        "list_total": f"{total:.2f}" if any_price else None,
        "priced_qty": priced,
        "unpriced_qty": unpriced,
        "notes": "Rolled from list prices already on the rows." if any_price else "No CCW prices on disk.",
    }


def locked_hosts(items):
    locked = set()
    for row in items:
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        if source.get("reliability") == "high" and source.get("kind") != "asset":
            locked.update(name for name in (row.get("devices") or []) if isinstance(name, str))
    return locked


def merge(existing, groups, kinds, moment):
    items = [row for row in (existing.get("items") or []) if isinstance(row, dict) and row.get("pid")]
    asset_home = {}
    for pid, group in groups.items():
        if group.get("pid_source") == "asset":
            for name in group["devices"]:
                asset_home[name] = pid
    for row in items:
        row["devices"] = [
            name for name in (row.get("devices") or [])
            if asset_home.get(name, row.get("pid")) == row.get("pid")
        ]
    by_pid = {row["pid"]: row for row in items}
    locked = locked_hosts(items)
    evidence_hosts = set()
    for group in groups.values():
        evidence_hosts.update(group["devices"])
    for pid, group in groups.items():
        hosts = [name for name in group["devices"] if name not in locked or pid in by_pid and name in (by_pid[pid].get("devices") or [])]
        if pid in by_pid:
            row = by_pid[pid]
            source = row.get("source") if isinstance(row.get("source"), dict) else {}
            if source.get("reliability") != "high" or group.get("pid_source") == "asset":
                for name in hosts:
                    add_unique(row["devices"], name)
                for role in group["roles"]:
                    add_unique(row["roles"], role)
                for platform in group["platforms"]:
                    add_unique(row["platforms"], platform)
                if group.get("pid_source") == "asset" or RANK[group["source"]["reliability"]] > RANK.get(source.get("reliability"), 0):
                    row["source"] = group["source"]
                    row["pid_source"] = group["pid_source"]
            for version in group["software_versions"]:
                add_unique(row.setdefault("software_versions", []), version)
            finish_row(row)
            continue
        if not hosts and all(name in locked for name in group["devices"]):
            continue
        row = blank_row(pid, group["pid_source"], group["source"], moment)
        row["devices"] = [name for name in group["devices"] if name not in locked]
        row["roles"] = list(group["roles"])
        row["platforms"] = list(group["platforms"])
        row["software_versions"] = list(group["software_versions"])
        if not row["devices"]:
            continue
        items.append(finish_row(row))
        by_pid[pid] = row
    for row in items:
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        if source.get("reliability") == "high":
            continue
        if source.get("kind") not in kinds:
            continue
        kept = [name for name in (row.get("devices") or []) if name in evidence_hosts or name in locked]
        row["devices"] = kept
        finish_row(row)
    kept = [row for row in items if row.get("devices")]
    for row in kept:
        row["detail_ref"] = f"inventory/assets/{safe_pid(row.get('pid') or 'pid')}.json"
    return kept


def shell(moment):
    return {
        "schema": "lifecycle-estate/v2",
        "keys": [],
        "updated_at": stamp_text(moment),
        "source_agent": "modernization-analysis",
        "status": "unknown",
        "headline": PENDING,
        "next_action": None,
        "dispatched": [],
        "coverage": {"item_count": 0, "with_eox": 0, "with_psirt": 0, "with_cost": 0, "with_software": 0},
        "recommendations": [],
        "guidance": {
            "updated_at": stamp_text(moment),
            "identity_confidence": "unknown",
            "research_confidence": "unknown",
            "objectives_status": "missing",
            "understood": "",
            "answers": "",
            "open_asks": [],
        },
        "assessment": {"must_move": [], "can_wait": [], "contradictions": [], "opinion": PENDING},
        "plan": {
            "status": "none",
            "cost": {"currency": None, "list_total": None, "priced_qty": 0, "unpriced_qty": 0, "notes": "No CCW prices on disk."},
            "timeline": [],
            "opinion": PENDING,
        },
        "roadmap_ref": None,
        "items": [],
    }


def coverage_of(items):
    return {
        "item_count": len(items),
        "with_eox": sum(1 for row in items if row.get("end_of_support")),
        "with_psirt": sum(1 for row in items if row.get("psirts")),
        "with_cost": sum(1 for row in items if row.get("list_cost_per_unit")),
        "with_software": sum(1 for row in items if row.get("recommended_software") or row.get("end_of_software_support")),
    }


def parse_pairs(values, label):
    pairs = []
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"{label} must be <hostname>=<pid>")
        host, pid = item.split("=", 1)
        host = host.strip()
        pid = pid.strip()
        if not host or not pid or " " in host:
            raise ValueError(f"{label} needs a hostname and a product id")
        pairs.append((host, pid))
    return pairs


def write_estate(path, estate):
    visit_common.validate(estate, SCHEMA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(estate, indent=2) + "\n", encoding="utf-8")


def cmd_assess(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    try:
        verbal = parse_pairs(args.verbal, "--verbal")
        upload = parse_pairs(args.upload, "--upload")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    moment = now_utc()
    path = ws / "state" / "lifecycle.json"
    existing = load_json(path)
    estate = existing if isinstance(existing, dict) else shell(moment)
    for key, value in shell(moment).items():
        estate.setdefault(key, value)
    assets = sync_assets(ws, moment)
    groups, kinds = evidence_groups(ws, verbal, upload, assets)
    if assets is not None:
        kinds.add("asset")
    estate["items"] = merge(estate, groups, kinds, moment)
    items = estate["items"]
    stamped = set(stamped_map(assets).values())
    guidance = estate.setdefault("guidance", shell(moment)["guidance"])
    identity, research = confidence(items, moment, stamped)
    guidance["identity_confidence"] = identity
    guidance["research_confidence"] = research
    guidance["updated_at"] = stamp_text(moment)
    guidance.setdefault("objectives_status", "missing")
    guidance.setdefault("understood", "")
    guidance.setdefault("answers", "")
    guidance.setdefault("open_asks", [])
    estate["status"] = estate_status(items, guidance, moment, stamped)
    assessment = estate.setdefault("assessment", shell(moment)["assessment"])
    assessment.setdefault("must_move", [])
    assessment.setdefault("can_wait", [])
    assessment.setdefault("contradictions", [])
    if not assessment.get("opinion"):
        assessment["opinion"] = PENDING
    plan = estate.setdefault("plan", shell(moment)["plan"])
    plan["cost"] = roll_cost(items)
    plan.setdefault("timeline", [])
    if not plan.get("opinion"):
        plan["opinion"] = PENDING
    if args.mode == "plan" and guidance.get("objectives_status") == "missing":
        plan["status"] = "asking"
    elif args.mode == "estate" and plan.get("status") == "asking":
        plan["status"] = "none"
    elif not plan.get("status"):
        plan["status"] = "none"
    asking = args.mode == "plan" and (
        guidance.get("objectives_status") != "stated"
        or any(row.get("replacement_ask") and not row.get("selected_replacement") for row in items)
    )
    if asking:
        plan["status"] = "asking"
    estate["coverage"] = coverage_of(items)
    estate["keys"] = device_keys(items)
    estate["updated_at"] = stamp_text(moment)
    estate["source_agent"] = "modernization-analysis"
    estate["dispatched"] = []
    if not estate.get("headline"):
        estate["headline"] = PENDING
    if estate.get("roadmap_ref") == "lifecycle/roadmap.md":
        estate["roadmap_ref"] = "inventory/assets/roadmap.md"
    if "goals" in estate and not isinstance(estate.get("goals"), list):
        estate.pop("goals", None)
    try:
        write_estate(path, estate)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    needs = any(row_stale(row, moment, stamped) for row in items)
    unstamped = []
    if isinstance(assets, dict):
        unstamped = [row.get("name") for row in assets.get("devices") or [] if not keep_text(row.get("product_id"))]
    needs_opinion = ["understood", "assessment.opinion", "plan.opinion"]
    if asking:
        needs_opinion.append("open_asks")
    print(visit_common.summary({
        "result": estate["status"],
        "wrote": ["state/lifecycle.json", "inventory/assets/devices.json"] if assets else ["state/lifecycle.json"],
        "mode": args.mode,
        "item_count": len(items),
        "identity_confidence": identity,
        "research_confidence": research,
        "objectives_status": guidance.get("objectives_status"),
        "needs_lifecycle": needs,
        "task": TASK if needs else None,
        "needs_opinion": needs_opinion,
        "open_asks": list(guidance.get("open_asks") or []),
        "unpriced": [row.get("pid") for row in items if row.get("selected_replacement") and not row.get("list_cost_per_unit")],
        "pids": [row.get("pid") for row in items],
        "stamped_pids": sorted(stamped),
        "unstamped_count": len(unstamped),
        "unstamped": unstamped[:12],
    }))
    return 0


def parse_stage(text):
    fields = {"order": None, "stage": None, "pids": [], "window": None, "summary": None}
    for part in text.split("|"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "pids":
            fields["pids"] = [pid for pid in value.split(",") if pid]
        elif key == "order":
            fields["order"] = int(value)
        elif key == "window":
            fields["window"] = value or None
        elif key in {"stage", "summary"}:
            fields[key] = value
    if fields["order"] is None or fields["stage"] not in {"order", "stage", "deploy", "schedule", "cutover"}:
        raise ValueError("stage must include order=<n> and stage=<order|stage|deploy|schedule|cutover>")
    if not fields["summary"]:
        raise ValueError("stage must include summary=")
    return fields


def cmd_annotate(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    path = ws / "state" / "lifecycle.json"
    estate = load_json(path)
    if not isinstance(estate, dict):
        print("state/lifecycle.json missing", file=sys.stderr)
        return 1
    moment = now_utc()
    guidance = estate.setdefault("guidance", {})
    assessment = estate.setdefault("assessment", {})
    plan = estate.setdefault("plan", {})
    if args.understood:
        guidance["understood"] = args.understood.strip()
    if args.answers:
        prior = guidance.get("answers") or ""
        extra = args.answers.strip()
        guidance["answers"] = extra if not prior else f"{prior}\n{extra}"
        if guidance.get("objectives_status") == "missing":
            guidance["objectives_status"] = "partial"
    if args.objectives:
        guidance["objectives_status"] = args.objectives
    if args.open_ask is not None and args.open_ask:
        guidance["open_asks"] = [text.strip() for text in args.open_ask if text.strip()][:8]
    elif args.clear_asks:
        guidance["open_asks"] = []
    guidance["updated_at"] = stamp_text(moment)
    if args.opinion:
        assessment["opinion"] = args.opinion.strip()
    if args.must is not None:
        assessment["must_move"] = [text.strip() for text in args.must if text.strip()][:12]
    if args.can_wait is not None:
        assessment["can_wait"] = [text.strip() for text in args.can_wait if text.strip()][:12]
    if args.contradiction is not None:
        assessment["contradictions"] = [text.strip() for text in args.contradiction if text.strip()][:8]
    if args.plan_opinion:
        plan["opinion"] = args.plan_opinion.strip()
    if args.plan_status:
        plan["status"] = args.plan_status
    if args.stage:
        try:
            plan["timeline"] = [parse_stage(text) for text in args.stage][:12]
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.recommendation:
        recs = []
        for text in args.recommendation[:10]:
            parts = text.split("|")
            if len(parts) < 4:
                print("recommendation must be priority|summary|why|next", file=sys.stderr)
                return 1
            priority, summary, why, nxt = (part.strip() for part in parts[:4])
            if priority not in {"high", "medium", "low"} or not summary or not why or not nxt:
                print("recommendation priority must be high, medium, or low", file=sys.stderr)
                return 1
            recs.append({
                "id": f"R-{len(recs) + 1}",
                "created_at": stamp_text(moment),
                "priority": priority,
                "summary": summary,
                "why": why,
                "evidence_refs": ["state/lifecycle.json"],
                "next_step": nxt,
            })
        estate["recommendations"] = recs
    items = estate.get("items") or []
    for item in args.selected or []:
        if "=" not in item:
            print("selected must be <pid>=<sku>", file=sys.stderr)
            return 1
        pid, sku = item.split("=", 1)
        pid = pid.strip()
        sku = sku.strip()
        match = next((row for row in items if row.get("pid") == pid), None)
        if match is None:
            print(f"selected unmatched pid: {pid}", file=sys.stderr)
            return 1
        match["selected_replacement"] = sku
        match["selected_replacement_source"] = "operator"
        if not match.get("list_cost_per_unit"):
            research = match.setdefault("research", {})
            if research.get("ccw") in {None, "skipped", "complete"}:
                research["ccw"] = "missing"
    if args.headline:
        estate["headline"] = args.headline.strip()
    elif args.plan_opinion and plan.get("status") in {"draft", "ready"}:
        estate["headline"] = args.plan_opinion.strip()[:240]
    elif args.opinion:
        estate["headline"] = args.opinion.strip()[:240]
    plan["cost"] = roll_cost(items)
    stamped = set(stamped_map(load_json(ws / DEVICES_PATH)).values())
    identity, research_conf = confidence(items, moment, stamped)
    guidance["identity_confidence"] = identity
    guidance["research_confidence"] = research_conf
    estate["status"] = estate_status(items, guidance, moment, stamped)
    estate["coverage"] = coverage_of(items)
    estate["keys"] = device_keys(items)
    estate["updated_at"] = stamp_text(moment)
    estate["source_agent"] = "modernization-analysis"
    if args.dispatched:
        estate["dispatched"] = [{"agent": "modernization-lifecycle", "invoked_at": stamp_text(moment)}]
    needs = any(row_stale(row, moment, stamped) for row in items)
    estate["next_action"] = TASK if needs else None
    try:
        write_estate(path, estate)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(visit_common.summary({
        "result": estate["status"],
        "wrote": "state/lifecycle.json",
        "annotated": True,
        "needs_lifecycle": needs,
        "task": TASK if needs else None,
        "objectives_status": guidance.get("objectives_status"),
        "plan_status": plan.get("status"),
    }))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="Modernization estate merge")
    sub = parser.add_subparsers(dest="cmd", required=True)
    assess = sub.add_parser("assess")
    assess.add_argument("--workspace", required=True)
    assess.add_argument("--mode", choices=("estate", "plan"), default="estate")
    assess.add_argument("--verbal", action="append", default=[])
    assess.add_argument("--upload", action="append", default=[])
    note = sub.add_parser("annotate")
    note.add_argument("--workspace", required=True)
    note.add_argument("--headline", default="")
    note.add_argument("--understood", default="")
    note.add_argument("--answers", default="")
    note.add_argument("--objectives", choices=("missing", "partial", "stated"), default="")
    note.add_argument("--open-ask", action="append", default=None)
    note.add_argument("--clear-asks", action="store_true")
    note.add_argument("--opinion", default="")
    note.add_argument("--plan-opinion", default="")
    note.add_argument("--plan-status", choices=("none", "asking", "draft", "ready"), default="")
    note.add_argument("--must", action="append", default=None)
    note.add_argument("--can-wait", action="append", default=None)
    note.add_argument("--contradiction", action="append", default=None)
    note.add_argument("--stage", action="append", default=None)
    note.add_argument("--recommendation", action="append", default=None)
    note.add_argument("--selected", action="append", default=None)
    note.add_argument("--dispatched", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "assess":
        return cmd_assess(args)
    return cmd_annotate(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
