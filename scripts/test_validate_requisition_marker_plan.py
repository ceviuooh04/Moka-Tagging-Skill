#!/usr/bin/env python3
"""Offline unit tests. All IDs, content and authorizations below are fictional.

Run: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
     test_validate_requisition_marker_plan
The positive fixtures are NOT evidence about any real candidate or account.
"""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
import validate_requisition_marker_plan as gate

NOW = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc)
TAG = {'id': 'TAG-DEMO', 'name': 'Workflow Review Marker',
       'group_id': 'GROUP-MANUAL', 'group_name': 'Manual Work Markers'}
OLD = {'id': 'TAG-OLD', 'name': 'Existing Item',
       'group_id': 'GROUP-OTHER', 'group_name': 'Other Group'}
TARGET = {'job_id': 'JOB-DEMO', 'requisition_id': 'REQ-DEMO',
          'application_id': 'APP-DEMO', 'candidate_id': 'CAND-DEMO',
          'edit_target': {'type': 'candidate', 'id': 'CAND-DEMO'}}


def make_source(sid, kind, body, now=NOW, section='other', record_id=None):
    result = {'source_id': sid, 'kind': kind, 'system': 'fictional source system',
              'reference': 'fictional actual-record location', 'captured_at': now.isoformat(),
              'verified': True, 'verification_reference': 'fictional reviewed source',
              'segments': [{'locator': 'segment-one', 'section': section, 'text': body}]}
    if record_id is not None:
        result['record_id'] = record_id
    return result


def citation(source, excerpt=None, locator='segment-one'):
    segment = next(s for s in source['segments'] if s['locator'] == locator)
    return {'source_id': source['source_id'], 'locator': locator,
            'excerpt': segment['text'] if excerpt is None else excerpt}


def mark(entry):
    return {**entry, 'verified': True, 'verification_reference': 'fictional reviewed binding'}


def fixture(now=NOW):
    work = make_source('WORK', 'requisition',
                       'Review automated workflow runs, diagnose failure modes, and report outcomes.',
                       now, 'work_content', 'REQ-DEMO')
    work['segments'].append({'locator': 'heading', 'section': 'title', 'text': 'Workflow Specialist'})
    record = make_source('RECORD', 'moka_record',
                         'JOB-DEMO REQ-DEMO APP-DEMO CAND-DEMO', now)
    user = make_source('USER', 'user_instruction',
                       'Please add the requested manual marker for the specified job and candidates.', now)
    library = make_source('LIBRARY', 'moka_tag_library',
                          'TAG-DEMO Workflow Review Marker GROUP-MANUAL Manual Work Markers enabled.', now)
    snapshot = make_source('SNAP', 'moka_tag_snapshot',
                           'CAND-DEMO APP-DEMO TAG-OLD Existing Item GROUP-OTHER Other Group', now)
    plan = {'target': copy.deepcopy(TARGET), 'tag': copy.deepcopy(TAG), 'action': 'add',
            'after_tags': [copy.deepcopy(OLD), copy.deepcopy(TAG)],
            'evidence': [citation(work)],
            'semantic_review': {'decision': 'match',
                                'reasoning': 'The cited duties concern reviewing workflow runs and outcomes.',
                                'subject': 'job_work_not_candidate_capability',
                                'work_content_verified': True,
                                'verification_reference': 'fictional reviewed work section'}}
    context = {'sources': [work, record, user, library, snapshot],
               'job_requisition_link': mark({'job_id': 'JOB-DEMO', 'requisition_id': 'REQ-DEMO',
                                             'citations': [citation(record)]}),
               'application_link': mark({'job_id': 'JOB-DEMO', 'application_id': 'APP-DEMO',
                                         'candidate_id': 'CAND-DEMO', 'citations': [citation(record)]}),
               'edit_target_check': mark({'type': 'candidate', 'id': 'CAND-DEMO',
                                          'citations': [citation(record)]}),
               'scope': mark({'job_id': 'JOB-DEMO', 'tag_id': 'TAG-DEMO', 'action': 'add',
                              'targets': [{'application_id': 'APP-DEMO', 'candidate_id': 'CAND-DEMO'}],
                              'citations': [citation(user)]}),
               'effects': {'complete': True, 'verification_reference': 'fictional sharing review',
                           'impacted_applications': [{'job_id': 'JOB-DEMO', 'application_id': 'APP-DEMO',
                                                      'candidate_id': 'CAND-DEMO',
                                                      'citations': [citation(record)]}]},
               'snapshot': {'edit_target': {'type': 'candidate', 'id': 'CAND-DEMO'},
                            'complete': True, 'verification_reference': 'fictional loaded all tags',
                            'citations': [citation(snapshot)],
                            'tags': [{**copy.deepcopy(OLD), 'citations': [citation(snapshot)]}]},
               'conflict_review': {'no_known_conflicts': True,
                                   'verification_reference': 'fictional review of known conflicts'}}
    lib = {'tag': {**copy.deepcopy(TAG), 'active': True, 'verified': True,
                   'verification_reference': 'fictional active library inspection',
                   'citations': [citation(library)],
                   'active_status_verified': True, 'active_status_reference': 'fictional status inspection',
                   'active_status_citations': [citation(library)],
                   'job_marker_group_verified': True,
                   'job_marker_group_reference': 'fictional observed marker group',
                   'distinct_from_taxonomy_project_category_verified': True,
                   'distinct_from_taxonomy_project_category_reference': 'fictional group distinction review'}}
    return [plan, context, lib]


def source(case, name):
    return next(s for s in case[1]['sources'] if s['source_id'] == name)


def add_existing_target(case):
    snap = source(case, 'SNAP')
    snap['segments'][0]['text'] += ' TAG-DEMO Workflow Review Marker GROUP-MANUAL Manual Work Markers'
    # Refresh all original snapshot citations to quote actual unchanged/current text.
    case[1]['snapshot']['citations'] = [citation(snap)]
    case[1]['snapshot']['tags'][0]['citations'] = [citation(snap)]
    case[1]['snapshot']['tags'].append({**copy.deepcopy(TAG), 'citations': [citation(snap)]})
    case[0]['action'] = 'skip'


class GateTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture()

    def outcome(self, **kwargs):
        return gate.validate(*self.case, now=NOW, **kwargs)

    def passes(self, action='add'):
        result = self.outcome()
        self.assertTrue(result['ready_for_confirmation'], result)
        self.assertEqual(result['action'], action)
        self.assertFalse(result['authorized'])
        self.assertFalse(result['executed'])
        self.assertFalse(result['semantic_match_proven'])
        self.assertFalse(result['source_authenticity_proven'])
        self.assertFalse(result['candidate_capability_inferred'])
        self.assertTrue(result['pre_write_reread_required'])
        self.assertTrue(result['post_write_reread_required'])
        return result

    def blocks(self, expected=None):
        result = self.outcome()
        self.assertFalse(result['ready_for_confirmation'], result)
        self.assertEqual(result['action'], 'blocked')
        self.assertFalse(result['authorized'])
        self.assertFalse(result['executed'])
        if expected:
            self.assertEqual(result['errors'], [expected])
        return result

    def test_fictional_valid_add_and_complete_preserved_tags(self):
        self.passes()

    def test_agent_workflow_example_uses_duties_not_title(self):
        work = source(self.case, 'WORK')
        work['segments'][0]['text'] = (
            'Evaluate coding agents on engineering tasks by reviewing their full '
            'trajectories, tool calls, edits and outcomes.'
        )
        self.case[0]['evidence'] = [citation(work)]
        self.case[0]['semantic_review']['reasoning'] = (
            'The project evaluates agent workflows and their execution trajectories.'
        )
        target = self.case[0]['tag']
        target['name'] = 'Agent Workflow Evaluation'
        self.case[0]['after_tags'][1]['name'] = target['name']
        libsource = source(self.case, 'LIBRARY')
        libsource['segments'][0]['text'] = (
            'TAG-DEMO Agent Workflow Evaluation GROUP-MANUAL Manual Work Markers enabled.'
        )
        self.case[2]['tag']['name'] = target['name']
        self.case[2]['tag']['citations'] = [citation(libsource)]
        self.case[2]['tag']['active_status_citations'] = [citation(libsource)]
        self.passes()  # The gate checks structure; semantic review remains human/agent judgment.
        self.case[0]['semantic_review']['decision'] = 'uncertain'
        self.blocks('SEMANTIC_MATCH_NOT_ASSERTED')

    def test_alternative_job_source_and_marker_no_fixed_keywords(self):
        work = source(self.case, 'WORK')
        work.update(kind='job', record_id='JOB-DEMO')
        work['segments'][0]['text'] = 'Calibrate images and report visual quality metrics.'
        self.case[0]['evidence'] = [citation(work)]
        self.case[0]['semantic_review']['reasoning'] = 'Agent reviewed the actual visual calibration duties.'
        self.passes()  # Structural pass only: no meaning is evaluated by the script.

    def test_unrelated_semantics_cannot_be_determined_by_script(self):
        work = source(self.case, 'WORK')
        work['segments'][0]['text'] = 'Water indoor plants and arrange flowers.'
        self.case[0]['evidence'] = [citation(work)]
        # Even a poor/fabricated assertion is not machine-verifiable. A pass here
        # demonstrates the limitation, not that these duties match the marker.
        result = self.passes()
        self.assertFalse(result['semantic_match_proven'])
        self.case[0]['semantic_review']['decision'] = 'no_match'
        self.blocks('SEMANTIC_MATCH_NOT_ASSERTED')
        self.case[0]['semantic_review']['decision'] = 'uncertain'
        self.blocks('SEMANTIC_MATCH_NOT_ASSERTED')

    def test_no_candidate_capability_or_missing_reasoning(self):
        self.case[0]['semantic_review']['subject'] = 'candidate_capability'
        self.blocks('WRONG_SEMANTIC_SUBJECT')
        self.case[0]['semantic_review']['subject'] = 'job_work_not_candidate_capability'
        self.case[0]['semantic_review']['reasoning'] = ''
        self.blocks('MISSING_REASONING')
        self.case[0]['semantic_review']['reasoning'] = 'Fictional reasoning'
        self.case[0]['semantic_review']['work_content_verified'] = False
        self.blocks('WORK_CONTENT_UNVERIFIED')

    def test_title_only_blocks_even_if_quote_is_exact(self):
        work = source(self.case, 'WORK')
        self.case[0]['evidence'] = [citation(work, locator='heading')]
        self.blocks('TITLE_OR_NON_WORK_EVIDENCE')

    def test_title_repeated_as_work_quote_is_not_sufficient(self):
        work = source(self.case, 'WORK')
        work['segments'][0]['text'] = 'Workflow Specialist'
        self.case[0]['evidence'] = [citation(work)]
        self.blocks('TITLE_OR_NON_WORK_EVIDENCE')

    def test_quote_must_be_literal_contiguous_and_real(self):
        work = source(self.case, 'WORK')
        for excerpt in ('Review automated ... report outcomes.', 'report results',
                        'REVIEW automated workflow runs', 'invented work'):
            with self.subTest(excerpt=excerpt):
                self.case[0]['evidence'] = [citation(work, excerpt)]
                self.blocks('INVALID_WORK_EVIDENCE')
        self.case[0]['evidence'] = [citation(work, 'automated workflow runs, diagnose failure modes')]
        self.passes()

    def test_evidence_from_wrong_requisition_or_job_blocks(self):
        source(self.case, 'WORK')['record_id'] = 'REQ-OTHER'
        self.blocks('CROSS_JOB_WORK_EVIDENCE')
        source(self.case, 'WORK').update(kind='job', record_id='JOB-OTHER')
        self.blocks('CROSS_JOB_WORK_EVIDENCE')

    def test_job_requisition_link_cannot_cross_jobs_or_be_unverified(self):
        self.case[1]['job_requisition_link']['requisition_id'] = 'REQ-OTHER'
        self.blocks('JOB_REQUISITION_MISMATCH')
        self.case[1]['job_requisition_link']['requisition_id'] = 'REQ-DEMO'
        self.case[1]['job_requisition_link']['verified'] = False
        self.blocks('UNVERIFIED_JOB_REQUISITION_LINK')
        self.case[1]['job_requisition_link']['verified'] = True
        self.case[1]['job_requisition_link']['citations'][0]['excerpt'] = 'JOB-DEMO'
        self.blocks('INCOMPLETE_JOB_LINK_EVIDENCE')

    def test_application_candidate_identity_and_source_are_required(self):
        for key in ('job_id', 'application_id', 'candidate_id'):
            with self.subTest(key=key):
                case = fixture()
                case[1]['application_link'][key] = 'WRONG-IDENTIFIER'
                self.assertEqual(gate.validate(*case, now=NOW)['errors'], ['APPLICATION_LINK_MISMATCH'])
        self.case[1]['application_link']['verified'] = False
        self.blocks('UNVERIFIED_APPLICATION_LINK')
        self.case[1]['application_link']['verified'] = True
        self.case[1]['application_link']['citations'][0]['excerpt'] = 'JOB-DEMO REQ-DEMO APP-DEMO'
        self.blocks('INCOMPLETE_APPLICATION_EVIDENCE')

    def test_edit_object_application_or_candidate_must_match_exactly(self):
        self.case[0]['target']['edit_target']['id'] = 'APP-DEMO'
        self.blocks('EDIT_TARGET_MISMATCH')
        self.case = fixture()
        self.case[0]['target']['edit_target'] = {'type': 'application', 'id': 'APP-DEMO'}
        self.case[1]['edit_target_check'].update(type='application', id='APP-DEMO')
        self.case[1]['snapshot']['edit_target'] = {'type': 'application', 'id': 'APP-DEMO'}
        self.passes()
        self.case[1]['snapshot']['edit_target']['id'] = 'APP-OTHER'
        self.blocks('SNAPSHOT_TARGET_MISMATCH')

    def test_unauthorized_unverified_and_out_of_scope(self):
        self.case[1]['scope']['verified'] = False
        self.blocks('SCOPE_UNVERIFIED')
        self.case[1]['scope']['verified'] = True
        self.case[1]['scope']['tag_id'] = 'TAG-OTHER'
        self.blocks('OUT_OF_SCOPE')
        self.case[1]['scope']['tag_id'] = 'TAG-DEMO'
        self.case[1]['scope']['action'] = 'read_only'
        self.blocks('OUT_OF_SCOPE')
        self.case[1]['scope']['action'] = 'add'
        self.case[1]['scope']['targets'][0]['application_id'] = 'APP-OTHER'
        self.blocks('OUT_OF_SCOPE')

    def test_whole_job_scope_and_explicit_candidate_scope(self):
        self.case[1]['scope']['targets'] = 'all_applications_for_job'
        self.passes()
        self.case[1]['scope']['targets'] = []
        self.blocks('INVALID_SCOPE_TARGETS')

    def test_scope_must_cite_actual_user_instruction_not_moka_record(self):
        self.case[1]['scope']['citations'] = [citation(source(self.case, 'RECORD'))]
        self.blocks('INVALID_SCOPE_EVIDENCE')

    def test_shared_profile_cross_job_propagation_is_disclosed_not_new_edit(self):
        impacts = self.case[1]['effects']['impacted_applications']
        shared = make_source('SHARED', 'moka_record', 'JOB-OTHER APP-OTHER CAND-DEMO')
        self.case[1]['sources'].append(shared)
        impacts.append({'job_id': 'JOB-OTHER', 'application_id': 'APP-OTHER', 'candidate_id': 'CAND-DEMO',
                        'citations': [citation(shared)]})
        self.passes()
        self.case[1]['scope']['targets'] = 'all_applications_for_job'
        self.passes()
        # The same effect is forbidden when the actual edit is an application,
        # rather than a verified shared candidate-profile tag.
        self.case[0]['target']['edit_target'] = {'type': 'application', 'id': 'APP-DEMO'}
        self.case[1]['edit_target_check'].update(type='application', id='APP-DEMO')
        self.case[1]['snapshot']['edit_target'] = {'type': 'application', 'id': 'APP-DEMO'}
        self.blocks('IMPACT_OUT_OF_SCOPE')

    def test_shared_effect_on_another_candidate_is_blocked(self):
        impacts = self.case[1]['effects']['impacted_applications']
        shared = make_source('SHARED', 'moka_record', 'JOB-OTHER APP-OTHER CAND-OTHER')
        self.case[1]['sources'].append(shared)
        impacts.append({'job_id': 'JOB-OTHER', 'application_id': 'APP-OTHER', 'candidate_id': 'CAND-OTHER',
                        'citations': [citation(shared)]})
        self.blocks('IMPACT_OUT_OF_SCOPE')

    def test_unverified_or_omitted_affected_applications_block(self):
        self.case[1]['effects']['complete'] = False
        self.blocks('SHARED_EFFECTS_UNVERIFIED')
        self.case[1]['effects']['complete'] = True
        self.case[1]['effects']['impacted_applications'] = []
        self.blocks('INVALID_EFFECTS')
        impact = {'job_id': 'JOB-DEMO', 'application_id': 'APP-OTHER', 'candidate_id': 'CAND-DEMO',
                  'citations': [citation(source(self.case, 'RECORD'))]}
        self.case[1]['scope']['targets'] = 'all_applications_for_job'
        self.case[1]['effects']['impacted_applications'] = [impact]
        self.blocks('INCOMPLETE_IMPACT_EVIDENCE')

    def test_library_group_id_active_and_distinction_are_verified(self):
        lib = self.case[2]['tag']
        checks = [('active', False, 'TAG_NOT_ACTIVE'), ('verified', False, 'LIBRARY_TAG_UNVERIFIED'),
                  ('active_status_verified', False, 'ACTIVE_STATUS_UNVERIFIED'),
                  ('job_marker_group_verified', False, 'MARKER_GROUP_UNVERIFIED'),
                  ('distinct_from_taxonomy_project_category_verified', False,
                   'TAXONOMY_GROUP_DISTINCTION_UNVERIFIED')]
        for key, value, expected in checks:
            with self.subTest(key=key):
                original = lib[key]
                lib[key] = value
                self.blocks(expected)
                lib[key] = original
        lib['taxonomy_project_category_group_id'] = 'GROUP-MANUAL'
        self.blocks('TAXONOMY_GROUP_CONFLICT')
        lib['taxonomy_project_category_group_id'] = 'GROUP-TAXONOMY'
        self.passes()
        lib['id'] = 'TAG-OTHER'
        self.blocks('LIBRARY_TAG_MISMATCH')

    def test_library_source_must_contain_real_group_and_tag_fields(self):
        libsource = source(self.case, 'LIBRARY')
        self.case[2]['tag']['citations'] = [citation(libsource, 'TAG-DEMO Workflow Review Marker')]
        self.blocks('INCOMPLETE_LIBRARY_EVIDENCE')

    def test_active_status_needs_its_own_actual_quote(self):
        self.case[2]['tag']['active_status_citations'] = []
        self.blocks('INVALID_ACTIVE_STATUS_EVIDENCE')
        self.case[2]['tag']['active_status_citations'] = [citation(source(self.case, 'LIBRARY'), 'active')]
        self.blocks('INVALID_ACTIVE_STATUS_EVIDENCE')
        self.case[2]['tag']['active_status_citations'] = [citation(source(self.case, 'LIBRARY'), 'enabled')]
        self.blocks('INCOMPLETE_ACTIVE_STATUS_EVIDENCE')

    def test_same_tag_name_is_not_an_id_or_group_mapping(self):
        self.case[2]['tag']['id'] = 'SAME-NAME-OTHER-ID'
        self.blocks('LIBRARY_TAG_MISMATCH')
        self.case[2]['tag']['id'] = 'TAG-DEMO'
        self.case[2]['tag']['group_id'] = 'TAXONOMY-GROUP'
        self.blocks('LIBRARY_TAG_MISMATCH')

    def test_existing_marker_skip_and_add_mismatch(self):
        add_existing_target(self.case)
        self.passes('skip')
        self.case[0]['action'] = 'add'
        self.blocks('ADD_SKIP_MISMATCH')
        self.case = fixture()
        self.case[0]['action'] = 'skip'
        self.blocks('ADD_SKIP_MISMATCH')

    def test_complete_empty_snapshot_supports_add_but_not_unread_snapshot(self):
        snap = source(self.case, 'SNAP')
        snap['segments'][0]['text'] = 'CAND-DEMO APP-DEMO No tags.'
        self.case[1]['snapshot']['citations'] = [citation(snap)]
        self.case[1]['snapshot']['tags'] = []
        self.case[0]['after_tags'] = [copy.deepcopy(TAG)]
        self.passes()
        self.case[1]['snapshot']['complete'] = False
        self.blocks('SNAPSHOT_INCOMPLETE')

    def test_after_tags_cannot_drop_change_or_add_any_other_tag(self):
        self.case[0]['after_tags'] = [copy.deepcopy(TAG)]
        self.blocks('OTHER_TAGS_NOT_PRESERVED')
        self.case[0]['after_tags'] = [copy.deepcopy(OLD), copy.deepcopy(TAG),
                                      {'id': 'EXTRA', 'name': 'Extra',
                                       'group_id': 'EXTRA-G', 'group_name': 'Extra Group'}]
        self.blocks('OTHER_TAGS_NOT_PRESERVED')
        self.case[0]['after_tags'] = [copy.deepcopy(OLD), copy.deepcopy(TAG), copy.deepcopy(TAG)]
        self.blocks('DUPLICATE_AFTER_TAG')

    def test_snapshot_existing_tag_must_be_visible_and_mapped(self):
        snap = source(self.case, 'SNAP')
        snap['segments'][0]['text'] = 'CAND-DEMO APP-DEMO'
        self.case[1]['snapshot']['citations'] = [citation(snap)]
        self.case[1]['snapshot']['tags'][0]['citations'] = [citation(snap)]
        self.blocks('EXISTING_TAG_NOT_IN_SNAPSHOT')
        snap['segments'][0]['text'] = 'CAND-DEMO APP-DEMO Existing Item'
        self.case[1]['snapshot']['citations'] = [citation(snap)]
        self.case[1]['snapshot']['tags'][0]['citations'] = [citation(snap)]
        self.blocks('INCOMPLETE_EXISTING_TAG_EVIDENCE')

    def test_snapshot_mapping_may_combine_visible_name_and_library_identifiers(self):
        snap = source(self.case, 'SNAP')
        snap['segments'][0]['text'] = 'CAND-DEMO APP-DEMO Existing Item'
        map_source = make_source('OLDMAP', 'moka_tag_library',
                                 'TAG-OLD Existing Item GROUP-OTHER Other Group')
        self.case[1]['sources'].append(map_source)
        self.case[1]['snapshot']['citations'] = [citation(snap)]
        self.case[1]['snapshot']['tags'][0]['citations'] = [citation(snap), citation(map_source)]
        self.passes()

    def test_same_name_in_another_actual_group_is_not_target_already_present(self):
        snap = source(self.case, 'SNAP')
        snap['segments'][0]['text'] = (
            'CAND-DEMO APP-DEMO TAG-OLD Workflow Review Marker GROUP-OTHER Other Group')
        old_same_name = {**OLD, 'name': TAG['name']}
        self.case[1]['snapshot']['citations'] = [citation(snap)]
        self.case[1]['snapshot']['tags'] = [{**old_same_name, 'citations': [citation(snap)]}]
        self.case[0]['after_tags'] = [old_same_name, copy.deepcopy(TAG)]
        self.passes('add')

    def test_duplicate_or_conflicting_existing_ids_block(self):
        self.case[1]['snapshot']['tags'].append(copy.deepcopy(self.case[1]['snapshot']['tags'][0]))
        self.blocks('DUPLICATE_OR_CONFLICTING_TAG_ID')

    def test_unknown_extra_actions_and_non_add_skip_block(self):
        self.case[0]['action'] = 'replace'
        self.blocks('UNSUPPORTED_ACTION')
        self.case[0]['action'] = 'add'
        self.case[0]['delete'] = [copy.deepcopy(OLD)]
        self.blocks('INVALID_PLAN')

    def test_conflicts_and_unreviewed_facts_block(self):
        self.case[1]['conflict_review']['no_known_conflicts'] = False
        self.blocks('KNOWN_OR_UNREVIEWED_CONFLICT')
        self.case[1]['conflict_review']['no_known_conflicts'] = True
        self.case[1]['conflict_review']['verification_reference'] = ''
        self.blocks('KNOWN_OR_UNREVIEWED_CONFLICT')

    def test_stale_future_and_naive_observation_times_block(self):
        work = source(self.case, 'WORK')
        for observed, expected in [(NOW - dt.timedelta(minutes=61), 'STALE_OR_FUTURE_SOURCE'),
                                   (NOW + dt.timedelta(seconds=1), 'STALE_OR_FUTURE_SOURCE'),
                                   (NOW.replace(tzinfo=None), 'INVALID_CAPTURE_TIME')]:
            with self.subTest(observed=observed):
                work['captured_at'] = observed.isoformat()
                self.blocks(expected)
        work['captured_at'] = (NOW - dt.timedelta(minutes=60)).isoformat()
        self.passes()
        work['captured_at'] = (NOW - dt.timedelta(minutes=61)).isoformat()
        self.assertTrue(self.outcome(max_age_minutes=62)['ready_for_confirmation'])
        self.assertEqual(self.outcome(max_age_minutes=0)['errors'], ['INVALID_FRESHNESS_WINDOW'])
        self.assertEqual(self.outcome(max_age_minutes=1441)['errors'], ['INVALID_FRESHNESS_WINDOW'])

    def test_missing_unknown_duplicate_malformed_data_fails_closed(self):
        self.case[1]['sources'].append(copy.deepcopy(source(self.case, 'WORK')))
        self.blocks('DUPLICATE_SOURCE')
        self.case = fixture()
        del self.case[0]['evidence']
        self.blocks('INVALID_PLAN')
        self.case = fixture()
        self.case[0]['evidence'] = []
        self.blocks('INVALID_WORK_EVIDENCE')
        self.case = fixture()
        self.case[0]['action'] = []
        self.blocks()

    def test_ids_are_not_matched_as_prefixes_of_larger_ids(self):
        src = make_source('OTHER-RECORD', 'moka_record', '')
        self.case[1]['sources'].append(src)
        for longer in ('CAND-DEMO-OTHER', 'CAND-DEMOOTHER', 'CAND-DEMO_OTHER'):
            with self.subTest(longer=longer):
                src['segments'][0]['text'] = 'JOB-DEMO APP-DEMO ' + longer
                self.case[1]['application_link']['citations'] = [citation(src)]
                self.blocks('INCOMPLETE_APPLICATION_EVIDENCE')

    def test_output_does_not_leak_private_ids_or_sources(self):
        output = json.dumps(self.passes())
        for private in ('JOB-DEMO', 'REQ-DEMO', 'CAND-DEMO', 'Workflow Review Marker',
                        'diagnose failure modes'):
            self.assertNotIn(private, output)


@unittest.skipUnless(hasattr(os, 'memfd_create'), 'requires Linux anonymous memory files')
class CliTests(unittest.TestCase):
    def run_cli(self, contents, extra=()):
        fds = []
        try:
            for data in contents:
                fd = os.memfd_create('fictional-test', 0)
                fds.append(fd)
                os.write(fd, data.encode('utf-8'))
                os.lseek(fd, 0, 0)
            cmd = [sys.executable, '-B', str(Path(gate.__file__).resolve())]
            for key, fd in zip(('plan', 'context', 'library'), fds):
                cmd.extend(['--' + key, '/proc/self/fd/' + str(fd)])
            cmd.extend(extra)
            return subprocess.run(cmd, pass_fds=fds, capture_output=True, text=True, check=False)
        finally:
            for fd in fds:
                os.close(fd)

    def test_cli_success_and_block(self):
        case = fixture(now=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1))
        result = self.run_cli([json.dumps(x) for x in case])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(json.loads(result.stdout)['ready_for_confirmation'])
        case[1]['scope']['verified'] = False
        result = self.run_cli([json.dumps(x) for x in case])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['errors'], ['SCOPE_UNVERIFIED'])

    def test_cli_invalid_json_duplicate_keys_and_privacy(self):
        valid = [json.dumps(x) for x in fixture(now=dt.datetime.now(dt.timezone.utc))]
        for invalid in ('{broken', '{"private":"value","private":"other"}', '{"value":NaN}'):
            with self.subTest(invalid=invalid):
                result = self.run_cli([invalid, valid[1], valid[2]])
                self.assertEqual(result.returncode, 3)
                self.assertNotIn('private', result.stderr)
                self.assertEqual(json.loads(result.stderr)['errors'], ['INVALID_INPUT'])


if __name__ == '__main__':
    unittest.main()
