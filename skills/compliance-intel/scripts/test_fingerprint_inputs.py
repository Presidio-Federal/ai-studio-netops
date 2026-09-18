#!/usr/bin/env python3
"""Tests for fingerprint_inputs.py — local fixtures only, no live NIST/git."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import fingerprint_inputs as fp  # noqa: E402

FIX = SCRIPTS / "fingerprint_fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def run(
    *,
    index: str = "index.json",
    estate: str | None = "estate.json",
    catalog: str | None = "catalog.json",
    prior: dict | None = None,
    missing_coverage: bool = False,
) -> dict:
    return fp.evaluate(
        index=load(index),
        pin=load("pin.json"),
        estate_doc=load(estate) if estate else None,
        catalog_doc=load(catalog) if catalog else None,
        prior=prior,
        missing_coverage=missing_coverage,
    )


class FingerprintTests(unittest.TestCase):
    def test_semantic_identical_inputs_same_hashes(self) -> None:
        a = run()
        b = run(estate="estate-churn.json", catalog="catalog-reordered.json")
        self.assertEqual(a["framework"]["hash"], b["framework"]["hash"])
        self.assertEqual(a["estate"]["hash"], b["estate"]["hash"])
        self.assertEqual(a["catalog"]["hash"], b["catalog"]["hash"])
        self.assertEqual(a["framework"]["control_count"], 2)

    def test_title_change_same_count_changes_framework_hash(self) -> None:
        base = run()
        changed = run(index="index-title-change.json")
        self.assertEqual(base["framework"]["control_count"], changed["framework"]["control_count"])
        self.assertNotEqual(base["framework"]["hash"], changed["framework"]["hash"])
        prior = base["persist"]
        again = fp.evaluate(
            index=load("index-title-change.json"),
            pin=load("pin.json"),
            estate_doc=load("estate.json"),
            catalog_doc=load("catalog.json"),
            prior=prior,
            missing_coverage=False,
        )
        self.assertEqual(again["changed"], ["framework"])
        self.assertTrue(again["work"]["framework_rescan"])
        self.assertTrue(again["work"]["estate_rejudge"])
        self.assertFalse(again["work"]["coverage_from_catalog"])

    def test_estate_role_change_not_timestamp_churn(self) -> None:
        base = run()
        prior = base["persist"]
        churn = fp.evaluate(
            index=load("index.json"),
            pin=load("pin.json"),
            estate_doc=load("estate-churn.json"),
            catalog_doc=load("catalog.json"),
            prior=prior,
            missing_coverage=False,
        )
        self.assertEqual(churn["changed"], [])
        self.assertFalse(churn["work"]["estate_rejudge"])
        self.assertFalse(churn["work"]["framework_rescan"])
        role = fp.evaluate(
            index=load("index.json"),
            pin=load("pin.json"),
            estate_doc=load("estate-role-change.json"),
            catalog_doc=load("catalog.json"),
            prior=prior,
            missing_coverage=False,
        )
        self.assertEqual(role["changed"], ["estate"])
        self.assertTrue(role["work"]["estate_rejudge"])
        self.assertFalse(role["work"]["framework_rescan"])
        self.assertFalse(role["work"]["coverage_from_catalog"])

    def test_catalog_nist_added(self) -> None:
        base = run()
        prior = base["persist"]
        added = fp.evaluate(
            index=load("index.json"),
            pin=load("pin.json"),
            estate_doc=load("estate.json"),
            catalog_doc=load("catalog-nist-added.json"),
            prior=prior,
            missing_coverage=False,
        )
        self.assertEqual(added["changed"], ["catalog"])
        self.assertTrue(added["work"]["coverage_from_catalog"])
        self.assertFalse(added["work"]["framework_rescan"])
        self.assertTrue(added["work"]["reconcile_candidates"])

    def test_matching_prior_is_reconcile_only(self) -> None:
        base = run()
        again = fp.evaluate(
            index=load("index.json"),
            pin=load("pin.json"),
            estate_doc=load("estate.json"),
            catalog_doc=load("catalog.json"),
            prior=base["persist"],
            missing_coverage=False,
        )
        self.assertEqual(again["changed"], [])
        self.assertFalse(again["missing_prior"])
        self.assertFalse(again["work"]["framework_rescan"])
        self.assertFalse(again["work"]["estate_rejudge"])
        self.assertFalse(again["work"]["coverage_from_catalog"])
        self.assertTrue(again["work"]["reconcile_candidates"])

    def test_missing_prior_and_missing_coverage_rescan(self) -> None:
        first = run(missing_coverage=True)
        self.assertTrue(first["missing_prior"])
        self.assertTrue(first["missing_coverage"])
        self.assertEqual(first["changed"], ["framework", "estate", "catalog"])
        self.assertTrue(first["work"]["framework_rescan"])
        self.assertTrue(first["work"]["estate_rejudge"])
        self.assertFalse(first["work"]["coverage_from_catalog"])
        self.assertTrue(first["work"]["reconcile_candidates"])

    def test_cli_catalog_stdin_and_prior_file(self) -> None:
        first = run()
        with tempfile.TemporaryDirectory() as tmp:
            prior_path = Path(tmp) / "metadata.json"
            prior_path.write_text(json.dumps(first["persist"]), encoding="utf-8")
            catalog = (FIX / "catalog.json").read_text(encoding="utf-8")
            argv = [
                "--pin",
                str(FIX / "pin.json"),
                "--index",
                str(FIX / "index.json"),
                "--estate",
                str(FIX / "estate.json"),
                "--catalog",
                "-",
                "--prior",
                str(prior_path),
                "--coverage",
                str(FIX / "coverage.json"),
            ]
            old_stdin = sys.stdin
            old_stdout = sys.stdout
            captured = __import__("io").StringIO()
            try:
                sys.stdin = __import__("io").StringIO(catalog)
                sys.stdout = captured
                code = fp.main(argv)
            finally:
                sys.stdin = old_stdin
                sys.stdout = old_stdout
            self.assertEqual(code, 0)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload["changed"], [])
            self.assertFalse(payload["work"]["framework_rescan"])

    def test_persist_schema_fields(self) -> None:
        payload = run()
        persist = payload["persist"]
        self.assertEqual(persist["schema"], "compliance-intel-metadata/v1")
        self.assertEqual(persist["source_agent"], "compliance")
        self.assertTrue(persist["framework"]["hash"].startswith("sha256:"))
        self.assertEqual(len(persist["framework"]["hash"]), 7 + 64)
        self.assertEqual(
            persist["last_evaluated"]["framework_hash"], persist["framework"]["hash"]
        )
        self.assertEqual(persist["framework"]["name"], "NIST-800-53")
        self.assertEqual(persist["framework"]["control_count"], 2)


if __name__ == "__main__":
    unittest.main()
