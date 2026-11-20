"""Fully fictional tests for validate_mixed_plan.py; never contact Moka or network."""
import copy
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_mixed_plan as gate
from test_validate_rate_write_plan import example as rate_example


class MixedPlanTests(unittest.TestCase):
    def setUp(self):
        self.library = {"taxonomy_version": "1.1"}
        self.tax_plan = {"candidate": {"moka_id": "FAKE-001", "match_status": "verified"},
                         "taxonomy_version": "1.1", "changes": [self.change("fictional-country")]}
        self.rate_plan = {"candidate": {"moka_id": "FAKE-001", "match_status": "verified"},
                          "taxonomy_version": "1.1", "changes": [self.change("fictional-rate")]}
        self.tax_context = self.context()
        self.rate_context = self.context()
        self.ok = {"ready_for_confirmation": True, "authorized": False, "executed": False, "errors": []}

    @staticmethod
    def change(tag_value, **updates):
        change = {"system": "moka", "record_id": "FAKE-001", "field": "candidate_custom_tags",
                  "operation": "add", "tag_group": "fictional", "tag_value": tag_value}
        change.update(updates)
        return change

    @staticmethod
    def context(**updates):
        obj = {"candidate": {"moka_id": "FAKE-001", "match_status": "verified"},
               "current_tags": {"moka": [{"tag_group": "fictional-group", "tag_value": "old-value"}]},
               "current_tags_verified": True, "current_tags_verification_reference": "FAKE-READ-A",
               "current_tag_groups_verified": True, "current_tag_groups_verification_reference": "FAKE-GROUPS-A",
               "current_tags_snapshot_verified": True, "current_tags_snapshot_verification_reference": "FAKE-SNAPSHOT-READ-A",
               "snapshot_id": "FAKE-SNAPSHOT-001",
               "sources": [{"source_id": "FAKE-SOURCE-A", "system": "moka", "record_id": "FAKE-001",
                            "url": "https://fictional.invalid/application/FAKE-001/profile",
                            "captured_at": "2099-01-01T00:00:00Z",
                            "segments": [{"locator": "fake", "text": "entirely fictional evidence"}]}]}
        obj.update(updates)
        return obj

    def run_gate(self):
        return gate.validate(self.tax_plan, self.tax_context, self.rate_plan, self.rate_context, self.library)

    def test_both_validators_called_with_same_library(self):
        with patch.object(gate.validate_taxonomy_plan, "validate", return_value=self.ok) as tax, \
             patch.object(gate.validate_rate_write_plan, "validate", return_value=self.ok) as rate:
            result = self.run_gate()
        self.assertTrue(result["ready_for_confirmation"])
        self.assertFalse(result["authorized"])
        self.assertFalse(result["executed"])
        self.assertIs(tax.call_args.args[2], self.library)
        self.assertIs(rate.call_args.args[2], self.library)

    def test_different_record_is_blocked(self):
        self.rate_plan["candidate"]["moka_id"] = "FAKE-002"
        self.assertIn("IDENTITY_MISMATCH", self.run_gate()["errors"])

    def test_tier_rate_pair_is_blocked_even_if_ids_have_same_text(self):
        self.tax_plan["changes"][0]["tag_group"] = "tier"
        with patch.object(gate.validate_taxonomy_plan, "validate", return_value=self.ok), \
             patch.object(gate.validate_rate_write_plan, "validate", return_value=self.ok):
            result = self.run_gate()
        self.assertFalse(result["ready_for_confirmation"])
        self.assertEqual(result["errors"], ["TIER_PROJECT_CONTEXT_UNSUPPORTED"])
        self.assertFalse(result["authorized"])
        self.assertFalse(result["executed"])

    def test_tier_mixed_preflight_ignores_order_and_normalizes(self):
        for label in ('tier', ' TIER ', 'Ｔｉｅｒ'):
            with self.subTest(label=label):
                self.tax_plan['changes'] = [self.change('ordinary'), self.change('tier 3', tag_group=label)]
                with patch.object(gate.validate_taxonomy_plan, 'validate', return_value=self.ok) as tax, \
                     patch.object(gate.validate_rate_write_plan, 'validate', return_value=self.ok) as rate:
                    result = self.run_gate()
                self.assertEqual(result['errors'], ['TIER_PROJECT_CONTEXT_UNSUPPORTED'])
                self.assertFalse(result['ready_for_confirmation'])
                tax.assert_not_called()
                rate.assert_not_called()

    def test_tier_misplaced_in_rate_plan_is_blocked_before_either_gate(self):
        self.rate_plan['changes'][0]['tag_group'] = ' TIER '
        with patch.object(gate.validate_taxonomy_plan, 'validate', return_value=self.ok) as tax, \
             patch.object(gate.validate_rate_write_plan, 'validate', return_value=self.ok) as rate:
            result = self.run_gate()
        self.assertFalse(result['ready_for_confirmation'])
        self.assertEqual(result['errors'], ['TIER_PROJECT_CONTEXT_UNSUPPORTED'])
        tax.assert_not_called()
        rate.assert_not_called()

    def test_existing_different_tier_values_do_not_trigger_a_tier_write_or_conflict(self):
        values = [{'tag_group': 'tier', 'tag_value': 'tier 1'},
                  {'tag_group': 'tier', 'tag_value': 'tier 3'}]
        self.tax_context['current_tags']['moka'] = copy.deepcopy(values)
        self.rate_context['current_tags']['moka'] = copy.deepcopy(values)
        before = copy.deepcopy((self.tax_plan, self.tax_context, self.rate_plan, self.rate_context))
        with patch.object(gate.validate_taxonomy_plan, 'validate', return_value=self.ok), \
             patch.object(gate.validate_rate_write_plan, 'validate', return_value=self.ok):
            result = self.run_gate()
        self.assertEqual(result, self.ok)
        self.assertEqual((self.tax_plan, self.tax_context, self.rate_plan, self.rate_context), before)

    def test_different_version_is_blocked(self):
        self.rate_plan["taxonomy_version"] = "FAKE-VERSION"
        self.assertIn("TAXONOMY_VERSION_MISMATCH", self.run_gate()["errors"])

    def test_different_field_is_blocked(self):
        self.tax_plan["changes"][0]["field"] = "fictional_other_field"
        self.assertIn("FIELD_NOT_ALLOWED", self.run_gate()["errors"])

    def test_different_old_tag_multiset_is_blocked(self):
        self.rate_context["current_tags"]["moka"][0]["tag_value"] = "different-fictional-old-value"
        self.assertIn("CURRENT_TAGS_MISMATCH", self.run_gate()["errors"])

    def test_different_snapshot_is_blocked(self):
        self.rate_context["snapshot_id"] = "FAKE-SNAPSHOT-002"
        self.assertIn("SNAPSHOT_MISMATCH", self.run_gate()["errors"])

    def test_either_gate_failure_blocks_pair(self):
        blocked = {"ready_for_confirmation": False, "authorized": False, "executed": False,
                   "errors": ["FAKE_BLOCK"]}
        with patch.object(gate.validate_taxonomy_plan, "validate", return_value=self.ok), \
             patch.object(gate.validate_rate_write_plan, "validate", return_value=blocked):
            result = self.run_gate()
        self.assertFalse(result["ready_for_confirmation"])
        self.assertEqual(result["errors"], ["RATE_GATE_BLOCKED"])

    def test_real_v11_gates_both_run_on_consistent_fictional_inputs(self):
        rate_plan, rate_context, library = rate_example()
        rate_plan['taxonomy_version'] = library['taxonomy_version'] = '1.1'
        library.update(current_version_verification_reference='DEMO-CURRENT',
                       active_status_verification_reference='DEMO-ACTIVE',
                       moka_id_mapping_reference='DEMO-IDS')
        library['tags'].append({'tag_group':'language','tag_value':'spanish',
                                'status':'Active','moka_tag_id':'DEMO-LANGUAGE-ID'})
        rate_context.update(current_tags_verification_reference='DEMO-TAGS',
                            current_tag_groups_verified=True,
                            current_tag_groups_verification_reference='DEMO-GROUPS',
                            current_tags_snapshot_verified=True,
                            current_tags_snapshot_verification_reference='DEMO-SNAPSHOT-REF',
                            snapshot_id='DEMO-SNAPSHOT')
        rate_context['current_tags']['moka'] = [
            {'tag_group': 'tier', 'tag_value': 'tier 1'},
            {'tag_group': 'tier', 'tag_value': 'tier 3'}]
        tax_context = copy.deepcopy(rate_context)
        tax_context['sources'][0]['segments'].append({'locator':'language',
                                                       'text':'fictional record supports spanish'})
        tax_plan = {'candidate':copy.deepcopy(rate_plan['candidate']), 'taxonomy_version':'1.1',
                    'changes':[{'system':'moka','record_id':'A1','field':'candidate_custom_tags',
                                'operation':'add','tag_group':'language','tag_value':'spanish',
                                'remote_tag_id':'DEMO-LANGUAGE-ID',
                                'evidence':[{'source_id':'S1','locator':'language','excerpt':'spanish'}]}]}
        result = gate.validate(tax_plan,tax_context,rate_plan,rate_context,library)
        self.assertTrue(result['ready_for_confirmation'],result)
        self.assertFalse(result['authorized']); self.assertFalse(result['executed'])
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / (str(i) + '.json') for i in range(5)]
            for path, value in zip(paths, (tax_plan, tax_context, rate_plan, rate_context, library)):
                path.write_text(json.dumps(value), encoding='utf-8')
            args = [sys.executable, str(Path(gate.__file__).resolve())]
            for flag, path in zip(('--taxonomy-plan', '--taxonomy-context', '--rate-plan',
                                   '--rate-context', '--library'), paths):
                args.extend((flag, str(path)))
            run = subprocess.run(args, cwd=directory, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                 capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(json.loads(run.stdout)['ready_for_confirmation'])
            self.assertEqual(run.stderr, '')
        rate_plan['expected_rate'] = '120'
        result = gate.validate(tax_plan,tax_context,rate_plan,rate_context,library)
        self.assertFalse(result['ready_for_confirmation'])
        self.assertIn('RATE_GATE_BLOCKED',result['errors'])

    def test_missing_or_single_plan_input_blocks(self):
        self.assertFalse(gate.validate(self.tax_plan, self.tax_context, None, self.rate_context,
                                       self.library)["ready_for_confirmation"])
        self.rate_plan["changes"] = []
        self.assertIn("CHANGE_COUNT_INVALID", self.run_gate()["errors"])

    def test_no_sensitive_evidence_in_output(self):
        self.tax_context["sources"][0]["segments"][0]["text"] = "PRIVATE_EVIDENCE_SENTINEL"
        output = json.dumps(self.run_gate())
        self.assertNotIn("PRIVATE_EVIDENCE_SENTINEL", output)

    def test_mixed_cli_subprocess_imports_dependencies_and_blocks_tier(self):
        self.tax_plan['changes'][0]['tag_group'] = 'tier'
        values = (self.tax_plan, self.tax_context, self.rate_plan, self.rate_context, self.library)
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / (str(i) + '.json') for i in range(5)]
            for path, value in zip(paths, values):
                path.write_text(json.dumps(value), encoding='utf-8')
            args = [sys.executable, str(Path(gate.__file__).resolve())]
            for flag, path in zip(('--taxonomy-plan', '--taxonomy-context', '--rate-plan',
                                   '--rate-context', '--library'), paths):
                args.extend((flag, str(path)))
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            run = subprocess.run(args, cwd=directory, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertEqual(json.loads(run.stdout)['errors'], ['TIER_PROJECT_CONTEXT_UNSUPPORTED'])
            self.assertEqual(run.stderr, '')

    def test_cli_rejects_duplicate_json_key_without_echoing_content(self):
        files = []
        try:
            for content in ('{"x":1,"x":2}', '{}', '{}', '{}', '{}'):
                f = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
                f.write(content)
                f.close()
                files.append(f.name)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = gate.main(["--taxonomy-plan", files[0], "--taxonomy-context", files[1],
                                  "--rate-plan", files[2], "--rate-context", files[3], "--library", files[4]])
            self.assertEqual(code, 3)
            self.assertNotIn('"x"', stdout.getvalue())
            self.assertNotIn('"2"', stdout.getvalue())
        finally:
            for name in files:
                Path(name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
