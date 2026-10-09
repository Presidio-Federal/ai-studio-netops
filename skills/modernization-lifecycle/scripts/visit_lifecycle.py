#!/usr/bin/env python3
"""Cisco lifecycle visit. One command collects, merges, and writes.

collect runs under execution_type mcp_orchestration. It reads
state/lifecycle.json, calls Cisco, CCW, and NVD for stale rows, and
writes inventory/assets/<pid>.json plus the estate merge. annotate runs
under standard and only sets replacement_ask for a family bulletin.

The outer hai_mcp envelope matches the other visit scripts: result[0]
is a JSON string or a string body. Inner Cisco EOX, PSIRT, CCW GraphQL,
and NVD concise text are parsed here. A body this parser does not
recognize is a gap naming the keys. It does not invent a date, SKU,
train, or price.

  python3 <skill>/scripts/visit_lifecycle.py collect --workspace <file_explorer>
  python3 <skill>/scripts/visit_lifecycle.py annotate --workspace <file_explorer> \\
      --ask <pid>=<why, then the choice>
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

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
ESTATE_SCHEMA = SCHEMA_DIR / "lifecycle-estate.schema.json"
ITEM_SCHEMA = SCHEMA_DIR / "lifecycle-item.schema.json"
MAX_PIDS = 8
MAX_CISCO = 28
MAX_CCW = 4
MAX_NVD = 8
MAX_ADV = 15
NVD_PER_PID = 3
SW_CAP = 2
VIRTUAL = ("cat8000v", "c8000v", "csr1000v", "iosvl2", "iosv", "asav", "ftdv", "c9800-cl", "virtual")
DATE_KEYS = {
    "end_of_sale": ("EndOfSaleDate", "end_of_sale", "endOfSale"),
    "end_of_support": ("LastDateOfSupport", "end_of_support", "lastDateOfSupport"),
    "end_of_software_support": (
        "EndOfSWMaintenanceReleases",
        "end_of_software_support",
        "endOfSoftwareMaintenance",
    ),
    "end_of_security_vuln_support": (
        "EndOfSecurityVulSupportDate",
        "end_of_security_vuln_support",
        "endOfSecurityVulSupport",
    ),
}
HW_DATES = ("end_of_sale", "end_of_support")
SW_DATES = ("end_of_software_support", "end_of_security_vuln_support")
TRAIN_KEYS = (
    "recommended_software",
    "recommendedRelease",
    "recommended_release",
    "suggestedRelease",
    "suggested_release",
    "firstFixed",
    "first_fixed",
    "fixedRelease",
    "recommendedVersion",
)
SKU_KEYS = ("MigrationProductId", "migration_product_id", "migrationProductId")
FAMILY_KEYS = ("MigrationProductName", "migration_product_name", "migrationProductName")
BULLETIN_KEYS = ("LinkToProductBulletinURL", "bulletin_url", "bulletinUrl")
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}", re.I)
SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")


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


def write_json(path, payload, schema):
    path.parent.mkdir(parents=True, exist_ok=True)
    visit_common.validate(payload, schema)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
            print(f"lifecycle workspace={resolved}", file=sys.stderr)
            return resolved
    print('{"error": "workspace directory missing"}', file=sys.stderr)
    return None


def device_keys(names):
    keys = []
    for name in names or []:
        if not isinstance(name, str):
            continue
        text = name.strip()
        if not text or " " in text:
            continue
        key = f"device:{text}"
        if key not in keys:
            keys.append(key)
    return keys


def safe_pid(pid):
    return SAFE_RE.sub("_", pid).strip("._") or "pid"


def pid_variants(pid):
    found = []
    for candidate in (pid, pid.upper(), pid.replace("_", "-"), pid.upper().replace("_", "-")):
        if candidate and candidate not in found:
            found.append(candidate)
    return found[:3]


def is_virtual(row):
    blob = " ".join([str(row.get("pid") or "")] + [str(p) for p in (row.get("platforms") or [])]).lower()
    return any(token in blob for token in VIRTUAL)


def row_needs(row, now, detail_missing):
    research = row.get("research") if isinstance(row.get("research"), dict) else {}
    if detail_missing:
        return True
    exp = parse_time(row.get("expires_at"))
    if exp is None or now >= exp:
        return True
    if row.get("end_of_support") is None and research.get("eox") != "unavailable":
        return True
    versions = [v for v in (row.get("software_versions") or []) if isinstance(v, str) and v.strip()]
    if versions and not row.get("recommended_software") and research.get("software") in {None, "missing"}:
        return True
    if research.get("psirt") == "missing":
        return True
    rec = row.get("recommended_replacement")
    ccw = research.get("ccw")
    if rec and rec != row.get("pid") and not row.get("list_cost_per_unit") and ccw not in {"unavailable", "skipped"}:
        return True
    if row.get("selected_replacement") and not row.get("list_cost_per_unit") and ccw != "unavailable":
        return True
    return False


def unwrap(envelope):
    """Return (payload, error). payload is a dict, list, or text."""
    if not isinstance(envelope, dict) or not envelope.get("success"):
        err = envelope.get("error") if isinstance(envelope, dict) else None
        return None, str(err or "success false")[:300]
    outer = envelope.get("result")
    raw = outer[0] if isinstance(outer, list) and outer else outer
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None, "empty result"
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return text, None
    if isinstance(raw, dict) and raw.get("ok") is False:
        return None, str(raw.get("error") or raw.get("message") or "ok false")[:300]
    return raw, None


def glimpse(payload):
    if isinstance(payload, dict):
        return ",".join(list(payload.keys())[:8])
    if isinstance(payload, str):
        return payload[:160].replace("\n", " ")
    if isinstance(payload, list):
        return f"list:{len(payload)}"
    return type(payload).__name__


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def date_value(node):
    if node is None:
        return None
    if isinstance(node, str):
        text = node.strip()
        if not text or text.lower() in {"n/a", "na", "none", "null"}:
            return None
        return text[:10] if len(text) >= 10 and text[4] == "-" else text
    if isinstance(node, dict):
        for key in ("value", "date", "dateValue"):
            if key in node:
                return date_value(node.get(key))
    return None


def first_field(obj, names):
    for name in names:
        if name in obj and obj.get(name) not in (None, ""):
            return obj.get(name)
    return None


def parse_eox(payload):
    """Dates, one migration SKU, or a family with candidates. No invention."""
    dates = {key: None for key in DATE_KEYS}
    skus = []
    families = []
    bulletin = None
    if payload is None:
        return dates, skus, families, bulletin, True
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return dates, skus, families, bulletin, True
    for obj in walk(payload):
        for field, names in DATE_KEYS.items():
            if dates[field] is None:
                dates[field] = date_value(first_field(obj, names))
        sku = first_field(obj, SKU_KEYS)
        if isinstance(sku, str) and sku.strip() and sku.strip() not in skus:
            skus.append(sku.strip())
        family = first_field(obj, FAMILY_KEYS)
        if isinstance(family, str) and family.strip() and family.strip() not in families:
            families.append(family.strip())
        if bulletin is None:
            url = first_field(obj, BULLETIN_KEYS)
            if isinstance(url, str) and url.strip():
                bulletin = url.strip()
    empty = not any(dates.values()) and not skus and not families
    return dates, skus, families, bulletin, empty


def parse_train(payload):
    if not isinstance(payload, (dict, list)):
        return None
    for obj in walk(payload):
        for key in TRAIN_KEYS:
            value = obj.get(key)
            if isinstance(value, list):
                value = next((item for item in value if isinstance(item, str) and item.strip()), None)
            if isinstance(value, str):
                text = value.strip()
                if text and not text.lower().startswith("http"):
                    return text
    return None


def parse_advisories(payload):
    found = []
    seen = set()
    if not isinstance(payload, (dict, list)):
        return found
    for obj in walk(payload):
        aid = obj.get("advisoryId") or obj.get("advisory_id")
        if not isinstance(aid, str) or not aid.strip():
            title = obj.get("advisoryTitle") or obj.get("title")
            raw_id = obj.get("id")
            if isinstance(raw_id, str) and raw_id.startswith("cisco-sa"):
                aid = raw_id
            elif not title:
                continue
            else:
                aid = raw_id if isinstance(raw_id, str) else None
        if not aid or aid in seen:
            continue
        seen.add(aid)
        cves = obj.get("cves") or obj.get("cve") or []
        if isinstance(cves, str):
            cves = [cves]
        cve = next((item for item in cves if isinstance(item, str) and item.strip()), None)
        score = obj.get("cvssBaseScore")
        if score is None:
            score = obj.get("cvss")
        found.append({
            "id": aid,
            "title": obj.get("advisoryTitle") or obj.get("title"),
            "severity": obj.get("sir") or obj.get("severity"),
            "cve": cve,
            "cvss": None if score in (None, "", "N/A") else str(score),
        })
        if len(found) >= MAX_ADV:
            break
    return found


def cve_ids(advisories, payload):
    found = []
    for row in advisories:
        cve = row.get("cve")
        if isinstance(cve, str) and cve.upper().startswith("CVE-") and cve not in found:
            found.append(cve)
    if len(found) < NVD_PER_PID and isinstance(payload, (dict, list, str)):
        text = payload if isinstance(payload, str) else json.dumps(payload)
        for match in CVE_RE.findall(text):
            cve = match.upper()
            if cve not in found:
                found.append(cve)
            if len(found) >= NVD_PER_PID:
                break
    return found[:NVD_PER_PID]


def parse_nvd(payload, cve_id):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    title = None
    score = None
    severity = None
    for line in text.splitlines():
        if line.startswith("Description:"):
            title = line.split(":", 1)[1].strip() or None
        if "Score:" in line and "CVSS" in line:
            match = re.search(r"Score:\s*([0-9.]+|N/A)\s*(?:\(([^)]+)\))?", line)
            if match and match.group(1) != "N/A":
                score = match.group(1)
                severity = match.group(2)
    if text.lower().startswith("no data") or text.lower().startswith("error"):
        return None
    return {"id": cve_id, "title": title, "severity": severity, "cve": cve_id, "cvss": score}


def parse_ccw(payload):
    """Map SKU to list price. Entitlement and invalid-item errors stay unpriced."""
    prices = {}
    invalid = set()
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return prices, invalid
    if not isinstance(payload, (dict, list)):
        return prices, invalid
    text = json.dumps(payload)
    for match in re.findall(r"Invalid Item '([^']+)'", text):
        invalid.add(match)
    for obj in walk(payload):
        sku = obj.get("sku")
        unit = obj.get("unitListPrice")
        if not isinstance(sku, str) or not isinstance(unit, list):
            continue
        chars = obj.get("itemCharacteristics") if isinstance(obj.get("itemCharacteristics"), dict) else {}
        lead = obj.get("leadTime") if isinstance(obj.get("leadTime"), dict) else {}
        for price in unit:
            cost = (price or {}).get("cost") if isinstance(price, dict) else None
            if not isinstance(cost, dict) or cost.get("amount") is None:
                continue
            lead_text = None
            if lead.get("measurement") is not None:
                lead_text = f"{lead.get('measurement')} {lead.get('unitOfMeasure') or ''}".strip()
            orderable = chars.get("isOrderable")
            prices[sku] = {
                "amount": str(cost.get("amount")),
                "currency": cost.get("currency") or "USD",
                "availability": None if orderable is None else ("orderable" if orderable else "not orderable"),
                "lead_time": lead_text,
            }
            break
    return prices, invalid


def call_tool(tool, args, bucket, limits, budget):
    if budget.exhausted():
        return None, "budget exhausted"
    if limits[bucket] <= 0:
        return None, f"{bucket} cap"
    limits[bucket] -= 1
    payload, err = unwrap(visit_common.mcp_call(tool, args))
    return payload, err


def apply_dates(target, dates, fields):
    for field in fields:
        if dates.get(field) and not target.get(field):
            target[field] = dates[field]


def price_target(row):
    selected = row.get("selected_replacement")
    if isinstance(selected, str) and selected.strip():
        return selected.strip()
    recommended = row.get("recommended_replacement")
    if isinstance(recommended, str) and recommended.strip() and recommended.strip() != row.get("pid"):
        return recommended.strip()
    return None


def money_total(unit, qty):
    try:
        return f"{float(unit) * int(qty):.2f}"
    except (TypeError, ValueError):
        return None


def coverage_of(items):
    return {
        "item_count": len(items),
        "with_eox": sum(1 for row in items if row.get("end_of_support")),
        "with_psirt": sum(1 for row in items if row.get("psirts")),
        "with_cost": sum(1 for row in items if row.get("list_cost_per_unit")),
        "with_software": sum(
            1 for row in items if row.get("recommended_software") or row.get("end_of_software_support")
        ),
    }


def estate_status(estate):
    items = estate.get("items") or []
    if not items:
        return "unknown"
    now = now_utc()
    research_stale = False
    for row in items:
        research = row.get("research") if isinstance(row.get("research"), dict) else {}
        exp = parse_time(row.get("expires_at"))
        if research.get("eox") == "missing" or (exp is not None and now >= exp):
            research_stale = True
        versions = row.get("software_versions") or []
        if versions and research.get("software") == "missing":
            research_stale = True
        if row.get("selected_replacement") and not row.get("list_cost_per_unit"):
            research_stale = True
    if research_stale:
        return "stale"
    guidance = estate.get("guidance") if isinstance(estate.get("guidance"), dict) else {}
    if guidance.get("objectives_status") != "stated":
        return "partial"
    incomplete = False
    for row in items:
        research = row.get("research") if isinstance(row.get("research"), dict) else {}
        if research.get("eox") in {None, "missing", "partial"}:
            incomplete = True
    if incomplete:
        return "partial"
    return "ok"


def blank_item(row, moment):
    names = [name for name in (row.get("devices") or []) if isinstance(name, str)]
    return {
        "schema": "lifecycle-item/v1",
        "keys": device_keys(names),
        "pid": row.get("pid"),
        "updated_at": stamp_text(moment),
        "expires_at": stamp_text(moment + timedelta(days=90)),
        "quantity": int(row.get("quantity") or len(names)),
        "sample_device": row.get("sample_device"),
        "devices": names,
        "software_versions": [v for v in (row.get("software_versions") or []) if isinstance(v, str)],
        "eox": {
            "end_of_sale": row.get("end_of_sale"),
            "end_of_support": row.get("end_of_support"),
            "end_of_software_support": row.get("end_of_software_support"),
            "end_of_security_vuln_support": row.get("end_of_security_vuln_support"),
        },
        "replacement": {
            "sku": row.get("recommended_replacement"),
            "family": row.get("replacement_family"),
            "candidates": list(row.get("replacement_candidates") or []),
            "bulletin_url": None,
            "ask": row.get("replacement_ask"),
            "priced": bool(row.get("list_cost_per_unit")),
            "list_cost_per_unit": row.get("list_cost_per_unit"),
            "total_list_cost": row.get("total_list_cost"),
            "currency": row.get("currency"),
            "availability": None,
            "lead_time": None,
        },
        "recommended_software": row.get("recommended_software"),
        "psirts": list(row.get("psirts") or []),
        "vulnerabilities": list(row.get("vulnerabilities") or []),
        "gaps": [],
    }


def sot_versions(ws, row):
    sot = load_json(ws / "inventory" / "infra-sot.json")
    if not isinstance(sot, dict):
        return []
    wanted = {name for name in (row.get("devices") or []) if isinstance(name, str)}
    found = []
    for device in sot.get("devices") or []:
        if not isinstance(device, dict) or device.get("name") not in wanted:
            continue
        version = device.get("software_version")
        if isinstance(version, str) and version.strip() and version.strip() not in found:
            found.append(version.strip())
    return found


def collect_pid(row, limits, budget, gaps, lines):
    """Fill one estate row from Cisco. Returns (needs_family_ask, price_sku or None)."""
    pid = row.get("pid")
    research = row.setdefault("research", {})
    item_gaps = []
    virtual = is_virtual(row)

    dates = {key: None for key in DATE_KEYS}
    skus = []
    families = []
    bulletin = None
    saw_body = False
    eox_error = None
    for variant in pid_variants(pid):
        payload, err = call_tool(
            "cisco_get_eox_product_ids",
            {"product_ids": variant},
            "cisco",
            limits,
            budget,
        )
        if err:
            eox_error = err
            if "not found" in err.lower() or err == "budget exhausted":
                break
            continue
        saw_body = True
        got_dates, got_skus, got_families, got_url, empty = parse_eox(payload)
        if empty:
            eox_error = eox_error or f"no EoX records ({glimpse(payload)})"
            continue
        dates, skus, families, bulletin = got_dates, got_skus, got_families, got_url
        eox_error = None
        break
    if not any(dates.values()) and not skus and limits["cisco"] > 0 and not budget.exhausted():
        payload, err = call_tool(
            "cisco_psirt_product_id_finder",
            {"product": pid},
            "cisco",
            limits,
            budget,
        )
        if err:
            eox_error = eox_error or err
        elif payload is not None:
            saw_body = True
            for obj in walk(payload) if isinstance(payload, (dict, list)) else []:
                for key in ("productId", "product_id", "pid"):
                    found = obj.get(key)
                    if isinstance(found, str) and found.strip() and found.strip() != pid:
                        retry, retry_err = call_tool(
                            "cisco_get_eox_product_ids",
                            {"product_ids": found.strip()},
                            "cisco",
                            limits,
                            budget,
                        )
                        if retry_err or retry is None:
                            continue
                        got_dates, got_skus, got_families, got_url, empty = parse_eox(retry)
                        if not empty:
                            dates, skus, families, bulletin = got_dates, got_skus, got_families, got_url
                            eox_error = None
                        break
                if any(dates.values()) or skus:
                    break
    serial = row.get("serial") if isinstance(row.get("serial"), str) else None
    if serial and not any(dates.values()) and not skus:
        info, info_err = call_tool(
            "cisco_get_product_info_by_serials",
            {"serial_numbers": serial},
            "cisco",
            limits,
            budget,
        )
        if info_err:
            item_gaps.append(f"serial lookup: {info_err}")
        by_serial, serial_err = call_tool(
            "cisco_get_eox_by_serial_numbers",
            {"serial_numbers": serial},
            "cisco",
            limits,
            budget,
        )
        if serial_err:
            item_gaps.append(f"serial EoX: {serial_err}")
        elif by_serial is not None:
            saw_body = True
            got_dates, got_skus, got_families, got_url, empty = parse_eox(by_serial)
            if not empty:
                dates, skus, families, bulletin = got_dates, got_skus, got_families, got_url
                eox_error = None
            elif info is not None:
                got_dates, got_skus, got_families, got_url, empty = parse_eox(info)
                if not empty:
                    dates, skus, families, bulletin = got_dates, got_skus, got_families, got_url
                    eox_error = None

    apply_dates(row, dates, HW_DATES)
    skus = [sku for sku in skus if sku != pid]
    if len(skus) == 1:
        row["recommended_replacement"] = skus[0]
        row["replacement_family"] = None
        row["replacement_candidates"] = []
    elif len(skus) > 1:
        row["recommended_replacement"] = None
        row["replacement_candidates"] = skus[:8]
        row["replacement_family"] = families[0] if families else row.get("replacement_family")
    elif families:
        row["recommended_replacement"] = None
        row["replacement_family"] = families[0]
    if dates.get("end_of_support"):
        research["eox"] = "complete"
    elif saw_body or virtual:
        research["eox"] = "unavailable"
        if not virtual and eox_error:
            item_gaps.append(f"hardware EoX: {eox_error}")
    else:
        research["eox"] = "unavailable"
        item_gaps.append(f"hardware EoX: {eox_error or 'no response'}")

    versions = [v.strip() for v in (row.get("software_versions") or []) if isinstance(v, str) and v.strip()]
    versions = versions[:SW_CAP]
    train = None
    sw_dates = {key: None for key in DATE_KEYS}
    if not versions:
        research["software"] = "skipped"
    else:
        sw_error = None
        for version in versions:
            payload, err = call_tool(
                "cisco_get_eox_by_sw_release",
                {"software_release": version, "product_id": pid},
                "cisco",
                limits,
                budget,
            )
            if err and "product_id" in err.lower():
                payload, err = call_tool(
                    "cisco_get_eox_by_sw_release",
                    {"software_release": version},
                    "cisco",
                    limits,
                    budget,
                )
            if err:
                sw_error = err
                continue
            got_dates, _, _, _, empty = parse_eox(payload)
            if not empty:
                for field in SW_DATES:
                    if got_dates.get(field) and sw_dates[field] is None:
                        sw_dates[field] = got_dates[field]
            found = parse_train(payload)
            if found and train is None:
                train = found
            checker, checker_err = call_tool(
                "cisco_psirt_software",
                {"version": version},
                "cisco",
                limits,
                budget,
            )
            if checker_err:
                sw_error = sw_error or checker_err
            else:
                found = parse_train(checker)
                if found and train is None:
                    train = found
                got_dates, _, _, _, empty = parse_eox(checker)
                if not empty:
                    for field in SW_DATES:
                        if got_dates.get(field) and sw_dates[field] is None:
                            sw_dates[field] = got_dates[field]
        apply_dates(row, sw_dates, SW_DATES)
        if train:
            row["recommended_software"] = train
        if train or row.get("end_of_software_support"):
            research["software"] = "complete"
        elif sw_error:
            research["software"] = "unavailable"
            item_gaps.append(f"software: {sw_error}")
        else:
            research["software"] = "unavailable"
            item_gaps.append("software: Cisco returned no train")

    payload, err = call_tool("cisco_psirt_by_product", {"product": pid}, "cisco", limits, budget)
    advisories = []
    if err and "product" in err.lower():
        payload, err = call_tool("cisco_psirt_by_product", {"product_id": pid}, "cisco", limits, budget)
    if err:
        research["psirt"] = "unavailable"
        item_gaps.append(f"PSIRT: {err}")
    else:
        advisories = parse_advisories(payload)
        row["psirts"] = advisories
        research["psirt"] = "complete"

    cves = cve_ids(advisories, payload)
    vulns = []
    if not cves:
        research["nvd"] = "skipped"
    else:
        nvd_error = None
        for cve in cves:
            body, nvd_err = call_tool(
                "nvd_get_cve",
                {"cve_id": cve, "concise": True},
                "nvd",
                limits,
                budget,
            )
            if nvd_err:
                nvd_error = nvd_err
                continue
            parsed = parse_nvd(body, cve)
            if parsed:
                vulns.append(parsed)
        row["vulnerabilities"] = vulns
        if vulns:
            research["nvd"] = "complete" if not nvd_error else "partial"
        elif nvd_error:
            research["nvd"] = "unavailable"
            item_gaps.append(f"NVD: {nvd_error}")
        else:
            research["nvd"] = "unavailable"

    sku = price_target(row)
    if not sku or sku == pid:
        research["ccw"] = "skipped"
        sku = None
    else:
        research["ccw"] = "missing"

    family_ask = bool(row.get("replacement_family")) and not row.get("recommended_replacement") and not row.get("replacement_ask")
    for gap in item_gaps:
        gaps.append(f"{pid}: {gap}")
    if dates.get("end_of_support") or row.get("recommended_replacement") or row.get("recommended_software"):
        bits = [pid]
        if dates.get("end_of_support"):
            bits.append(f"support {dates['end_of_support']}")
        if row.get("recommended_software"):
            bits.append(f"software {row['recommended_software']}")
        if row.get("recommended_replacement"):
            bits.append(f"replacement {row['recommended_replacement']}")
        elif row.get("replacement_family"):
            bits.append(f"family {row['replacement_family']}")
        lines.append(", ".join(bits))
    return family_ask, sku, bulletin, item_gaps


def merge_clock(row, moment):
    row["updated_at"] = stamp_text(moment)
    row["expires_at"] = stamp_text(moment + timedelta(days=90))
    names = [name for name in (row.get("devices") or []) if isinstance(name, str)]
    row["quantity"] = len(names)
    if names and not row.get("sample_device"):
        row["sample_device"] = names[0]


def item_from_row(row, moment, bulletin, item_gaps):
    doc = blank_item(row, moment)
    doc["eox"] = {
        "end_of_sale": row.get("end_of_sale"),
        "end_of_support": row.get("end_of_support"),
        "end_of_software_support": row.get("end_of_software_support"),
        "end_of_security_vuln_support": row.get("end_of_security_vuln_support"),
    }
    doc["replacement"]["bulletin_url"] = bulletin
    doc["replacement"]["sku"] = row.get("recommended_replacement")
    doc["replacement"]["family"] = row.get("replacement_family")
    doc["replacement"]["candidates"] = list(row.get("replacement_candidates") or [])[:8]
    doc["replacement"]["ask"] = row.get("replacement_ask")
    doc["gaps"] = item_gaps[:12]
    doc["psirts"] = list(row.get("psirts") or [])[:15]
    doc["vulnerabilities"] = list(row.get("vulnerabilities") or [])[:15]
    return doc


def apply_price(row, doc, quote):
    if not quote:
        return
    amount = quote.get("amount")
    row["list_cost_per_unit"] = amount
    row["currency"] = quote.get("currency")
    row["total_list_cost"] = money_total(amount, row.get("quantity") or 0)
    research = row.setdefault("research", {})
    research["ccw"] = "complete"
    repl = doc["replacement"]
    repl["priced"] = True
    repl["list_cost_per_unit"] = amount
    repl["total_list_cost"] = row.get("total_list_cost")
    repl["currency"] = quote.get("currency")
    repl["availability"] = quote.get("availability")
    repl["lead_time"] = quote.get("lead_time")


def stamped_product_ids(ws):
    """PIDs the operator typed on inventory/assets/devices.json. None if that file is missing."""
    groups = asset_groups(ws)
    if groups is None:
        return None
    return set(groups)


def asset_groups(ws):
    """Group devices.json by product_id. None if the file is missing."""
    doc = load_json(ws / "inventory" / "assets" / "devices.json")
    if doc is None:
        doc = load_json(ws / "inventory" / "assets.json")
    if not isinstance(doc, dict):
        return None
    groups = {}
    for device in doc.get("devices") or []:
        if not isinstance(device, dict) or not isinstance(device.get("name"), str):
            continue
        pid = device.get("product_id")
        if not isinstance(pid, str) or not pid.strip():
            continue
        bucket = groups.setdefault(pid.strip(), {"devices": [], "versions": []})
        name = device["name"].strip()
        if name and name not in bucket["devices"]:
            bucket["devices"].append(name)
        version = device.get("software_version")
        if isinstance(version, str) and version.strip() and version.strip() not in bucket["versions"]:
            bucket["versions"].append(version.strip())
    return groups


def blank_stamped_row(pid, names, versions, moment):
    return {
        "pid": pid,
        "pid_source": "asset",
        "quantity": len(names),
        "devices": list(names),
        "roles": [],
        "platforms": [],
        "software_versions": list(versions),
        "sample_device": names[0] if names else None,
        "summary": f"{len(names)} devices, product id {pid}.",
        "source": {"kind": "asset", "reliability": "high", "ref": "inventory/assets/devices.json"},
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
            "software": "missing" if versions else "skipped",
            "psirt": "missing",
            "ccw": "skipped",
            "nvd": "skipped",
        },
    }


def adopt_stamped(items, groups, moment):
    """Make sure each product_id on the asset list has an estate row.

    Hostnames move off the CML node-type row onto that product id.
    A new row has no Cisco research yet, so the visit will collect it.
    """
    by_pid = {}
    for row in items:
        if isinstance(row, dict) and row.get("pid") and row["pid"] not in by_pid:
            by_pid[row["pid"]] = row
    claimed = set()
    for pid, group in groups.items():
        claimed.update(group["devices"])
        row = by_pid.get(pid)
        if row is None:
            row = blank_stamped_row(pid, group["devices"], group["versions"], moment)
            items.append(row)
            by_pid[pid] = row
            continue
        devices = [name for name in (row.get("devices") or []) if isinstance(name, str)]
        for name in group["devices"]:
            if name not in devices:
                devices.append(name)
        row["devices"] = devices
        row["quantity"] = len(devices)
        versions = [v for v in (row.get("software_versions") or []) if isinstance(v, str)]
        added = False
        for version in group["versions"]:
            if version not in versions:
                versions.append(version)
                added = True
        row["software_versions"] = versions
        if added:
            research = row.setdefault("research", {})
            if research.get("software") in {None, "skipped", "complete"}:
                research["software"] = "missing"
        if not row.get("detail_ref"):
            row["detail_ref"] = f"inventory/assets/{safe_pid(pid)}.json"
    for row in items:
        if row.get("pid") in groups:
            continue
        row["devices"] = [name for name in (row.get("devices") or []) if name not in claimed]
        row["quantity"] = len(row["devices"])
    return [row for row in items if row.get("devices")]


def cmd_collect(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    estate_path = ws / "state" / "lifecycle.json"
    estate = load_json(estate_path)
    if not isinstance(estate, dict):
        print(visit_common.summary({
            "result": "unknown",
            "wrote": None,
            "current": False,
            "pids": [],
            "needs_note": [],
            "gaps": ["state/lifecycle.json missing"],
            "lines": ["Estate file was not written."],
        }))
        return 0
    moment = now_utc()
    stamped = stamped_product_ids(ws)
    if stamped is None:
        print(visit_common.summary({
            "result": "unknown",
            "wrote": None,
            "current": False,
            "pids": [],
            "needs_note": [],
            "gaps": ["inventory/assets/devices.json missing"],
            "lines": ["No product ids to look up. Cisco was not called."],
        }))
        return 0
    items = [row for row in (estate.get("items") or []) if isinstance(row, dict) and row.get("pid")]
    groups = asset_groups(ws)
    if groups:
        items = adopt_stamped(items, groups, moment)
    version_copied = False
    for row in items:
        if row.get("pid") not in stamped or row.get("software_versions"):
            continue
        found = sot_versions(ws, row)
        if found:
            row["software_versions"] = found
            research = row.setdefault("research", {})
            if research.get("software") == "skipped":
                research["software"] = "missing"
            version_copied = True
    due = []
    for row in items:
        if row.get("pid") not in stamped:
            continue
        ref = row.get("detail_ref")
        missing = not (isinstance(ref, str) and (ws / ref).is_file())
        if row_needs(row, moment, missing):
            due.append(row)
    if not due and not version_copied:
        line = "No product_id is set on inventory/assets/devices.json." if not stamped else "Table is current."
        print(visit_common.summary({
            "result": "collected",
            "wrote": None,
            "current": True,
            "pids": [],
            "needs_note": [],
            "gaps": [],
            "lines": [line],
        }))
        return 0
    limits = {"cisco": MAX_CISCO, "ccw": MAX_CCW, "nvd": MAX_NVD}
    budget = visit_common.Budget(240)
    gaps = []
    lines = []
    needs_note = []
    want_price = {}
    collected = due[:MAX_PIDS]
    if len(due) > MAX_PIDS:
        gaps.append(f"cap: {len(due) - MAX_PIDS} PIDs left for the next visit")
    for row in collected:
        if budget.exhausted():
            gaps.append("budget exhausted")
            break
        family_ask, sku, bulletin, item_gaps = collect_pid(row, limits, budget, gaps, lines)
        merge_clock(row, moment)
        if family_ask:
            needs_note.append(row["pid"])
        doc = item_from_row(row, moment, bulletin, item_gaps)
        ref = f"inventory/assets/{safe_pid(row['pid'])}.json"
        row["detail_ref"] = ref
        if sku:
            want_price.setdefault(sku, []).append((row, doc))
        else:
            write_json(ws / ref, doc, ITEM_SCHEMA)
    quotes = {}
    invalid = set()
    skus = list(want_price)
    if skus and not budget.exhausted():
        for start in range(0, len(skus), 20):
            chunk = skus[start:start + 20]
            payload, err = call_tool(
                "ccw_get_catalog_items",
                {"skus": chunk, "priceListCode": "GLUS", "currency": "USD"},
                "ccw",
                limits,
                budget,
            )
            if err:
                for sku in chunk:
                    gaps.append(f"{sku}: CCW {err}")
                continue
            found, bad = parse_ccw(payload)
            quotes.update(found)
            invalid.update(bad)
            if not found and payload is not None:
                gaps.append(f"CCW: no prices ({glimpse(payload)})")
    for sku, pairs in want_price.items():
        quote = quotes.get(sku)
        for row, doc in pairs:
            if quote:
                apply_price(row, doc, quote)
                lines.append(f"{row['pid']} list {quote['amount']} {quote.get('currency') or 'USD'} for {sku}")
            elif sku in invalid:
                row.setdefault("research", {})["ccw"] = "unavailable"
                gaps.append(f"{sku}: CCW invalid or not entitled")
            else:
                row.setdefault("research", {})["ccw"] = "unavailable"
                gaps.append(f"{sku}: CCW returned no list price")
            ref = row.get("detail_ref")
            write_json(ws / ref, doc, ITEM_SCHEMA)
    estate["items"] = items
    for row in items:
        if isinstance(row, dict):
            row.setdefault("recommended_software", None)
            row.setdefault("recommended_replacement", None)
            row.setdefault("list_cost_per_unit", None)
            row.setdefault("total_list_cost", None)
            row.setdefault("end_of_support", None)
            row.setdefault("end_of_software_support", None)
            if not isinstance(row.get("vulnerabilities"), list):
                row["vulnerabilities"] = []
            if not isinstance(row.get("psirts"), list):
                row["psirts"] = []
    estate["keys"] = device_keys([name for row in items for name in (row.get("devices") or [])])
    estate["coverage"] = coverage_of(items)
    estate["updated_at"] = stamp_text(moment)
    estate["source_agent"] = "modernization-lifecycle"
    estate["status"] = estate_status(estate)
    if not lines:
        lines.append(f"Collected {len(collected)} PIDs." if collected else "Copied software versions from SoT.")
    estate["headline"] = lines[0][:240]
    write_json(estate_path, estate, ESTATE_SCHEMA)
    result = "partial" if gaps else "collected"
    print(visit_common.summary({
        "result": result,
        "wrote": "state/lifecycle.json",
        "current": False,
        "pids": [row.get("pid") for row in collected],
        "needs_note": needs_note,
        "gaps": gaps[:12],
        "lines": lines[:5],
    }))
    return 0


def cmd_annotate(args):
    ws = resolve_workspace(args.workspace)
    if ws is None:
        return 1
    estate_path = ws / "state" / "lifecycle.json"
    estate = load_json(estate_path)
    if not isinstance(estate, dict):
        print("state/lifecycle.json missing", file=sys.stderr)
        return 1
    asks = {}
    for item in args.ask or []:
        if "=" not in item:
            print("ask must be <pid>=<why, then the choice>", file=sys.stderr)
            return 1
        pid, text = item.split("=", 1)
        asks[pid.strip()] = text.strip()
    if not asks:
        print("annotate requires --ask", file=sys.stderr)
        return 1
    matched = set()
    for row in estate.get("items") or []:
        if not isinstance(row, dict):
            continue
        pid = row.get("pid")
        if pid not in asks or not asks[pid]:
            continue
        matched.add(pid)
        row["replacement_ask"] = asks[pid]
        ref = row.get("detail_ref")
        if not isinstance(ref, str):
            continue
        doc_path = ws / ref
        doc = load_json(doc_path)
        if not isinstance(doc, dict):
            continue
        replacement = doc.setdefault("replacement", {})
        replacement["ask"] = asks[pid]
        try:
            write_json(doc_path, doc, ITEM_SCHEMA)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    missing = sorted(set(asks) - matched)
    if missing:
        print("annotate unmatched pids: " + ", ".join(missing), file=sys.stderr)
        return 1
    try:
        write_json(estate_path, estate, ESTATE_SCHEMA)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(visit_common.summary({"result": "collected", "annotated": True, "asks": sorted(asks)}))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="Cisco lifecycle visit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--workspace", required=True)
    note = sub.add_parser("annotate")
    note.add_argument("--workspace", required=True)
    note.add_argument("--ask", action="append", default=[])
    args = parser.parse_args(argv)
    if args.cmd == "collect":
        return cmd_collect(args)
    return cmd_annotate(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
