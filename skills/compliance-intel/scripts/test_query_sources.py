"""Local fixture tests for query_sources.py. No Studio, GitHub, NIST, or network."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

import query_sources as qs

SCRIPTS = Path(__file__).resolve().parent
FIX = SCRIPTS / "unresolved_fixtures"
CATALOG = FIX / "catalog.json"
COVERAGE = FIX / "coverage.json"
INTEL = FIX / "intel.json"
INTEL_SKIPPED = FIX / "intel-skipped.json"
FORBIDDEN_KEYS = {"statement", "guidance", "prose", "related"}


def cli(argv: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = qs.main(argv)
    return code, json.loads(buf.getvalue())


def unresolved(*extra: str) -> dict:
    argv = [
        "unresolved",
        "--catalog",
        str(CATALOG),
        "--coverage",
        str(COVERAGE),
        "--intel",
        str(INTEL),
        *extra,
    ]
    code, payload = cli(argv)
    if code != 0 and payload.get("ok") is not False:
        raise AssertionError(payload)
    return payload


class UnresolvedTests(unittest.TestCase):
    def test_untouched_control_is_returned(self) -> None:
        payload = unresolved("--limit", "20")
        ids = [c["id"] for c in payload["controls"]]
        self.assertIn("AC-1", ids)

    def test_catalog_covered_control_is_excluded(self) -> None:
        payload = unresolved("--limit", "20")
        ids = [c["id"] for c in payload["controls"]]
        self.assertNotIn("AC-3", ids)
        self.assertEqual(payload["excluded"]["covered"], 1)

    def test_coverage_not_applicable_is_excluded(self) -> None:
        payload = unresolved("--limit", "150")
        ids = [c["id"] for c in payload["controls"]]
        self.assertNotIn("AC-19", ids)
        self.assertGreaterEqual(payload["excluded"]["not_applicable"], 1)

    def test_intel_candidate_is_excluded(self) -> None:
        payload = unresolved("--limit", "150")
        ids = [c["id"] for c in payload["controls"]]
        self.assertNotIn("SC-8", ids)
        self.assertEqual(payload["excluded"]["intel_candidate"], 1)

    def test_limit_5_caps_returned(self) -> None:
        payload = unresolved("--limit", "5")
        self.assertLessEqual(len(payload["controls"]), 5)
        self.assertEqual(payload["returned"], 5)
        self.assertEqual(payload["limit"], 5)

    def test_limit_20_caps_returned(self) -> None:
        payload = unresolved("--limit", "20")
        self.assertLessEqual(len(payload["controls"]), 20)
        self.assertEqual(payload["returned"], 20)
        self.assertEqual(payload["limit"], 20)
        self.assertGreater(payload["unresolved_total"], 20)

    def test_ordering_is_deterministic(self) -> None:
        first = unresolved("--limit", "20")
        second = unresolved("--limit", "20")
        self.assertEqual(first, second)
        index = qs.load_json(qs.REF / "oscal-800-53-rev5-index.json")
        index_ids = [c["id"] for c in index["controls"]]
        returned = [c["id"] for c in first["controls"]]
        self.assertEqual(returned, sorted(returned, key=index_ids.index))

    def test_family_behavior_unchanged(self) -> None:
        code, payload = cli(["family", "AC"])
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["family"], "AC")
        self.assertEqual(payload["oscal_release"], "v1.5.0")
        ids = [c["id"] for c in payload["controls"]]
        self.assertEqual(ids[:3], ["AC-1", "AC-2", "AC-3"])
        self.assertEqual(len(payload["controls"]), 28)
        for row in payload["controls"]:
            self.assertEqual(set(row), {"id", "title", "family"})
        self.assertEqual(
            payload["note"],
            "Titles only. Network-relevant families in the local index: AC AU CM IA SC SI.",
        )

    def test_lookup_behavior_unchanged(self) -> None:
        code, payload = cli(["lookup", "AC-17", "--offline"])
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["oscal_release"], "v1.5.0")
        self.assertEqual(payload["query"]["identifier"], "AC-17")
        self.assertEqual(payload["resolved"][0]["title"], "Remote Access")
        self.assertEqual(payload["resolved"][0]["source_control"], "nist-800-53:AC-17")
        dump = json.dumps(payload)
        self.assertNotIn('"statement"', dump)
        self.assertNotIn('"guidance"', dump)

        code171, payload171 = cli(["lookup", "3.1.7", "--offline"])
        self.assertEqual(code171, 0)
        self.assertTrue(payload171["ok"])
        self.assertEqual(payload171["resolved"][0]["resolved_from"], "nist-800-171:3.1.7")

    def test_unresolved_omits_statements_and_guidance(self) -> None:
        payload = unresolved("--limit", "20")
        dump = json.dumps(payload)
        self.assertNotIn('"statement"', dump)
        self.assertNotIn('"guidance"', dump)
        for row in payload["controls"]:
            self.assertEqual(set(row), {"id", "title", "family"})
            self.assertTrue(FORBIDDEN_KEYS.isdisjoint(row))

    def test_skipped_non_network_is_excluded(self) -> None:
        code, payload = cli(
            [
                "unresolved",
                "--intel",
                str(INTEL_SKIPPED),
                "--limit",
                "150",
            ]
        )
        self.assertEqual(code, 0)
        ids = [c["id"] for c in payload["controls"]]
        self.assertNotIn("AC-11", ids)
        self.assertGreaterEqual(payload["excluded"]["not_applicable"], 1)

    def test_gap_in_coverage_is_not_excluded(self) -> None:
        payload = unresolved("--limit", "20")
        ids = [c["id"] for c in payload["controls"]]
        self.assertIn("AC-1", ids)

    def test_filter_counts(self) -> None:
        index = qs.load_json(qs.REF / "oscal-800-53-rev5-index.json")
        before = len(index["controls"])
        payload = unresolved("--limit", "150")
        excluded = payload["excluded"]
        removed = excluded["covered"] + excluded["not_applicable"] + excluded["intel_candidate"]
        self.assertEqual(before, 150)
        self.assertEqual(removed, 3)
        self.assertEqual(payload["unresolved_total"], before - removed)
        self.assertEqual(payload["returned"], payload["unresolved_total"])


if __name__ == "__main__":
    unittest.main()
