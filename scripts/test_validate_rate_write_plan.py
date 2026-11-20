#!/usr/bin/env python3
"""Offline contract tests using fictional, explicit examples only.

These examples do not establish a real approval, source capture, Moka mapping,
identity, authorization, or actual write. Run with:
    PYTHONDONTWRITEBYTECODE=1 python3 test_validate_rate_write_plan.py
"""
import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
import validate_rate_write_plan as gate


RATE_VALUE = "60 USD < Expected Rate ≤ 100 USD"
RATE_LABEL = "Expected hourly rate in USD"
STANDARD_V11_INTERVALS = (
    ("0 USD ≤ Expected Rate ≤ 10 USD", "0", "10", True, True),
    ("10 USD < Expected Rate ≤ 20 USD", "10", "20", False, True),
    ("20 USD < Expected Rate ≤ 30 USD", "20", "30", False, True),
    ("30 USD < Expected Rate ≤ 60 USD", "30", "60", False, True),
    ("60 USD < Expected Rate ≤ 100 USD", "60", "100", False, True),
)


def example():
    """Return fresh, completely fictional data; example.test is not a service."""
    candidate = {"moka_id": "A1", "name": "Alice", "match_status": "verified"}
    plan = {
        "candidate": copy.deepcopy(candidate),
        "taxonomy_version": "v1",
        "expected_rate": "80",
        "rate_label": RATE_LABEL,
        "evidence": [{"source_id": "S1", "locator": "profile-rate", "excerpt": "80"}],
        "changes": [{
            "system": "moka", "record_id": "A1", "field": "candidate_custom_tags",
            "operation": "add", "tag_group": "rate", "tag_value": RATE_VALUE,
            "remote_tag_id": "T5",
        }],
    }
    context = {
        "candidate": copy.deepcopy(candidate),
        "allowed_record_ids": {"moka": ["A1"]},
        "allowed_fields": {"moka": ["candidate_custom_tags"]},
        "allowed_operations": {"moka": ["add"]},
        "current_tags_verified": True,
        "current_tags": {"moka": [{"tag_group": "language", "tag_value": "English"}]},
        "rate_intervals_complete_verified": True,
        "rate_intervals_verification_reference": "DEMO-COMPLETE-RATE-BANDS-REF",
        "sources": [{
            "source_id": "S1", "system": "moka", "record_id": "A1",
            "url": "https://example.test/candidates/application/A1/info",
            "captured_at": "2026-01-01T00:00:00Z",
            "segments": [{"locator": "profile-rate", "text": RATE_LABEL + ": 80"}],
        }],
    }
    library = {
        "taxonomy_version": "v1",
        "current_approved_version_verified": True,
        "active_status_verified": True,
        "moka_id_mapping_verified": True,
        "approval_reference": "fictional example of an approved documented source",
        "tags": [
            {"tag_group": "rate", "tag_value": label, "status": "Active",
             "moka_tag_id": f"T{index}", "currency": "USD", "period": "hour",
             "lower": lower, "upper": upper, "lower_inclusive": lower_inclusive,
             "upper_inclusive": upper_inclusive}
            for index, (label, lower, upper, lower_inclusive, upper_inclusive)
            in enumerate(STANDARD_V11_INTERVALS, 1)
        ],
    }
    return plan, context, library


def legacy_example():
    """Retain the original one-band v1 fixture and its legacy tests."""
    plan, context, library = example()
    library["tags"] = [library["tags"][-1]]
    context.pop("rate_intervals_complete_verified")
    context.pop("rate_intervals_verification_reference")
    return plan, context, library


def with_rate(plan, context, rate):
    """Change both the claimed amount and its fictional verbatim source."""
    plan["expected_rate"] = rate
    plan["evidence"][0]["excerpt"] = str(rate)
    context["sources"][0]["segments"][0]["text"] = RATE_LABEL + ": " + str(rate)


def second_rate_tag(lower="100", upper="150", lower_inclusive=False):
    operator = "≤" if lower_inclusive else "<"
    return {
        "tag_group": "rate",
        "tag_value": f"{lower} USD {operator} Expected Rate ≤ {upper} USD",
        "status": "Active", "moka_tag_id": "T6", "currency": "USD", "period": "hour",
        "lower": lower, "upper": upper, "lower_inclusive": lower_inclusive,
        "upper_inclusive": True,
    }


class RateWritePlanTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.context, self.library = legacy_example()

    def check(self, ready):
        before = copy.deepcopy((self.plan, self.context, self.library))
        result = gate.validate(self.plan, self.context, self.library)
        self.assertIsInstance(result, dict)
        self.assertIs(result.get("ready_for_confirmation"), ready, result)
        self.assertIs(result.get("authorized"), False, result)
        self.assertIs(result.get("executed"), False, result)
        self.assertIsInstance(result.get("errors"), list, result)
        if ready:
            self.assertEqual(result["errors"], [], result)
        else:
            self.assertTrue(result["errors"], result)
            self.assertTrue(all(isinstance(code, str) and code.strip() for code in result["errors"]), result)
        self.assertEqual((self.plan, self.context, self.library), before, "validation must not mutate inputs")
        return result

    def test_valid_only_moka_rate_is_ready_but_never_authorized_or_executed(self):
        self.check(True)
        self.check(True)

    def test_validate_does_not_use_network(self):
        with patch("socket.socket", side_effect=AssertionError("unexpected network access")):
            self.check(True)

    def test_identity_must_be_verified_in_both_plan_and_context(self):
        for target in ("plan", "context"):
            for status in ("unverified", "", None, True):
                with self.subTest(target=target, status=status):
                    self.plan, self.context, self.library = legacy_example()
                    (self.plan if target == "plan" else self.context)["candidate"]["match_status"] = status
                    self.check(False)

    def test_candidate_ids_must_match_and_be_present(self):
        for target, value in (("plan", "OTHER"), ("context", "OTHER"), ("plan", ""), ("context", None)):
            with self.subTest(target=target, value=value):
                self.plan, self.context, self.library = legacy_example()
                (self.plan if target == "plan" else self.context)["candidate"]["moka_id"] = value
                self.check(False)

    def test_record_cannot_differ_from_candidate_even_if_allowlisted(self):
        self.plan["changes"][0]["record_id"] = "OTHER"
        self.context["allowed_record_ids"]["moka"].append("OTHER")
        self.check(False)

    def test_unapproved_record_field_and_operation_are_blocked(self):
        cases = (("allowed_record_ids", "A1"), ("allowed_fields", "candidate_custom_tags"),
                 ("allowed_operations", "add"))
        for mapping, value in cases:
            with self.subTest(mapping=mapping):
                self.plan, self.context, self.library = legacy_example()
                self.context[mapping]["moka"].remove(value)
                self.check(False)
        for field, value in (("field", "unapproved_field"), ("operation", "delete")):
            with self.subTest(field=field):
                self.plan, self.context, self.library = legacy_example()
                self.plan["changes"][0][field] = value
                self.check(False)

    def test_only_moka_is_allowed_even_when_other_system_is_allowlisted(self):
        self.plan["changes"][0]["system"] = "benchmark"
        for key, value in (("allowed_record_ids", "A1"), ("allowed_fields", "candidate_custom_tags"),
                           ("allowed_operations", "add")):
            self.context[key]["benchmark"] = [value]
        self.context["current_tags"]["benchmark"] = []
        self.check(False)

    def test_unknown_system_is_blocked(self):
        self.plan["changes"][0]["system"] = "not-a-system"
        self.check(False)

    def test_must_verify_current_tags_exactly_true(self):
        for flag in (False, None, "true", 1):
            with self.subTest(flag=flag):
                self.plan, self.context, self.library = legacy_example()
                self.context["current_tags_verified"] = flag
                self.check(False)
        self.plan, self.context, self.library = legacy_example()
        del self.context["current_tags_verified"]
        self.check(False)

    def test_missing_current_tag_data_is_not_treated_as_empty(self):
        for value in (None, {}, {"moka": None}):
            with self.subTest(value=value):
                self.plan, self.context, self.library = legacy_example()
                self.context["current_tags"] = value
                self.check(False)
        self.plan, self.context, self.library = legacy_example()
        del self.context["current_tags"]
        self.check(False)

    def test_same_rate_already_present_is_skipped_not_ready_to_write(self):
        self.context["current_tags"]["moka"].append({"tag_group": "rate", "tag_value": RATE_VALUE})
        self.check(False)

    def test_different_existing_rate_conflicts_even_if_other_tags_are_allowed(self):
        self.context["current_tags"]["moka"].append({
            "tag_group": "rate", "tag_value": "0 USD < Expected Rate ≤ 60 USD",
        })
        self.check(False)

    def test_library_approval_active_status_and_mapping_require_exact_true(self):
        fields = ("current_approved_version_verified", "active_status_verified", "moka_id_mapping_verified")
        for field in fields:
            for flag in (False, None, "true", 1):
                with self.subTest(field=field, flag=flag):
                    self.plan, self.context, self.library = legacy_example()
                    self.library[field] = flag
                    self.check(False)
            with self.subTest(field=field, flag="missing"):
                self.plan, self.context, self.library = legacy_example()
                del self.library[field]
                self.check(False)

    def test_approval_reference_must_be_present(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                self.plan, self.context, self.library = legacy_example()
                self.library["approval_reference"] = value
                self.check(False)
        self.plan, self.context, self.library = legacy_example()
        del self.library["approval_reference"]
        self.check(False)

    def test_taxonomy_version_must_match(self):
        self.plan["taxonomy_version"] = "other-v1"
        self.check(False)

    def test_library_without_rate_cannot_authorize_plan(self):
        self.library["tags"] = [{"tag_group": "language", "tag_value": "English",
                                  "status": "Active", "moka_tag_id": "L1"}]
        self.check(False)

    def test_selected_tag_must_be_active(self):
        for status in ("Inactive", "active", "", None):
            with self.subTest(status=status):
                self.plan, self.context, self.library = legacy_example()
                self.library["tags"][0]["status"] = status
                self.check(False)

    def test_exact_rate_tag_value_and_real_mapped_id_must_match(self):
        for field, value in (("tag_group", "language"), ("tag_value", "free-text rate"),
                             ("tag_value", RATE_VALUE + " "), ("remote_tag_id", "NOT-T5"),
                             ("remote_tag_id", ""), ("remote_tag_id", None)):
            with self.subTest(field=field, value=value):
                self.plan, self.context, self.library = legacy_example()
                self.plan["changes"][0][field] = value
                self.check(False)
        self.plan, self.context, self.library = legacy_example()
        self.library["tags"][0]["moka_tag_id"] = ""
        self.check(False)

    def test_duplicate_library_mapping_is_ambiguous(self):
        self.library["tags"].append(copy.deepcopy(self.library["tags"][0]))
        self.check(False)

    def test_evidence_is_required(self):
        for evidence in ([], None):
            with self.subTest(evidence=evidence):
                self.plan, self.context, self.library = legacy_example()
                self.plan["evidence"] = evidence
                self.check(False)
        self.plan, self.context, self.library = legacy_example()
        del self.plan["evidence"]
        self.check(False)

    def test_missing_or_wrong_citation_is_blocked(self):
        for key, value in (("source_id", "not-S1"), ("locator", "not-profile-rate"),
                           ("excerpt", "not-verbatim"), ("excerpt", "")):
            with self.subTest(key=key):
                self.plan, self.context, self.library = legacy_example()
                self.plan["evidence"][0][key] = value
                self.check(False)

    def test_source_must_belong_to_this_candidate_and_moka(self):
        for key, value in (("record_id", "OTHER"), ("system", "benchmark")):
            with self.subTest(key=key):
                self.plan, self.context, self.library = legacy_example()
                self.context["sources"][0][key] = value
                self.check(False)

    def test_source_and_locator_must_be_unambiguous(self):
        self.context["sources"].append(copy.deepcopy(self.context["sources"][0]))
        self.check(False)
        self.plan, self.context, self.library = legacy_example()
        self.context["sources"][0]["segments"].append(
            {"locator": "profile-rate", "text": "Expected hourly rate in USD: 90"})
        self.check(False)

    def test_expected_rate_cannot_be_unsupported_by_evidence(self):
        self.plan["expected_rate"] = "85"
        self.check(False)

    def test_rate_digits_cannot_be_just_a_substring_of_another_number(self):
        self.context["sources"][0]["segments"][0]["text"] = RATE_LABEL + ": 180"
        self.check(False)

    def test_quote_must_support_rate_and_label_not_an_unrelated_number(self):
        self.context["sources"][0]["segments"][0]["text"] = "Years of experience: 80"
        self.check(False)

    def test_rate_label_must_match_the_source(self):
        self.plan["rate_label"] = "Expected annual rate in EUR"
        self.check(False)

    def test_rate_must_be_finite_numeric_not_boolean(self):
        for value in ("not-a-number", "NaN", "Infinity", "-Infinity", "", None, True, False):
            with self.subTest(value=value):
                self.plan, self.context, self.library = legacy_example()
                self.plan["expected_rate"] = value
                self.check(False)

    def test_exact_range_boundaries(self):
        for rate, ready in (("59.999", False), ("60", False), ("60.001", True),
                            ("80", True), ("100", True), ("100.001", False)):
            with self.subTest(rate=rate):
                self.plan, self.context, self.library = legacy_example()
                with_rate(self.plan, self.context, rate)
                self.check(ready)

    def test_neighboring_nonoverlapping_intervals_are_valid(self):
        self.library["tags"].append(second_rate_tag())
        self.check(True)

    def test_overlapping_intervals_are_blocked_even_if_this_rate_is_outside_overlap(self):
        self.library["tags"].append(second_rate_tag("90", "150"))
        self.check(False)

    def test_rate_in_overlapping_intervals_is_blocked(self):
        self.library["tags"].append(second_rate_tag("90", "150"))
        with_rate(self.plan, self.context, "95")
        self.check(False)

    def test_shared_inclusive_boundary_is_an_overlap(self):
        self.library["tags"].append(second_rate_tag("100", "150", lower_inclusive=True))
        self.check(False)

    def test_rate_at_shared_inclusive_boundary_is_blocked(self):
        self.library["tags"].append(second_rate_tag("100", "150", lower_inclusive=True))
        with_rate(self.plan, self.context, "100")
        self.check(False)

    def test_bad_interval_metadata_cannot_be_used(self):
        for key, value in (("lower", "not-a-number"), ("upper", "NaN"), ("lower", "101"),
                           ("lower_inclusive", "false"), ("upper_inclusive", 1)):
            with self.subTest(key=key, value=value):
                self.plan, self.context, self.library = legacy_example()
                self.library["tags"][0][key] = value
                self.check(False)

    def test_non_usd_or_non_hour_rate_is_blocked(self):
        for key, value in (("currency", "EUR"), ("currency", ""), ("period", "month"),
                           ("period", "day"), ("period", "")):
            with self.subTest(key=key, value=value):
                self.plan, self.context, self.library = legacy_example()
                self.library["tags"][0][key] = value
                self.check(False)

    def test_no_extra_changes_even_if_they_are_otherwise_allowlisted(self):
        self.plan["changes"].append(copy.deepcopy(self.plan["changes"][0]))
        self.check(False)
        self.plan, self.context, self.library = legacy_example()
        extra = copy.deepcopy(self.plan["changes"][0])
        extra.update(tag_group="language", tag_value="English", remote_tag_id="L1")
        self.plan["changes"].append(extra)
        self.library["tags"].append({"tag_group": "language", "tag_value": "English",
                                     "status": "Active", "moka_tag_id": "L1"})
        self.context["current_tags"]["moka"] = []
        self.check(False)

    def test_empty_change_list_is_not_ready(self):
        self.plan["changes"] = []
        self.check(False)

    def test_malformed_roots_fail_closed_instead_of_raising(self):
        for which in ("plan", "context", "library"):
            for value in (None, [], "not-an-object", 0):
                with self.subTest(which=which, value=value):
                    self.plan, self.context, self.library = legacy_example()
                    setattr(self, which, value)
                    self.check(False)


def v11_example():
    """All names, IDs, references and source content here are fabricated test data."""
    plan, context, library = example()
    for candidate in (plan['candidate'], context['candidate']):
        candidate.update(moka_id='DEMO-APP-1', name='DEMO-PERSON')
    plan['changes'][0]['record_id'] = 'DEMO-APP-1'
    context['allowed_record_ids']['moka'] = ['DEMO-APP-1']
    source = context['sources'][0]
    source['record_id'] = 'DEMO-APP-1'
    source['url'] = 'https://example.invalid/application/DEMO-APP-1/profile'
    plan['taxonomy_version'] = library['taxonomy_version'] = '1.1'
    context.update(current_tag_groups_verified=True,
                   current_tags_verification_reference='DEMO-CURRENT-OLD-TAGS-REF',
                   current_tag_groups_verification_reference='DEMO-CURRENT-GROUPS-REF',
                   rate_intervals_complete_verified=True,
                   rate_intervals_verification_reference='DEMO-VERIFIED-INTERVALS-REF')
    library.update(approval_reference='DEMO-APPROVAL-REF',
                   current_version_verification_reference='DEMO-VERSION-REF',
                   active_status_verification_reference='DEMO-ACTIVE-REF',
                   moka_id_mapping_reference='DEMO-MAPPING-REF')
    library['tags'] = []
    for index, (label, lower, upper, lower_inclusive, upper_inclusive) in enumerate(STANDARD_V11_INTERVALS, 1):
        library['tags'].append({'tag_group': 'rate', 'tag_value': label, 'status': 'Active',
                                'moka_tag_id': f'DEMO-INTERVAL-ID-{index}', 'currency': 'USD',
                                'period': 'hour', 'lower': str(lower), 'upper': str(upper),
                                'lower_inclusive': lower_inclusive, 'upper_inclusive': upper_inclusive})
    library['tags'].append({'tag_group': 'rate', 'tag_value': gate.RATE_EXCEPTION, 'status': 'Active',
                            'moka_tag_id': 'DEMO-EXCEPTION-ID'})
    plan['changes'][0].update(tag_value=gate.RATE_EXCEPTION, remote_tag_id='DEMO-EXCEPTION-ID')
    with_rate(plan, context, '100.01')
    return plan, context, library


class RateV11ExceptionTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.context, self.library = v11_example()

    def check(self, ready, error=None):
        before = copy.deepcopy((self.plan, self.context, self.library))
        result = gate.validate(self.plan, self.context, self.library)
        self.assertIs(result['ready_for_confirmation'], ready, result)
        self.assertFalse(result['authorized'])
        self.assertFalse(result['executed'])
        if error:
            self.assertEqual(result['errors'], [error])
        self.assertEqual((self.plan, self.context, self.library), before)
        return result

    def test_exception_and_normal_values_exact_boundaries(self):
        self.check(True)
        for amount, index in (('0', 0), ('10', 0), ('10.0000001', 1), ('20', 1),
                              ('20.01', 2), ('30', 2), ('30.01', 3), ('60', 3),
                              ('60.0001', 4), ('100', 4)):
            with self.subTest(amount=amount):
                self.plan, self.context, self.library = v11_example()
                with_rate(self.plan, self.context, amount)
                tag = self.library['tags'][index]
                self.plan['changes'][0].update(tag_value=tag['tag_value'], remote_tag_id=tag['moka_tag_id'])
                self.check(True)
                self.plan['changes'][0].update(tag_value=gate.RATE_EXCEPTION, remote_tag_id='DEMO-EXCEPTION-ID')
                self.check(False)
        self.plan, self.context, self.library = v11_example()
        with_rate(self.plan, self.context, '100.0000000000000000000000000000000000001')
        self.check(True)

    def test_invalid_missing_negative_or_wrong_units_block(self):
        for amount in (None, '', 'unknown', 'N/A', '-0.01', 'NaN', 'Infinity', True, '101 USD', '101 EUR/hour'):
            with self.subTest(amount=amount):
                self.plan, self.context, self.library = v11_example()
                with_rate(self.plan, self.context, amount)
                self.check(False)
        for rate_label in ('', 'Expected hourly rate in EUR', 'Expected monthly rate in USD', 'Expected rate'):
            with self.subTest(label=rate_label):
                self.plan, self.context, self.library = v11_example()
                self.plan['rate_label'] = rate_label
                self.check(False)

    def test_exact_exception_active_and_mapped(self):
        for mutation in ('missing', 'inactive', 'blank_id', 'placeholder_id', 'wrong_id', 'wrong_label', 'unapproved'):
            with self.subTest(mutation=mutation):
                self.plan, self.context, self.library = v11_example()
                tag = self.library['tags'][-1]
                if mutation == 'missing': self.library['tags'].pop()
                if mutation == 'inactive': tag['status'] = 'Inactive'
                if mutation == 'blank_id': tag['moka_tag_id'] = ''
                if mutation == 'placeholder_id':
                    tag['moka_tag_id'] = self.plan['changes'][0]['remote_tag_id'] = 'unknown'
                if mutation == 'wrong_id': self.plan['changes'][0]['remote_tag_id'] = 'DEMO-WRONG'
                if mutation == 'wrong_label': tag['tag_value'] = 'Rate not included'
                if mutation == 'unapproved': self.library['current_approved_version_verified'] = False
                self.check(False)

    def test_full_five_exact_active_boundaries_and_unique_ids_required(self):
        for index in range(5):
            for mutation in ('missing', 'inactive', 'blank_id', 'wrong_id_shared', 'altered_boundary', 'altered_label'):
                with self.subTest(index=index, mutation=mutation):
                    self.plan, self.context, self.library = v11_example()
                    tag = self.library['tags'][index]
                    if mutation == 'missing': self.library['tags'].pop(index)
                    if mutation == 'inactive': tag['status'] = 'Inactive'
                    if mutation == 'blank_id': tag['moka_tag_id'] = ''
                    if mutation == 'wrong_id_shared': tag['moka_tag_id'] = 'DEMO-EXCEPTION-ID'
                    if mutation == 'altered_boundary': tag['upper'] = str(Decimal(tag['upper']) + 1)
                    if mutation == 'altered_label': tag['tag_value'] += ' '
                    self.check(False)
        self.plan, self.context, self.library = v11_example()
        self.library['tags'].append({'tag_group': 'language', 'tag_value': 'DEMO', 'status': 'Active',
                                     'moka_tag_id': 'DEMO-INTERVAL-ID-1'})
        self.check(False, 'TAG_AMBIGUOUS')

    def test_extra_interval_and_overlap_are_blocked(self):
        for tag in (second_rate_tag('90', '150'), second_rate_tag('100', '150', True),
                    second_rate_tag('100', '150', False), second_rate_tag('200', '300', False)):
            with self.subTest(tag=tag):
                self.plan, self.context, self.library = v11_example()
                self.library['tags'].append(tag)
                self.check(False)

    def test_interval_verification_and_references_are_required(self):
        for flag in (False, None, 1, 'true'):
            self.context['rate_intervals_complete_verified'] = flag
            self.check(False, 'RATE_INTERVALS_UNVERIFIED')
        self.plan, self.context, self.library = v11_example()
        for value in ('', None, '   ', 'unknown', 'n/a'):
            self.context['rate_intervals_verification_reference'] = value
            self.check(False, 'RATE_INTERVALS_UNVERIFIED')

    def test_exception_cannot_bypass_provenance_by_changing_version_string(self):
        self.plan['taxonomy_version'] = self.library['taxonomy_version'] = 'DEMO-OTHER-VERSION'
        self.check(True)
        self.context['current_tag_groups_verified'] = False
        self.check(False, 'CURRENT_TAG_GROUPS_UNVERIFIED')
        self.context['current_tag_groups_verified'] = True
        self.library['moka_id_mapping_reference'] = ''
        self.check(False, 'MOKA_MAPPING_UNVERIFIED')

    def test_v11_context_and_library_provenance_required_for_normal_and_exception(self):
        cases = [('context', 'current_tags_verified', 'CURRENT_TAGS_UNVERIFIED'),
                 ('context', 'current_tags_verification_reference', 'CURRENT_TAGS_UNVERIFIED'),
                 ('context', 'current_tag_groups_verified', 'CURRENT_TAG_GROUPS_UNVERIFIED'),
                 ('context', 'current_tag_groups_verification_reference', 'CURRENT_TAG_GROUPS_UNVERIFIED'),
                 ('library', 'current_version_verification_reference', 'LIBRARY_NOT_APPROVED'),
                 ('library', 'active_status_verification_reference', 'ACTIVE_STATUS_UNVERIFIED'),
                 ('library', 'moka_id_mapping_reference', 'MOKA_MAPPING_UNVERIFIED')]
        for mode in ('ordinary', 'exception'):
            for owner, field, error in cases:
                for value in (None, False, ''):
                    with self.subTest(mode=mode, field=field, value=value):
                        self.plan, self.context, self.library = v11_example()
                        if mode == 'ordinary':
                            with_rate(self.plan, self.context, '80')
                            tag = self.library['tags'][4]
                            self.plan['changes'][0].update(tag_value=tag['tag_value'], remote_tag_id=tag['moka_tag_id'])
                        (self.context if owner == 'context' else self.library)[field] = value
                        self.check(False, error)

    def test_exception_does_not_block_ordinary_value_when_it_is_absent_or_unapproved(self):
        for mode in ('missing', 'inactive', 'no_id'):
            self.plan, self.context, self.library = v11_example()
            with_rate(self.plan, self.context, '100')
            tag = self.library['tags'][4]
            self.plan['changes'][0].update(tag_value=tag['tag_value'], remote_tag_id=tag['moka_tag_id'])
            if mode == 'missing': self.library['tags'].pop()
            if mode == 'inactive': self.library['tags'][-1]['status'] = 'Inactive'
            if mode == 'no_id': self.library['tags'][-1]['moka_tag_id'] = ''
            self.check(True)

    def test_cli_decimal_numeric_value_is_not_rounded(self):
        amount = '100.0000000000000000000000000000000000001'
        with_rate(self.plan, self.context, Decimal(amount))
        encoded = [json.dumps(x, default=str) for x in (self.plan, self.context, self.library)]
        encoded[0] = encoded[0].replace('"expected_rate": "' + amount + '"', '"expected_rate": ' + amount)
        stdout = io.StringIO()
        with patch('sys.argv', ['gate', '--plan', 'DEMO', '--context', 'DEMO', '--library', 'DEMO']), \
             patch('builtins.open', side_effect=[io.StringIO(s) for s in encoded]), redirect_stdout(stdout):
            code = gate.main()
        self.assertEqual(code, 0, stdout.getvalue())
        self.assertTrue(json.loads(stdout.getvalue())['ready_for_confirmation'])

    def test_v11_programmatic_float_is_blocked_because_precision_may_be_lost(self):
        self.plan['expected_rate'] = 100.01
        self.check(False, 'RATE_PRECISION_UNVERIFIED')
        self.plan, self.context, self.library = v11_example()
        self.library['tags'][0]['upper'] = 10.0
        self.check(False, 'RATE_PRECISION_UNVERIFIED')
        self.plan, self.context, self.library = v11_example()
        self.plan['taxonomy_version'] = self.library['taxonomy_version'] = 'DEMO-OLDER'
        self.plan['expected_rate'] = 100.01
        self.check(False, 'RATE_PRECISION_UNVERIFIED')  # exception is always exact
        # Ordinary legacy floats retain their existing behavior.
        self.plan, self.context, self.library = legacy_example()
        with_rate(self.plan, self.context, 80.0)
        self.check(True)

    def test_batch_cannot_bypass_exactness_and_decimal_strings_work(self):
        from validate_rate_batch import validate_batch
        data = {'items': [{'plan': self.plan, 'context': self.context}]}
        result = validate_batch(data, self.library)
        self.assertEqual(result['results'][0]['status'], 'ready')
        self.plan['expected_rate'] = 100.01  # as produced by a binary-float JSON parser
        result = validate_batch(data, self.library)
        self.assertEqual(result['results'][0]['status'], 'blocked')
        self.assertIn('RATE_PRECISION_UNVERIFIED', result['results'][0]['errors'])
        self.assertFalse(result['authorized'])
        self.assertFalse(result['executed'])


class RateSafetyRegressionTests(unittest.TestCase):
    """Fully fabricated inputs prove structural behavior, not real-world truth or access."""

    def make_case(self, mode):
        if mode == 'legacy':
            return legacy_example()
        plan, context, library = v11_example()
        if mode == 'ordinary':
            with_rate(plan, context, '80')
            tag = library['tags'][4]
            plan['changes'][0].update(tag_value=tag['tag_value'], remote_tag_id=tag['moka_tag_id'])
        return plan, context, library

    def check_case(self, case, ready, error=None):
        before = copy.deepcopy(case)
        result = gate.validate(*case)
        self.assertIs(result['ready_for_confirmation'], ready, result)
        self.assertIs(result['authorized'], False, result)
        self.assertIs(result['executed'], False, result)
        if error is not None:
            self.assertEqual(result['errors'], [error])
        self.assertEqual(case, before)
        return result

    def check_batch(self, case, ready, error=None):
        from validate_rate_batch import validate_batch
        plan, context, library = case
        data = {'items': [{'plan': plan, 'context': context}]}
        with patch('socket.socket', side_effect=AssertionError('no network access')):
            result = validate_batch(data, library)
        self.assertIs(result['all_ready'], ready, result)
        self.assertEqual(result['results'][0]['status'], 'ready' if ready else 'blocked', result)
        self.assertIs(result['authorized'], False)
        self.assertIs(result['executed'], False)
        if error is not None:
            self.assertIn(error, result['results'][0]['errors'])

    def test_unknown_current_groups_block_single_and_batch_even_if_claimed_verified(self):
        from validate_taxonomy_plan import UNKNOWN_GROUPS as TAXONOMY_UNKNOWN_GROUPS
        self.assertEqual(gate.UNKNOWN_GROUPS, TAXONOMY_UNKNOWN_GROUPS)
        unknowns = tuple(sorted(TAXONOMY_UNKNOWN_GROUPS)) + (
            '  OTHER  ', 'ＯＴＨＥＲ　ＧＲＯＵＰ', 'UNCLASSIFIED', 'not   classified', 'Ｎ／Ａ')
        for mode in ('legacy', 'ordinary', 'exception'):
            for group in unknowns:
                with self.subTest(mode=mode, group=group):
                    case = self.make_case(mode)
                    case[1]['current_tags']['moka'][0]['tag_group'] = group
                    self.check_case(case, False, 'CURRENT_TAG_GROUP_UNKNOWN')
                    self.check_batch(case, False, 'CURRENT_TAG_GROUP_UNKNOWN')
            for group in ('', '  ', None):
                with self.subTest(mode=mode, group=group):
                    case = self.make_case(mode)
                    case[1]['current_tags']['moka'][0]['tag_group'] = group
                    self.check_case(case, False, 'CURRENT_TAGS_INVALID')
                    self.check_batch(case, False, 'CURRENT_TAGS_INVALID')

    def test_specific_other_groups_remain_allowed_and_existing_rate_uses_nfkc(self):
        for mode in ('legacy', 'ordinary', 'exception'):
            for group in ('country', 'knowledge domain', 'other projects', 'custom rate category', '项目类型'):
                with self.subTest(mode=mode, group=group):
                    case = self.make_case(mode)
                    case[1]['current_tags']['moka'][0]['tag_group'] = group
                    self.check_case(case, True)
                    self.check_batch(case, True)
            case = self.make_case(mode)
            case[1]['current_tags']['moka'][0]['tag_group'] = ' ＲＡＴＥ '
            self.check_case(case, False, 'EXISTING_RATE_TAG')

    def test_v11_standard_complete_set_passes_in_both_modes(self):
        expected = {label: (Decimal(lower), Decimal(upper), li, ui)
                    for label, lower, upper, li, ui in STANDARD_V11_INTERVALS}
        self.assertEqual(gate.V11_INTERVALS, expected)
        for mode in ('ordinary', 'exception'):
            for version in ('1.1', 'v1.1', ' V1.1 '):
                with self.subTest(mode=mode, version=version):
                    case = self.make_case(mode)
                    case[0]['taxonomy_version'] = case[2]['taxonomy_version'] = version
                    self.check_case(case, True)
                    self.check_batch(case, True)

    def test_v11_malformed_incomplete_or_extra_bands_block_both_modes(self):
        for mode in ('ordinary', 'exception'):
            for mutation in ('missing', 'inactive', 'typo', 'changed_spelling', 'upper_to_120', 'upper_metadata',
                             'wrong_inclusive', 'wrong_unit', 'wrong_period', 'overlap', 'extra'):
                with self.subTest(mode=mode, mutation=mutation):
                    case = self.make_case(mode)
                    tags = case[2]['tags']
                    if mutation == 'missing': tags.pop(1)
                    if mutation == 'inactive': tags[1]['status'] = 'Inactive'
                    if mutation == 'typo': tags[1]['tag_value'] = tags[1]['tag_value'].replace('Expected', 'Expexted')
                    if mutation == 'changed_spelling': tags[1]['tag_value'] = tags[1]['tag_value'].replace('10 USD', '10.0 USD', 1)
                    if mutation == 'upper_to_120':
                        tags[4]['upper'] = '120'
                        tags[4]['tag_value'] = '60 USD < Expected Rate ≤ 120 USD'
                        if mode == 'ordinary':
                            case[0]['changes'][0]['tag_value'] = tags[4]['tag_value']
                    if mutation == 'upper_metadata': tags[4]['upper'] = '120'
                    if mutation == 'wrong_inclusive': tags[0]['upper_inclusive'] = False
                    if mutation == 'wrong_unit': tags[1]['currency'] = 'EUR'
                    if mutation == 'wrong_period': tags[1]['period'] = 'month'
                    if mutation == 'overlap': tags.append(second_rate_tag('90', '150'))
                    if mutation == 'extra': tags.append(second_rate_tag('100', '150'))
                    self.check_case(case, False)
                    self.check_batch(case, False)

    def test_v11_high_precision_boundaries_are_never_rounded(self):
        cases = (
            ('0', 0), ('9.99999999999999999999999999999999999', 0), ('10', 0),
            ('10.00000000000000000000000000000000001', 1), ('20', 1),
            ('20.00000000000000000000000000000000001', 2), ('30', 2),
            ('30.00000000000000000000000000000000001', 3), ('60', 3),
            ('60.00000000000000000000000000000000001', 4), ('100', 4),
            ('100.00000000000000000000000000000000001', 5),
        )
        for amount, index in cases:
            with self.subTest(amount=amount):
                case = self.make_case('exception')
                with_rate(case[0], case[1], amount)
                tag = case[2]['tags'][index]
                case[0]['changes'][0].update(tag_value=tag['tag_value'], remote_tag_id=tag['moka_tag_id'])
                self.check_case(case, True)
                self.check_batch(case, True)

    def test_v11_complete_claim_and_reference_required_for_both_modes(self):
        for mode in ('ordinary', 'exception'):
            for field, values in (
                    ('rate_intervals_complete_verified', (False, None, 1, 'true')),
                    ('rate_intervals_verification_reference', ('', None, 'unknown', 'Ｎ／Ａ', False))):
                for value in values:
                    with self.subTest(mode=mode, field=field, value=value):
                        case = self.make_case(mode)
                        case[1][field] = value
                        self.check_case(case, False, 'RATE_INTERVALS_UNVERIFIED')
                        self.check_batch(case, False, 'RATE_INTERVALS_UNVERIFIED')
                case = self.make_case(mode)
                del case[1][field]
                self.check_case(case, False, 'RATE_INTERVALS_UNVERIFIED')
                self.check_batch(case, False, 'RATE_INTERVALS_UNVERIFIED')

    def test_id_uniqueness_is_checked_across_all_groups_and_statuses(self):
        for mode in ('ordinary', 'exception'):
            for index in range(6):
                for status in ('Active', 'Inactive'):
                    with self.subTest(mode=mode, index=index, status=status):
                        case = self.make_case(mode)
                        remote_id = case[2]['tags'][index]['moka_tag_id']
                        case[2]['tags'].append({'tag_group': 'language', 'tag_value': 'DEMO',
                                                'status': status, 'moka_tag_id': remote_id})
                        self.check_case(case, False, 'TAG_AMBIGUOUS')
                        self.check_batch(case, False, 'TAG_AMBIGUOUS')
            case = self.make_case(mode)
            case[2]['tags'].extend([
                {'tag_group': 'language', 'tag_value': 'A', 'moka_tag_id': 'OTHER-DUPLICATE'},
                {'tag_group': 'country', 'tag_value': 'B', 'moka_tag_id': 'OTHER-DUPLICATE'},
            ])
            self.check_case(case, False, 'TAG_AMBIGUOUS')
        case = self.make_case('legacy')
        case[2]['tags'].append({'tag_group': 'language', 'tag_value': 'DEMO',
                                'status': 'Inactive', 'moka_tag_id': 'T5'})
        self.check_case(case, False, 'TAG_AMBIGUOUS')
        self.check_batch(case, False, 'TAG_AMBIGUOUS')

    def test_fictional_default_templates_and_unverified_access_stay_blocked(self):
        templates = Path(__file__).resolve().parents[1] / 'templates'
        library = json.loads((templates / 'rate-library.example.json').read_text(encoding='utf-8'))
        for prefix, context_name in (('rate-plan', 'rate-evidence-context'),
                                     ('rate-exception-plan', 'rate-exception-context')):
            plan = json.loads((templates / (prefix + '.example.json')).read_text(encoding='utf-8'))
            context = json.loads((templates / (context_name + '.example.json')).read_text(encoding='utf-8'))
            self.check_case((plan, context, library), False)
        from validate_rate_batch import validate_batch
        batch = json.loads((templates / 'rate-batch.example.json').read_text(encoding='utf-8'))
        result = validate_batch(batch, library)
        self.assertFalse(result['all_ready'])
        self.assertTrue(all(item['status'] == 'blocked' for item in result['results']))
        self.assertFalse(result['authorized'])
        self.assertFalse(result['executed'])
        for mode in ('ordinary', 'exception'):
            for field in ('current_tags_verified', 'current_tag_groups_verified',
                          'rate_intervals_complete_verified'):
                case = self.make_case(mode)
                case[1][field] = False
                self.check_case(case, False)
                self.check_batch(case, False)
            for field in ('allowed_record_ids', 'allowed_fields', 'allowed_operations'):
                case = self.make_case(mode)
                case[1][field]['moka'] = []
                self.check_case(case, False)
                self.check_batch(case, False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
