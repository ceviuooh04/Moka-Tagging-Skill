#!/usr/bin/env python3
"""Fictional tests for the offline batch and exact boundaries; no live access."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import validate_rate_batch as batch
from test_validate_rate_write_plan import example


def test_library():
    _, _, library = example()
    bounds = [(0, 10, True), (10, 20, False), (20, 30, False),
              (30, 60, False), (60, 100, False)]
    library["tags"] = []
    for i, (lo, hi, inclusive) in enumerate(bounds):
        library["tags"].append({
            "tag_group": "rate", "tag_value": f"{lo} USD {'≤' if inclusive else '<'} Expected Rate ≤ {hi} USD",
            "status": "Active", "moka_tag_id": f"DEMO-T{i}", "currency": "USD", "period": "hour",
            "lower": str(lo), "upper": str(hi), "lower_inclusive": inclusive, "upper_inclusive": True,
        })
    return library


def item(record="A1", name="Alice", rate="80", index=4, sharing=None):
    plan, context, _ = example()
    lib = test_library()
    for candidate in (plan["candidate"], context["candidate"]):
        candidate.update(moka_id=record, name=name)
    context["allowed_record_ids"]["moka"] = [record]
    context["sources"][0].update(record_id=record, url=f"https://example.test/candidates/application/{record}/info")
    context["sources"][0]["segments"][0]["text"] = f"Expected hourly rate in USD\n{rate}"
    plan["expected_rate"] = rate
    plan["evidence"][0]["excerpt"] = rate
    plan["changes"][0].update(record_id=record, tag_value=lib["tags"][index]["tag_value"],
                              remote_tag_id=lib["tags"][index]["moka_tag_id"])
    out = {"plan": plan, "context": context}
    if sharing is not None:
        out["sharing"] = sharing
    return out


def identity(key, shared=True, sharing_verified=True):
    return {"candidate_key": key, "identity_verified": True,
            "tags_shared": shared, "tags_shared_verified": sharing_verified}


class BatchTests(unittest.TestCase):
    def run_batch(self, items):
        data = {"items": items}
        before = copy.deepcopy(data)
        with patch("socket.socket", side_effect=AssertionError("network must not be used")):
            result = batch.validate_batch(data, test_library())
        self.assertEqual(data, before)
        self.assertIs(result["authorized"], False)
        self.assertIs(result["executed"], False)
        self.assertIs(result["cross_record_review_required"], True)
        return result

    def test_all_five_boundaries_and_just_above(self):
        cases = [("0", 0), ("10", 0), ("10.001", 1), ("20", 1), ("20.001", 2),
                 ("30", 2), ("30.001", 3), ("60", 3), ("60.001", 4), ("100", 4)]
        for rate, idx in cases:
            with self.subTest(rate=rate):
                result = self.run_batch([item(rate=rate, index=idx)])
                self.assertEqual(result["results"][0]["status"], "ready", result)
        for rate in ("-0.1", "100.001", "1000"):
            with self.subTest(rate=rate):
                self.assertEqual(self.run_batch([item(rate=rate)])["results"][0]["status"], "blocked")

    def test_exact_wrong_boundary_tag_is_blocked(self):
        for rate, wrong_index in (("10", 1), ("20", 2), ("30", 3), ("60", 4)):
            with self.subTest(rate=rate):
                self.assertEqual(self.run_batch([item(rate=rate, index=wrong_index)])["results"][0]["status"], "blocked")

    def test_duplicate_application_id_blocks_both(self):
        result = self.run_batch([item(), item(name="Other")])
        self.assertEqual([x["status"] for x in result["results"]], ["blocked", "blocked"])
        self.assertTrue(all("DUPLICATE_APPLICATION_ID" in x["errors"] for x in result["results"]))

    def test_same_name_without_verified_identity_blocks_both(self):
        result = self.run_batch([item(), item(record="A2", name="ALICE")])
        self.assertEqual([x["status"] for x in result["results"]], ["blocked", "blocked"])
        self.assertTrue(all("SAME_NAME_IDENTITY_UNVERIFIED" in x["errors"] for x in result["results"]))

    def test_same_name_different_verified_people_are_independent(self):
        result = self.run_batch([item(sharing=identity("P1")),
                                 item(record="A2", name="ALICE", sharing=identity("P2"))])
        self.assertEqual([x["status"] for x in result["results"]], ["ready", "ready"])

    def test_shared_tags_defer_one_even_when_format_differs(self):
        result = self.run_batch([item(rate="60", index=3, sharing=identity("P1")),
                                 item(record="A2", name="Alice B", rate="60.0", index=3, sharing=identity("P1"))])
        self.assertEqual([x["status"] for x in result["results"]], ["ready", "deferred_shared"])
        self.assertFalse(result["all_ready"])

    def test_unshared_tags_are_independent_when_verified(self):
        result = self.run_batch([item(sharing=identity("P1", shared=False)),
                                 item(record="A2", name="Alice B", sharing=identity("P1", shared=False))])
        self.assertEqual([x["status"] for x in result["results"]], ["ready", "ready"])

    def test_shared_candidate_conflicting_rate_or_sharing_blocks_both(self):
        one = item(sharing=identity("P1"))
        two = item(record="A2", name="Alice B", rate="90", sharing=identity("P1"))
        result = self.run_batch([one, two])
        self.assertTrue(all("CANDIDATE_RATE_CONFLICT_OR_INVALID" in x["errors"] for x in result["results"]))
        two = item(record="A2", name="Alice B", sharing=identity("P1", sharing_verified=False))
        result = self.run_batch([one, two])
        self.assertTrue(all("TAG_SHARING_UNVERIFIED_OR_CONFLICTING" in x["errors"] for x in result["results"]))

    def test_existing_rate_tag_cannot_be_added(self):
        entry = item()
        entry["context"]["current_tags"]["moka"].append({"tag_group": "rate", "tag_value": "existing"})
        self.assertEqual(self.run_batch([entry])["results"][0]["status"], "blocked")

    def test_input_output_is_private_and_does_not_overwrite_input(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source, library, output = base / "batch.json", base / "library.json", base / "output.json"
            source.write_text(json.dumps({"items": [item()]}), encoding="utf-8")
            library.write_text(json.dumps(test_library()), encoding="utf-8")
            script = Path(batch.__file__)
            args = [sys.executable, str(script), "--batch", str(source), "--library", str(library), "--output"]
            completed = subprocess.run(args + [str(output)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            output.chmod(0o644)
            completed = subprocess.run(args + [str(output)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            original = source.read_text(encoding="utf-8")
            completed = subprocess.run(args + [str(source)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 3)
            self.assertEqual(source.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
