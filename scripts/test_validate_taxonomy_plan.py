#!/usr/bin/env python3
"""Fictional fixtures only. No network, Moka access, authorization or writes."""
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

sys.dont_write_bytecode = True
import validate_taxonomy_plan as gate


def fixture():
    candidate = {"moka_id": "DEMO-RECORD-1", "match_status": "verified"}
    quote = {"source_id": "DEMO-SOURCE-1", "locator": "DEMO-PARAGRAPH-1", "excerpt": "DEMO continuous evidence"}
    pairs = [("language", "english"), ("language", "spanish"), ("country", "japan"),
             ("country", "singapore"), ("project category", "translation"),
             ("project category", "annotation"), ("knowledge domain", "biology"),
             ("knowledge domain", "chemistry"), ("tier", "tier 3"), ("tier", "tier 4")]
    library = {"taxonomy_version": "DEMO-VERSION", "current_approved_version_verified": True,
               "active_status_verified": True, "moka_id_mapping_verified": True,
               "approval_reference": "DEMO-APPROVAL-REF", "current_version_verification_reference": "DEMO-CURRENT-REF",
               "active_status_verification_reference": "DEMO-ACTIVE-REF", "moka_id_mapping_reference": "DEMO-MAPPING-REF",
               "tags": [{"tag_group": g, "tag_value": v, "status": "Active", "moka_tag_id": "DEMO-TAG-" + str(i)}
                        for i, (g, v) in enumerate(pairs)]}
    context = {"candidate": copy.deepcopy(candidate), "allowed_record_ids": {"moka": [candidate["moka_id"]]},
               "allowed_fields": {"moka": ["DEMO-TAG-FIELD"]}, "allowed_operations": {"moka": ["add"]},
               "current_tags": {"moka": []}, "current_tags_verified": True, "current_tag_groups_verified": True,
               "current_tags_verification_reference": "DEMO-CURRENT-TAGS-REF",
               "current_tag_groups_verification_reference": "DEMO-CURRENT-GROUPS-REF",
               "project_category_selection_type": "multi", "project_category_decision_reference": "DEMO-PC-DECISION",
               "approved_rubric": None,
               "sources": [{"source_id": "DEMO-SOURCE-1", "system": "moka", "record_id": candidate["moka_id"],
                            "url": "https://example.invalid/DEMO-PAGE", "captured_at": "DEMO-CAPTURE-ONLY",
                            "segments": [{"locator": quote["locator"], "text": "Prefix DEMO continuous evidence suffix"}]}]}
    change = {"system": "moka", "record_id": candidate["moka_id"], "field": "DEMO-TAG-FIELD", "operation": "add",
              "tag_group": "language", "tag_value": "english", "remote_tag_id": "DEMO-TAG-0", "evidence": [quote]}
    plan = {"candidate": candidate, "taxonomy_version": "DEMO-VERSION", "changes": [change]}
    return plan, context, library


class TaxonomyTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.context, self.library = fixture()

    def check(self, code=None):
        before = copy.deepcopy((self.plan, self.context, self.library))
        out = gate.validate(self.plan, self.context, self.library)
        self.assertEqual(out, gate.result([] if code is None else [code]))
        self.assertIs(out["authorized"], False)
        self.assertIs(out["executed"], False)
        self.assertEqual((self.plan, self.context, self.library), before)

    def select(self, group, value, append=False):
        change = copy.deepcopy(self.plan["changes"][0])
        tag = next(t for t in self.library["tags"] if (t["tag_group"], t["tag_value"]) == (group, value))
        change.update(tag_group=group, tag_value=value, remote_tag_id=tag["moka_tag_id"])
        if append:
            self.plan["changes"].append(change)
        else:
            self.plan["changes"] = [change]

    def tier(self):
        self.select("tier", "tier 3")
        self.plan["target_project_id"] = "DEMO-PROJECT-1"
        self.context["approved_rubric"] = {"approved": True, "approved_by": "DEMO-OWNER",
            "approval_reference": "DEMO-RUBRIC-APPROVAL", "project_id": "DEMO-PROJECT-1",
            "version": "DEMO-RUBRIC-1", "required_dimensions": list(gate.DIMENSIONS)}
        self.plan["tier_assessment"] = {"status": "assessed", "value": "tier 3", "rubric_version": "DEMO-RUBRIC-1",
            "dimension_evidence": {d: copy.deepcopy(self.plan["changes"][0]["evidence"]) for d in gate.DIMENSIONS}}

    def test_valid_moka_only_without_benchmark(self):
        self.assertNotIn("benchmark_id", self.plan["candidate"])
        self.check()

    def test_missing_identity_and_mismatch(self):
        for val in (None, "", "   ", 123):
            with self.subTest(val=val):
                self.plan["candidate"]["moka_id"] = val
                self.check("IDENTITY_MISMATCH")
        self.plan["candidate"]["moka_id"] = "DEMO-OTHER"
        self.check("IDENTITY_MISMATCH")

    def test_identity_must_be_verified_in_both(self):
        for target in (self.plan, self.context):
            target["candidate"]["match_status"] = "unverified"
            self.check("IDENTITY_UNVERIFIED")
            target["candidate"]["match_status"] = "verified"

    def test_record_allowlist_required(self):
        self.context["allowed_record_ids"]["moka"] = []
        self.check("TARGET_NOT_ALLOWED")

    def test_cross_record_change_rejected(self):
        self.plan["changes"][0]["record_id"] = "DEMO-OTHER"
        self.context["allowed_record_ids"]["moka"].append("DEMO-OTHER")
        self.check("TARGET_NOT_ALLOWED")

    def test_benchmark_change_rejected_even_if_listed(self):
        self.plan["changes"][0]["system"] = "benchmark"
        self.context["allowed_fields"]["benchmark"] = ["DEMO-TAG-FIELD"]
        self.check("TARGET_NOT_ALLOWED")

    def test_field_allowlist_required(self):
        self.context["allowed_fields"]["moka"] = []
        self.check("FIELD_NOT_ALLOWED")

    def test_only_add_and_explicit_operation_scope(self):
        for op in ("set", "delete", "remove", "replace"):
            self.plan["changes"][0]["operation"] = op
            self.context["allowed_operations"]["moka"] = [op]
            self.check("OPERATION_NOT_ALLOWED")
        self.plan["changes"][0]["operation"] = "add"
        self.context["allowed_operations"]["moka"] = []
        self.check("OPERATION_NOT_ALLOWED")

    def test_current_tags_not_read_or_not_referenced(self):
        for value in (False, None, 1, "true"):
            self.context["current_tags_verified"] = value
            self.check("CURRENT_TAGS_UNVERIFIED")
        self.context["current_tags_verified"] = True
        self.context["current_tags_verification_reference"] = ""
        self.check("CURRENT_TAGS_UNVERIFIED")

    def test_current_groups_not_verified_or_not_referenced(self):
        for value in (False, None, 1, "true"):
            self.context["current_tag_groups_verified"] = value
            self.check("CURRENT_TAG_GROUPS_UNVERIFIED")
        self.context["current_tag_groups_verified"] = True
        self.context["current_tag_groups_verification_reference"] = ""
        self.check("CURRENT_TAG_GROUPS_UNVERIFIED")

    def test_other_real_named_group_allowed_without_mutation(self):
        self.context["current_tags"]["moka"] = [{"tag_group": "Rate", "tag_value": "DEMO-RATE"}]
        self.check()

    def test_unknown_groups_cannot_be_other_placeholder(self):
        for group in ("other", " Other ", "UNKNOWN", "其他", "未知", "未分类", "misc"):
            self.context["current_tags"]["moka"] = [{"tag_group": group, "tag_value": "DEMO-TAG"}]
            self.check("CURRENT_TAG_GROUP_UNKNOWN")
        for group in (None, "", "  "):
            self.context["current_tags"]["moka"] = [{"tag_group": group, "tag_value": "DEMO-TAG"}]
            self.check("CURRENT_TAGS_INVALID")

    def test_current_tags_structure_and_empty_value(self):
        for current in ([None], [{}], [{"tag_group": "Rate", "tag_value": ""}]):
            self.context["current_tags"]["moka"] = current
            self.check("CURRENT_TAGS_INVALID")

    def test_existing_value_must_skip_or_block(self):
        self.context["current_tags"]["moka"] = [{"tag_group": "Language", "tag_value": "  ENGLISH  "}]
        self.check("EXISTING_TAG")

    def test_existing_country_conflict_even_when_group_case_differs(self):
        self.select("country", "japan")
        self.context["current_tags"]["moka"] = [{"tag_group": "COUNTRY", "tag_value": "singapore"}]
        self.check("SINGLE_SELECT_CONFLICT")

    def test_country_single_conflict_within_plan(self):
        self.select("country", "japan")
        self.select("country", "singapore", append=True)
        self.check("SINGLE_SELECT_CONFLICT")

    def test_tier_changes_are_blocked_not_classified_as_cross_project_conflicts(self):
        self.tier()
        self.select("tier", "tier 4", append=True)
        self.check("TIER_PROJECT_CONTEXT_UNSUPPORTED")
        self.plan["changes"].pop()
        self.context["current_tags"]["moka"] = [{"tag_group": "tier", "tag_value": "tier 4"}]
        self.check("TIER_PROJECT_CONTEXT_UNSUPPORTED")

    def test_ordinary_changes_allow_existing_different_tier_values(self):
        self.context["current_tags"]["moka"] = [
            {"tag_group": "TIER", "tag_value": "tier 1"},
            {"tag_group": "tier", "tag_value": "tier 3"}]
        self.plan["candidate"]["record_type"] = "candidate_profile"
        self.context["allowed_fields"]["moka"].append("candidate_custom_tags")
        self.plan["changes"][0]["field"] = "candidate_custom_tags"
        self.check()
        self.assertEqual(len(self.plan["changes"]), 1)
        self.assertEqual(self.plan["changes"][0]["tag_group"], "language")

    def test_language_multiselect(self):
        self.select("language", "spanish", append=True)
        self.context["current_tags"]["moka"] = [{"tag_group": "language", "tag_value": "DEMO-OTHER-LANGUAGE"}]
        self.check()

    def test_domain_multiselect(self):
        self.select("knowledge domain", "biology")
        self.select("knowledge domain", "chemistry", append=True)
        self.check()

    def test_project_category_decision_must_be_explicit(self):
        self.select("project category", "translation")
        for val in (None, "", "unknown", "Multi", True):
            self.context["project_category_selection_type"] = val
            self.check("PC_DECISION_REQUIRED")
        self.context["project_category_selection_type"] = "multi"
        self.context["project_category_decision_reference"] = " "
        self.check("PC_DECISION_REQUIRED")

    def test_project_category_single_existing_and_plan_conflicts(self):
        self.select("project category", "translation")
        self.context["project_category_selection_type"] = "single"
        self.context["current_tags"]["moka"] = [{"tag_group": "project category", "tag_value": "annotation"}]
        self.check("SINGLE_SELECT_CONFLICT")
        self.context["current_tags"]["moka"] = []
        self.select("project category", "annotation", append=True)
        self.check("SINGLE_SELECT_CONFLICT")

    def test_project_category_multi_after_owner_decision(self):
        self.select("project category", "translation")
        self.select("project category", "annotation", append=True)
        self.check()

    def test_duplicate_plan_change_rejected(self):
        self.plan["changes"].append(copy.deepcopy(self.plan["changes"][0]))
        self.check("DUPLICATE_CHANGE")

    def test_only_five_groups_and_formal_exact_values(self):
        self.plan["changes"][0]["tag_group"] = "rate"
        self.check("UNKNOWN_TAG_GROUP")
        self.plan["changes"][0]["tag_group"] = "language"
        for value in ("English", "english japan", "DEMO-NEW-TAG"):
            self.plan["changes"][0]["tag_value"] = value
            self.check("TAG_NOT_IN_LIBRARY")

    def test_same_label_in_distinct_groups_is_not_duplicate(self):
        tag = copy.deepcopy(self.library["tags"][0])
        tag.update(tag_group="knowledge domain", moka_tag_id="DEMO-DIFFERENT-ID")
        self.library["tags"].append(tag)
        self.check()
        self.select("knowledge domain", "english", append=True)
        self.check()

    def test_duplicate_formal_pair_is_ambiguous(self):
        tag = copy.deepcopy(self.library["tags"][0])
        tag["moka_tag_id"] = "DEMO-OTHER-ID"
        self.library["tags"].append(tag)
        self.check("TAG_AMBIGUOUS")

    def test_duplicate_real_mapping_ids_are_ambiguous(self):
        self.library["tags"][1]["moka_tag_id"] = self.library["tags"][0]["moka_tag_id"]
        self.check("MOKA_ID_AMBIGUOUS")

    def test_fake_remote_id_does_not_match_verified_library(self):
        self.plan["changes"][0]["remote_tag_id"] = "DEMO-FAKE-ID"
        self.check("REMOTE_TAG_ID_MISMATCH")

    def test_missing_remote_id_fails_closed(self):
        self.plan["changes"][0]["remote_tag_id"] = ""
        self.check("MALFORMED_INPUT")
        self.plan["changes"][0]["remote_tag_id"] = "DEMO-TAG-0"
        self.library["tags"][0]["moka_tag_id"] = None
        self.check("REMOTE_TAG_ID_MISMATCH")

    def test_inactive_or_unverified_tag_rejected(self):
        for status in (None, "Unverified", "Inactive", "active", True):
            self.library["tags"][0]["status"] = status
            self.check("TAG_NOT_ACTIVE")

    def test_unverified_library_rejected_even_if_tags_say_active(self):
        self.library["current_approved_version_verified"] = False
        self.check("LIBRARY_NOT_APPROVED")

    def test_verification_flags_must_be_exact_true(self):
        fields = [("current_approved_version_verified", "LIBRARY_NOT_APPROVED"),
                  ("active_status_verified", "ACTIVE_STATUS_UNVERIFIED"),
                  ("moka_id_mapping_verified", "MOKA_MAPPING_UNVERIFIED")]
        for field, code in fields:
            for flag in (None, False, 1, "true"):
                p, c, lib = fixture()
                lib[field] = flag
                self.assertEqual(gate.validate(p, c, lib), gate.result([code]))

    def test_approval_and_verification_provenance_required(self):
        fields = [("approval_reference", "LIBRARY_NOT_APPROVED"),
                  ("current_version_verification_reference", "LIBRARY_NOT_APPROVED"),
                  ("active_status_verification_reference", "ACTIVE_STATUS_UNVERIFIED"),
                  ("moka_id_mapping_reference", "MOKA_MAPPING_UNVERIFIED")]
        for field, code in fields:
            for value in (None, "", " ", True):
                p, c, lib = fixture()
                lib[field] = value
                self.assertEqual(gate.validate(p, c, lib), gate.result([code]))

    def test_taxonomy_version_must_match(self):
        for version in (None, "", "DEMO-OLD-VERSION"):
            self.plan["taxonomy_version"] = version
            self.check("TAXONOMY_VERSION_MISMATCH")

    def test_source_is_same_moka_record(self):
        self.context["sources"][0]["record_id"] = "DEMO-OTHER"
        self.check("SOURCE_IDENTITY_MISMATCH")
        self.context["sources"][0]["record_id"] = "DEMO-RECORD-1"
        self.context["sources"][0]["system"] = "benchmark"
        self.check("SOURCE_IDENTITY_MISMATCH")

    def test_missing_source_or_wrong_locator(self):
        self.plan["changes"][0]["evidence"][0]["source_id"] = "DEMO-MISSING"
        self.check("EVIDENCE_SOURCE_NOT_FOUND")
        self.plan["changes"][0]["evidence"][0]["source_id"] = "DEMO-SOURCE-1"
        self.plan["changes"][0]["evidence"][0]["locator"] = "DEMO-WRONG-LOCATOR"
        self.check("QUOTE_NOT_VERBATIM")

    def test_evidence_must_be_literal_contiguous_and_nonempty(self):
        quote = self.plan["changes"][0]["evidence"][0]
        for excerpt in ("DEMO invented", "Prefix suffix", "demo continuous evidence"):
            quote["excerpt"] = excerpt
            self.check("QUOTE_NOT_VERBATIM")
        quote["excerpt"] = ""
        self.check("EVIDENCE_MISSING")
        self.plan["changes"][0]["evidence"] = []
        self.check("EVIDENCE_MISSING")

    def test_every_change_requires_own_evidence(self):
        self.select("language", "spanish", append=True)
        self.plan["changes"][1]["evidence"] = []
        self.check("EVIDENCE_MISSING")

    def test_source_url_missing_bad_or_contains_credentials(self):
        for url in ("", "not-a-url", "file:///etc/passwd", "https://user:password@example.invalid/x"):
            self.context["sources"][0]["url"] = url
            self.check("EVIDENCE_SOURCE_INVALID")

    def test_duplicate_source_and_ambiguous_locator(self):
        self.context["sources"].append(copy.deepcopy(self.context["sources"][0]))
        self.check("DUPLICATE_SOURCE_ID")
        self.context["sources"].pop()
        segment = self.context["sources"][0]["segments"][0]
        self.context["sources"][0]["segments"].append(copy.deepcopy(segment))
        self.check("AMBIGUOUS_LOCATOR")

    def test_apparently_complete_historical_tier_is_unsupported(self):
        self.tier()
        self.check("TIER_PROJECT_CONTEXT_UNSUPPORTED")

    def test_no_changes_rejected(self):
        self.plan["changes"] = []
        self.check("NO_CHANGES")

    def test_malformed_inputs_fail_closed_without_leak(self):
        for value in (None, False, 1, "DEMO-SECRET", [], {}):
            out = gate.validate(value, self.context, self.library)
            self.assertFalse(out["ready_for_confirmation"])
            self.assertNotIn("DEMO-SECRET", json.dumps(out))

    def test_extra_benchmark_context_never_required_or_operated(self):
        self.context["allowed_record_ids"]["benchmark"] = []
        self.context["current_tags"]["benchmark"] = []
        self.check()


def upgrade_v11_tier(plan, context, projects):
    """Construct a historical rollup-shaped fixture; never a real platform schema."""
    candidate_id = plan['candidate']['moka_id']
    plan['candidate']['record_type'] = 'candidate_profile'
    context['allowed_fields']['moka'].append('candidate_custom_tags')
    change = plan['changes'][0]
    change['field'] = 'candidate_custom_tags'
    profile_text = f'candidate_moka_id={candidate_id}; record_type=candidate_profile; candidate_custom_tags=[]'
    profile_quote = {'source_id': 'DEMO-PROFILE-SOURCE', 'locator': 'DEMO-PROFILE', 'excerpt': profile_text}
    context['sources'].append({'source_id': 'DEMO-PROFILE-SOURCE', 'system': 'moka',
        'record_id': candidate_id, 'url': 'https://example.invalid/profile', 'captured_at': 'DEMO-ONLY',
        'record_type': 'candidate_profile', 'verified': True, 'verification_reference': 'DEMO-PROFILE-VERIFICATION',
        'segments': [{'locator': profile_quote['locator'], 'text': profile_text}]})
    context['candidate_profile'] = {'moka_id': candidate_id, 'record_type': 'candidate_profile',
        'verified': True, 'verification_reference': 'DEMO-PROFILE-VERIFICATION',
        'identity_evidence': [copy.deepcopy(profile_quote)], 'current_tags_evidence': [copy.deepcopy(profile_quote)]}
    project_ids = [project['project_id'] for project in projects]
    description, statement = 'DEMO-RELEVANT-SCOPE', 'DEMO-ALL-RELEVANT-PROJECTS-COVERED'
    scope_text = (f'candidate_moka_id={candidate_id}; scope_description={description}; coverage_statement={statement}; '
                  f'project_ids={json.dumps(project_ids)}')
    scope_quote = {'source_id': 'DEMO-SCOPE-SOURCE', 'locator': 'DEMO-SCOPE', 'excerpt': scope_text}
    context['sources'].append({'source_id': 'DEMO-SCOPE-SOURCE', 'system': 'moka', 'record_id': candidate_id,
        'url': 'https://example.invalid/projects', 'captured_at': 'DEMO-ONLY', 'record_type': 'candidate_projects',
        'verified': True, 'verification_reference': 'DEMO-SCOPE-VERIFICATION',
        'segments': [{'locator': scope_quote['locator'], 'text': scope_text}]})
    scope = {'candidate_moka_id': candidate_id, 'scope_description': description, 'scope_verified': True,
        'scope_reference': 'DEMO-SCOPE-REF', 'scope_evidence': [copy.deepcopy(scope_quote)],
        'coverage_verified': True, 'coverage_reference': 'DEMO-COVERAGE-REF', 'coverage_statement': statement,
        'coverage_evidence': [copy.deepcopy(scope_quote)], 'projects': []}
    context['tier_project_scope'] = scope
    selected_quote = None
    for i, original in enumerate(projects):
        project = copy.deepcopy(original)
        project['candidate_moka_id'] = candidate_id
        value, version = project.get('tier_value'), project.get('rubric_version')
        excerpt = (f'candidate_moka_id={candidate_id}; project_id={project["project_id"]}; '
                   f'assessment_status={project["assessment_status"]}; validity={project["validity"]}')
        if value is not None:
            excerpt += f'; tier_value={value}; rubric_version={version}'
        excerpt += '; note=DEMO continuous evidence DEMO-UNCOVERED-FACT-tier'
        quote = {'source_id': f'DEMO-PROJECT-SOURCE-{i}', 'locator': 'DEMO-ASSESSMENT', 'excerpt': excerpt}
        context['sources'].append({'source_id': quote['source_id'], 'system': 'moka', 'record_id': candidate_id,
            'url': f'https://example.invalid/project/{i}', 'captured_at': 'DEMO-ONLY',
            'record_type': 'project_assessment', 'project_id': project['project_id'],
            'verified': True, 'verification_reference': 'DEMO-ASSESSMENT-VERIFICATION',
            'segments': [{'locator': quote['locator'], 'text': excerpt}]})
        project['evidence'] = [copy.deepcopy(quote)]
        scope['projects'].append(project)
        if project['project_id'] == plan['target_project_id']:
            selected_quote = quote
    if selected_quote is not None:
        change['evidence'] = [copy.deepcopy(selected_quote)]
        plan['tier_assessment']['dimension_evidence'] = {
            dimension: [copy.deepcopy(selected_quote)] for dimension in gate.DIMENSIONS}


def v11_tier_fixture(projects=None, selected_id='DEMO-PROJECT-1', selected_value='tier 3'):
    plan, context, library = fixture()
    plan['taxonomy_version'] = library['taxonomy_version'] = '1.1'
    for value in ('tier 1', 'tier 2', 'tier not included'):
        library['tags'].append({'tag_group': 'tier', 'tag_value': value, 'status': 'Active',
                                'moka_tag_id': 'DEMO-NEW-' + value})
    tag = next(t for t in library['tags'] if t['tag_group'] == 'tier' and t['tag_value'] == selected_value)
    plan['changes'][0].update(tag_group='tier', tag_value=selected_value, remote_tag_id=tag['moka_tag_id'])
    if selected_value == 'tier not included':
        plan['changes'][0]['exception_assessment'] = {'known_value': 'DEMO-UNCOVERED-FACT-tier',
            'no_matching_tag_verified': True, 'comparison_reference': 'DEMO-EXCEPTION-REF'}
    plan['target_project_id'] = selected_id
    context['approved_rubric'] = {'approved': True, 'approved_by': 'DEMO-OWNER',
        'approval_reference': 'DEMO-RUBRIC-REF', 'project_id': selected_id,
        'version': 'DEMO-RUBRIC-1', 'required_dimensions': list(gate.DIMENSIONS)}
    plan['tier_assessment'] = {'status': 'assessed', 'value': selected_value, 'rubric_version': 'DEMO-RUBRIC-1',
        'dimension_evidence': {d: copy.deepcopy(plan['changes'][0]['evidence']) for d in gate.DIMENSIONS}}
    if projects is None:
        projects = [{'project_id': selected_id, 'assessment_status': 'completed', 'validity': 'valid',
                     'tier_value': selected_value, 'rubric_version': 'DEMO-RUBRIC-1'}]
    upgrade_v11_tier(plan, context, projects)
    return plan, context, library


def exception_fixture(group):
    """A fabricated approved-looking library is only a local test fixture."""
    plan, context, library = fixture()
    plan['taxonomy_version'] = library['taxonomy_version'] = '1.1'
    label = f'{group} not included'
    tag_id = 'DEMO-EXCEPTION-ID-' + group
    library['tags'].append({'tag_group': group, 'tag_value': label,
                            'status': 'Active', 'moka_tag_id': tag_id})
    known = 'DEMO-UNCOVERED-FACT-' + group
    quote = {'source_id': 'DEMO-SOURCE-1', 'locator': 'DEMO-EXCEPTION-LOC', 'excerpt': known}
    context['sources'][0]['segments'].append({'locator': quote['locator'], 'text': 'Evidence: ' + known})
    plan['changes'][0].update(tag_group=group, tag_value=label, remote_tag_id=tag_id, evidence=[quote],
                              exception_assessment={'known_value': known, 'no_matching_tag_verified': True,
                                                    'comparison_reference': 'DEMO-COMPARISON-REF'})
    if group == 'tier':
        plan['target_project_id'] = 'DEMO-PROJECT-1'
        context['approved_rubric'] = {'approved': True, 'approved_by': 'DEMO-OWNER',
            'approval_reference': 'DEMO-RUBRIC-REF', 'project_id': 'DEMO-PROJECT-1',
            'version': 'DEMO-RUBRIC-1', 'required_dimensions': list(gate.DIMENSIONS)}
        plan['tier_assessment'] = {'status': 'assessed', 'value': label, 'rubric_version': 'DEMO-RUBRIC-1',
            'dimension_evidence': {dimension: [copy.deepcopy(quote)] for dimension in gate.DIMENSIONS}}
        upgrade_v11_tier(plan, context, [{'project_id': 'DEMO-PROJECT-1', 'assessment_status': 'completed',
            'validity': 'valid', 'tier_value': label, 'rubric_version': 'DEMO-RUBRIC-1'}])
    return plan, context, library


class TaxonomyExceptionTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.context, self.library = exception_fixture('language')

    def check(self, code=None):
        before = copy.deepcopy((self.plan, self.context, self.library))
        out = gate.validate(self.plan, self.context, self.library)
        self.assertEqual(out, gate.result([] if code is None else [code]))
        self.assertFalse(out['authorized'])
        self.assertFalse(out['executed'])
        self.assertEqual((self.plan, self.context, self.library), before)
        return out

    def test_non_tier_group_exceptions_can_pass_with_fictional_evidence(self):
        for group in (g for g in gate.GROUPS if g != 'tier'):
            with self.subTest(group=group):
                self.plan, self.context, self.library = exception_fixture(group)
                self.check()

    def test_known_value_cannot_be_unknown_empty_or_placeholder(self):
        for value in (None, '', '  ', 'unknown', 'UNSPECIFIED', 'N/A', 'no data', 'not evaluated',
                      'unassessed', '暂无', '未知', '未评估', '---', 1, True):
            with self.subTest(value=value):
                self.plan, self.context, self.library = exception_fixture('language')
                self.plan['changes'][0]['exception_assessment']['known_value'] = value
                self.check('EXCEPTION_KNOWN_VALUE_INVALID')

    def test_assessment_and_verified_comparison_required(self):
        self.plan['changes'][0].pop('exception_assessment')
        self.check('EXCEPTION_ASSESSMENT_REQUIRED')
        for flag in (False, None, 1, 'true'):
            self.plan, self.context, self.library = exception_fixture('language')
            self.plan['changes'][0]['exception_assessment']['no_matching_tag_verified'] = flag
            self.check('EXCEPTION_COMPARISON_UNVERIFIED')
        for reference in ('', None, '  ', 'unknown', 'N/A', True):
            self.plan, self.context, self.library = exception_fixture('language')
            self.plan['changes'][0]['exception_assessment']['comparison_reference'] = reference
            self.check('EXCEPTION_COMPARISON_UNVERIFIED')

    def test_known_value_must_occur_verbatim_in_the_changes_evidence(self):
        change = self.plan['changes'][0]
        known = change['exception_assessment']['known_value']
        # The full source contains the value, but this quote does not.
        change['evidence'][0]['excerpt'] = 'Evidence:'
        self.check('EXCEPTION_EVIDENCE_MISMATCH')
        change['evidence'][0]['excerpt'] = known.lower()
        self.check('QUOTE_NOT_VERBATIM')
        change['evidence'][0]['excerpt'] = 'Evidence: ' + known
        self.check()
        self.plan['changes'][0]['evidence'] = []
        self.check('EVIDENCE_MISSING')

    def test_existing_active_normal_value_cannot_be_reported_as_uncovered(self):
        normal = {'country': 'japan', 'language': 'english', 'project category': 'translation',
                  'knowledge domain': 'biology'}
        for group, value in normal.items():
            with self.subTest(group=group):
                self.plan, self.context, self.library = exception_fixture(group)
                change = self.plan['changes'][0]
                change['exception_assessment']['known_value'] = value.upper()
                change['evidence'][0]['excerpt'] = value.upper()
                source = next(s for s in self.context['sources'] if s['source_id'] == change['evidence'][0]['source_id'])
                segment = next(s for s in source['segments'] if s['locator'] == change['evidence'][0]['locator'])
                segment['text'] = 'Evidence: ' + value.upper()
                self.check('EXCEPTION_KNOWN_VALUE_MATCHES_TAG')
        self.plan, self.context, self.library = exception_fixture('language')
        self.library['tags'][0]['tag_group'] = 'Language'
        change = self.plan['changes'][0]
        change['exception_assessment']['known_value'] = 'english'
        change['evidence'][0]['excerpt'] = 'english'
        self.context['sources'][0]['segments'][-1]['text'] = 'english'
        self.check('EXCEPTION_KNOWN_VALUE_MATCHES_TAG')

    def test_inactive_value_or_other_groups_same_value_not_automatically_a_match(self):
        self.plan['changes'][0]['exception_assessment']['known_value'] = 'english'
        self.plan['changes'][0]['evidence'][0]['excerpt'] = 'english'
        self.context['sources'][0]['segments'][-1]['text'] = 'english'
        self.library['tags'][0]['status'] = 'Inactive'
        self.library['tags'].append({'tag_group': 'country', 'tag_value': 'english', 'status': 'Active',
                                     'moka_tag_id': 'DEMO-OTHER-GROUP-ID'})
        self.check()

    def test_exception_must_be_exact_active_in_correct_group_with_unique_id(self):
        for mutation, error in (('missing', 'TAG_NOT_IN_LIBRARY'), ('inactive', 'TAG_NOT_ACTIVE'),
                                ('blank_id', 'REMOTE_TAG_ID_MISMATCH'), ('wrong_id', 'REMOTE_TAG_ID_MISMATCH'),
                                ('duplicate_id', 'MOKA_ID_AMBIGUOUS'), ('wrong_group', 'TAG_NOT_IN_LIBRARY'),
                                ('wrong_label', 'TAG_NOT_IN_LIBRARY'), ('unapproved', 'LIBRARY_NOT_APPROVED')):
            with self.subTest(mutation=mutation):
                self.plan, self.context, self.library = exception_fixture('language')
                tag = self.library['tags'][-1]
                if mutation == 'missing': self.library['tags'].pop()
                if mutation == 'inactive': tag['status'] = 'Inactive'
                if mutation == 'blank_id': tag['moka_tag_id'] = ''
                if mutation == 'wrong_id': self.plan['changes'][0]['remote_tag_id'] = 'DEMO-NOT-THE-ID'
                if mutation == 'duplicate_id': tag['moka_tag_id'] = self.library['tags'][0]['moka_tag_id']
                if mutation == 'wrong_group': tag['tag_group'] = 'country'
                if mutation == 'wrong_label': tag['tag_value'] = 'language exception'
                if mutation == 'unapproved': self.library['current_approved_version_verified'] = False
                self.check(error)

    def test_exception_value_from_another_group_or_case_variant_cannot_bypass(self):
        for value in ('country not included', 'Language not included', 'rate not included'):
            with self.subTest(value=value):
                self.plan, self.context, self.library = exception_fixture('language')
                self.plan['changes'][0]['tag_value'] = value
                self.check('EXCEPTION_GROUP_MISMATCH')

    def test_multiselect_can_add_one_ordinary_and_one_different_uncovered_value(self):
        ordinary = {'language': ('english', 'DEMO-TAG-0'),
                    'knowledge domain': ('biology', 'DEMO-TAG-6'),
                    'project category': ('translation', 'DEMO-TAG-4')}
        for group, (value, tag_id) in ordinary.items():
            with self.subTest(group=group):
                self.plan, self.context, self.library = exception_fixture(group)
                regular = copy.deepcopy(self.plan['changes'][0])
                regular.update(tag_value=value, remote_tag_id=tag_id,
                               evidence=[{'source_id': 'DEMO-SOURCE-1', 'locator': 'DEMO-PARAGRAPH-1',
                                          'excerpt': 'DEMO continuous evidence'}])
                regular.pop('exception_assessment')
                self.plan['changes'].insert(0, regular)
                self.check()
                # Exception must not claim the selected ordinary value is unmatched.
                exception = self.plan['changes'][1]
                exception['exception_assessment']['known_value'] = value
                exception['evidence'][0]['excerpt'] = value
                self.context['sources'][0]['segments'][-1]['text'] = value
                self.check('EXCEPTION_KNOWN_VALUE_MATCHES_TAG')

    def test_country_exception_remains_single_select(self):
        self.plan, self.context, self.library = exception_fixture('country')
        self.context['current_tags']['moka'] = [{'tag_group': 'country', 'tag_value': 'japan'}]
        self.check('SINGLE_SELECT_CONFLICT')
        self.context['current_tags']['moka'] = []
        ordinary = copy.deepcopy(self.plan['changes'][0])
        ordinary.update(tag_value='japan', remote_tag_id='DEMO-TAG-2')
        self.plan['changes'].append(ordinary)
        self.check('SINGLE_SELECT_CONFLICT')

    def test_tier_exception_is_always_unsupported(self):
        self.plan, self.context, self.library = exception_fixture('tier')
        self.check('TIER_PROJECT_CONTEXT_UNSUPPORTED')
        self.context['approved_rubric']['approved'] = False
        self.check('TIER_PROJECT_CONTEXT_UNSUPPORTED')

    def test_v11_project_category_must_be_multi_old_versions_remain_compatible(self):
        self.plan, self.context, self.library = exception_fixture('project category')
        self.check()
        self.context['project_category_selection_type'] = 'single'
        self.check('PC_V11_MULTI_REQUIRED')
        self.plan['taxonomy_version'] = self.library['taxonomy_version'] = 'v1.1'
        self.check('PC_V11_MULTI_REQUIRED')
        self.plan['taxonomy_version'] = self.library['taxonomy_version'] = 'DEMO-VERSION'
        self.check()
        self.plan, self.context, self.library = fixture()
        self.plan['taxonomy_version'] = self.library['taxonomy_version'] = '1.1'
        self.plan['changes'][0].update(tag_group='project category', tag_value='translation', remote_tag_id='DEMO-TAG-4')
        self.context['project_category_selection_type'] = 'single'
        self.check('PC_V11_MULTI_REQUIRED')
        self.context['project_category_selection_type'] = 'multi'
        self.check()

    def test_rate_is_never_accepted_here_and_points_to_independent_gate(self):
        for value in ('rate not included', '60 USD < Expected Rate ≤ 100 USD'):
            self.plan, self.context, self.library = fixture()
            self.plan['changes'][0].update(tag_group='rate', tag_value=value, remote_tag_id='DEMO-RATE-ID')
            self.library['tags'].append({'tag_group': 'rate', 'tag_value': value,
                                         'status': 'Active', 'moka_tag_id': 'DEMO-RATE-ID'})
            result = self.check('UNKNOWN_TAG_GROUP')
            self.assertIn('validate_rate_write_plan.py', result['guidance'])


def demo_project(project_id, value, status='completed', validity='valid', version='DEMO-RUBRIC-1', **extra):
    return dict(project_id=project_id, assessment_status=status, validity=validity,
                tier_value=value, rubric_version=version, **extra)


class TaxonomyTierFailClosedTests(unittest.TestCase):
    ERROR = 'TIER_PROJECT_CONTEXT_UNSUPPORTED'

    def check_blocked(self, plan, context, library):
        before = copy.deepcopy((plan, context, library))
        out = gate.validate(plan, context, library)
        self.assertEqual(out, gate.result([self.ERROR]))
        self.assertFalse(out['authorized'])
        self.assertFalse(out['executed'])
        self.assertEqual((plan, context, library), before)
        return out

    def test_typical_old_highest_rollup_never_passes(self):
        projects = [demo_project('DEMO-OLD', 'tier 1', completed_at='2023-01-01'),
                    demo_project('DEMO-NEW', 'tier 3', completed_at='2026-01-01')]
        for order in (projects, list(reversed(projects))):
            # Old code accepted the highest in either order, and rejected the
            # independently assessed project as not-highest. Both now stop.
            for project, value in (('DEMO-OLD', 'tier 1'), ('DEMO-NEW', 'tier 3')):
                with self.subTest(order=order, project=project):
                    p, c, lib = v11_tier_fixture(order, project, value)
                    self.check_blocked(p, c, lib)

    def test_independent_project_results_do_not_cause_conflict_or_rollup_write(self):
        projects = [demo_project('DEMO-A', 'tier 1'), demo_project('DEMO-B', 'tier 3')]
        p, c, lib = v11_tier_fixture(projects, 'DEMO-B', 'tier 3')
        c['current_tags']['moka'] = [{'tag_group': 'tier', 'tag_value': 'tier 1'}]
        out = self.check_blocked(p, c, lib)
        self.assertNotIn('SINGLE_SELECT_CONFLICT', out['errors'])
        self.assertNotIn('TIER_NOT_HIGHEST', out['errors'])
        # A non-Tier operation leaves all project evidence/history untouched;
        # the validator does not create an implicit aggregate change.
        language = copy.deepcopy(fixture()[0]['changes'][0])
        language['field'] = 'candidate_custom_tags'
        p['changes'] = [language]
        before = copy.deepcopy((p, c, lib))
        result = gate.validate(p, c, lib)
        self.assertTrue(result['ready_for_confirmation'], result)
        self.assertFalse(result['authorized'])
        self.assertFalse(result['executed'])
        self.assertEqual((p, c, lib), before)
        self.assertEqual([ch['tag_group'] for ch in p['changes']], ['language'])

    def test_all_versions_operations_fields_and_statuses_are_blocked(self):
        for version in ('1.0', '1.1', 'v1.1', 'DEMO-FUTURE'):
            for field in ('candidate_custom_tags', 'DEMO-APPLICATION-FIELD'):
                for operation in ('add', 'replace', 'delete', 'set'):
                    p, c, lib = v11_tier_fixture()
                    p['taxonomy_version'] = lib['taxonomy_version'] = version
                    p['changes'][0].update(field=field, operation=operation)
                    c['allowed_fields']['moka'].append(field)
                    c['allowed_operations']['moka'].append(operation)
                    self.check_blocked(p, c, lib)
        p, c, lib = v11_tier_fixture()
        p['tier_assessment']['status'] = 'not_assessed'
        c['approved_rubric']['approved'] = False
        self.check_blocked(p, c, lib)

    def test_all_tier_values_including_exception_and_current_values_block(self):
        for value in ('tier 1', 'tier 2', 'tier 3', 'tier 4', 'tier not included'):
            for old in (None, 'tier 1', 'tier 3', 'tier not included'):
                p, c, lib = v11_tier_fixture(selected_value=value)
                if old:
                    c['current_tags']['moka'] = [{'tag_group': 'tier', 'tag_value': old}]
                self.check_blocked(p, c, lib)

    def test_mixed_changes_cannot_hide_tier_and_preflight_ignores_case_or_width(self):
        for label in ('tier', ' TIER ', 'Ｔｉｅｒ'):
            p, c, lib = fixture()
            tier = copy.deepcopy(p['changes'][0])
            tier['tag_group'] = label
            p['changes'].append(tier)
            self.check_blocked(p, c, lib)
            # Neither invalid earlier plan metadata nor a forbidden operation
            # can make the gate misclassify Tier as an existing-tag conflict.
            p['candidate']['match_status'] = 'unverified'
            self.check_blocked(p, c, lib)

    def test_internal_validation_entry_point_also_blocks(self):
        p, c, lib = v11_tier_fixture()
        with self.assertRaises(gate.Blocked) as caught:
            gate._validate(p, c, lib)
        self.assertEqual(str(caught.exception), self.ERROR)
        self.assertFalse(hasattr(gate, '_v11_tier_rollup'))

    def test_example_templates_are_explicitly_unsupported(self):
        base = Path(gate.__file__).resolve().parents[1] / 'templates'
        names = ('taxonomy-tier-plan.example.json', 'taxonomy-tier-context.example.json',
                 'taxonomy-tier-library.example.json')
        plan, context, library = [json.loads((base / name).read_text(encoding='utf-8')) for name in names]
        self.assertIn('TIER_PROJECT_CONTEXT_UNSUPPORTED', plan['_example_notice'])
        self.check_blocked(plan, context, library)


class CliTests(unittest.TestCase):
    def run_cli(self, inputs, argv=None):
        out = io.StringIO()
        with patch("builtins.open", side_effect=[io.StringIO(s) for s in inputs]) as opened, redirect_stdout(out):
            code = gate.main(argv or ["--plan", "DEMO-PLAN", "--context", "DEMO-CONTEXT", "--library", "DEMO-LIB"])
        return code, json.loads(out.getvalue()), opened

    def test_exit_codes_zero_two_three_and_no_sensitive_echo(self):
        p, c, lib = fixture()
        jsons = [json.dumps(x) for x in (p, c, lib)]
        code, output, _ = self.run_cli(jsons)
        self.assertEqual((code, output), (0, gate.result([])))
        p["candidate"]["match_status"] = "unverified"
        code, output, _ = self.run_cli([json.dumps(x) for x in (p, c, lib)])
        self.assertEqual((code, output), (2, gate.result(["IDENTITY_UNVERIFIED"])))
        code, output, _ = self.run_cli(['{"DEMO-SECRET":'] * 3)
        self.assertEqual((code, output), (3, gate.result(["INPUT_ERROR"])))
        self.assertNotIn("DEMO-SECRET", json.dumps(output))

    def test_v11_tier_cli_is_blocked_with_explicit_error(self):
        projects = [demo_project('DEMO-VALID', 'tier 3'),
                    demo_project('DEMO-PENDING', None, status='in_progress', validity='not_applicable', version=None)]
        p, c, lib = v11_tier_fixture(projects, 'DEMO-VALID', 'tier 3')
        code, output, _ = self.run_cli([json.dumps(x) for x in (p, c, lib)])
        self.assertEqual((code, output), (2, gate.result(['TIER_PROJECT_CONTEXT_UNSUPPORTED'])))
        self.assertFalse(output['authorized'])
        self.assertFalse(output['executed'])
        self.assertNotIn('tier_pending_verification_count', output)

    def test_script_subprocess_cli_and_dependency_contract(self):
        p, c, lib = v11_tier_fixture()
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ('plan.json', 'context.json', 'library.json')]
            def run(values):
                for path, value in zip(paths, values):
                    path.write_text(json.dumps(value), encoding='utf-8')
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
                return subprocess.run([sys.executable, str(Path(gate.__file__).resolve()),
                                       '--plan', str(paths[0]), '--context', str(paths[1]),
                                       '--library', str(paths[2])], capture_output=True, text=True, env=env,
                                      cwd=directory, check=False)
            tier = run((p, c, lib))
            self.assertEqual(tier.returncode, 2, tier.stderr)
            self.assertEqual(json.loads(tier.stdout), gate.result(['TIER_PROJECT_CONTEXT_UNSUPPORTED']))
            ordinary = run(fixture())
            self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
            self.assertEqual(json.loads(ordinary.stdout), gate.result([]))
            self.assertEqual(tier.stderr, '')
            self.assertEqual(ordinary.stderr, '')

    def test_duplicate_json_keys_nested_or_root_rejected(self):
        p, c, lib = fixture()
        for malformed in ('{"x":1,"x":2}', '{"candidate":{"moka_id":"x","moka_id":"y"}}'):
            code, output, _ = self.run_cli([malformed, json.dumps(c), json.dumps(lib)])
            self.assertEqual((code, output), (3, gate.result(["INPUT_ERROR"])))

    def test_nan_and_infinity_anywhere_rejected(self):
        p, c, lib = fixture()
        for token in ("NaN", "Infinity", "-Infinity"):
            code, output, _ = self.run_cli(['{"unused":' + token + '}', json.dumps(c), json.dumps(lib)])
            self.assertEqual((code, output), (3, gate.result(["INPUT_ERROR"])))

    def test_valid_large_exponent_is_json_not_nan(self):
        p, c, lib = fixture()
        p["ignored_number"] = 1
        encoded = json.dumps(p).replace('"ignored_number": 1', '"ignored_number": 1e9999')
        code, output, _ = self.run_cli([encoded, json.dumps(c), json.dumps(lib)])
        self.assertEqual((code, output), (0, gate.result([])))

    def test_default_snapshot_path_and_unverified_snapshot_blocks(self):
        p, c, lib = fixture()
        lib.update(current_approved_version_verified=False, active_status_verified=False,
                   moka_id_mapping_verified=False, approval_reference=None)
        code, output, opened = self.run_cli([json.dumps(x) for x in (p, c, lib)],
                                             ["--plan", "DEMO-PLAN", "--context", "DEMO-CONTEXT"])
        self.assertEqual((code, output), (2, gate.result(["LIBRARY_NOT_APPROVED"])))
        self.assertEqual(opened.call_args_list[2].args[0], str(gate.DEFAULT_LIBRARY))
        self.assertEqual(gate.DEFAULT_LIBRARY.name, "tag-library.snapshot.json")
        self.assertEqual(gate.DEFAULT_LIBRARY.parent.name, "assets")

    def test_missing_file_and_bad_arguments_exit_three_as_json(self):
        out = io.StringIO()
        with patch("builtins.open", side_effect=FileNotFoundError("DEMO-SECRET")), redirect_stdout(out):
            code = gate.main(["--plan", "X", "--context", "Y"])
        self.assertEqual((code, json.loads(out.getvalue())), (3, gate.result(["INPUT_ERROR"])))
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate.main(["--DEMO-SECRET"])
        self.assertEqual((code, json.loads(out.getvalue())), (3, gate.result(["INPUT_ERROR"])))

    def test_generic_literal_record_parsing_is_preserved(self):
        self.assertEqual(gate._parse_record('group=language; value=english'),
                         {'group': 'language', 'value': 'english'})
        self.assertTrue(gate._record_matches('{"group":"language","value":"english"}',
                                             {'group': 'language', 'value': 'english'}))
        self.assertFalse(gate._record_matches('group=language; value=spanish', {'value': 'english'}))
        self.assertIsNone(gate._parse_record('group=language; group=country'))
        self.assertIsNone(gate._parse_record('{"group":"language","group":"country"}'))
        self.assertIsNone(gate._parse_record('{"value":NaN}'))


if __name__ == "__main__":
    unittest.main(verbosity=1)
