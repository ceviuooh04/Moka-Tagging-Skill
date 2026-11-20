#!/usr/bin/env python3
"""Offline v1.1 and historical v1.0 package, provenance and regression checks."""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
import validate_taxonomy_plan as gate
from test_validate_taxonomy_plan import fixture

BASE = Path(__file__).resolve().parents[1]
ASSETS = BASE / 'assets'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
E_G = {
    'llm general response evaluation','llm safety evaluation','llm coding evaluation','llm preference evaluation',
    'agent task completion evaluation','agent planning and reasoning evaluation','agent tool and interface evaluation',
    'agent workflow and trajectory evaluation','prompt development','general ai training','model fine-tuning','agent training'}
RATES = {'0 USD ≤ Expected Rate ≤ 10 USD','10 USD < Expected Rate ≤ 20 USD',
         '20 USD < Expected Rate ≤ 30 USD','30 USD < Expected Rate ≤ 60 USD',
         '60 USD < Expected Rate ≤ 100 USD'}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def norm(s):
    return ' '.join(s.split())


def doc_nodes(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('word/document.xml'))
    body = root.find(W + 'body')
    return [x for x in body if x.tag == W+'p'], [x for x in body if x.tag == W+'tbl']


def element_text(element):
    return norm(''.join(x.text or '' for x in element.iter(W+'t')))


class PolicyPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load(ASSETS/'tag-library.snapshot.json')
        cls.old = load(ASSETS/'tag-library.v1.0.snapshot.json')
        cls.policy = load(ASSETS/'tagging-policy.json')
        cls.decisions = load(ASSETS/'policy-decisions.json')
        cls.version_doc = ASSETS/'source'/'Global_Talent_Taxonomy_v1.1.docx'

    def test_all_original_and_new_sources_present_with_correct_sha(self):
        for library in (self.old, self.library):
            for source in library['source_documents']:
                with self.subTest(file=source['file']):
                    path = ASSETS/'source'/source['file']
                    self.assertTrue(path.is_file(),path)
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),source['sha256'])
        self.assertEqual(self.old['taxonomy_version'],'1.0')
        self.assertEqual(self.library['taxonomy_version'],'1.1')
        self.assertEqual(self.library['management_spec_version'],'1.0')

    def test_new_group_counts_and_unchanged_nonproject_values(self):
        tags = self.library['tags']
        self.assertEqual(Counter(x['tag_group'] for x in tags),
                         {'country':225,'language':129,'project category':31,
                          'knowledge domain':22,'tier':5,'rate':6})
        pairs={(t['tag_group'],t['tag_value']) for t in tags}
        self.assertEqual(len(pairs),418)
        self.assertTrue({(g,g+' not included') for g in self.library['tag_groups']} <= pairs)
        for group in ('country','language','knowledge domain','tier'):
            old={(t['tag_group'],t['tag_value']) for t in self.old['tags'] if t['tag_group']==group}
            if group == 'language':
                old.discard(('language','farsi'))  # Explicit alias, not a separate canonical value.
            self.assertTrue(old <= pairs, group)
        self.assertIn(('language','persian'),pairs)
        self.assertNotIn(('language','farsi'),pairs)
        self.assertTrue({('rate',value) for value in RATES} <= pairs)
        self.assertTrue({('project category',value) for value in E_G} <= pairs)
        self.assertIn(('knowledge domain','model fine-tuning'),pairs)
        self.assertNotIn(('project category','llm reasoning evaluation'),pairs)
        self.assertNotIn(('project category','agent workflow evaluation'),pairs)

    def test_each_v11_tag_has_matching_source_location(self):
        paras,tables=doc_nodes(self.version_doc)
        for tag in self.library['tags']:
            self.assertTrue(tag.get('sources'))
            for src in tag['sources']:
                self.assertEqual(src['file'],self.version_doc.name)
                loc=src['locator']
                if loc.startswith('docx paragraph:'):
                    n=int(loc.split(':')[-1]); text=element_text(paras[n-1])
                else:
                    m=re.fullmatch(r'docx table:(\d+),row:(\d+),cell:(\d+)',loc)
                    self.assertIsNotNone(m,loc)
                    rows=[x for x in tables[int(m.group(1))-1] if x.tag==W+'tr']
                    cells=[x for x in rows[int(m.group(2))-1] if x.tag==W+'tc']
                    text=element_text(cells[int(m.group(3))-1])
                self.assertIn(norm(tag['tag_value']),text,(tag['tag_group'],tag['tag_value'],loc))

    def test_multiselect_and_draft_status_are_not_fabricated_approval(self):
        self.assertEqual(self.policy['taxonomy_document_version'],'1.1')
        self.assertEqual(self.policy['management_document_version'],'1.0')
        self.assertFalse(self.policy['is_production_configuration'])
        self.assertEqual(self.policy['selection_rules']['project category']['selection_type'],'multi')
        self.assertEqual(self.library['tag_groups']['project category']['selection_type'],'multi')
        self.assertEqual(self.library['tag_groups']['rate']['selection_type'],'single')
        for key in ('current_approved_version_verified','active_status_verified','moka_id_mapping_verified'):
            self.assertIs(self.library[key],False)
        self.assertTrue(all(t['status'] is None and t['moka_tag_id'] is None for t in self.library['tags']))
        p,c,_=fixture()
        self.assertEqual(gate.validate(p,c,self.library)['errors'],['LIBRARY_NOT_APPROVED'])

    def test_confirmed_multiselect_with_v11_real_value_strings_in_demo_fixture(self):
        p,c,lib=fixture()
        values=['agent tool and interface evaluation','agent workflow and trajectory evaluation']
        originals={(x['tag_group'],x['tag_value']):x for x in self.library['tags']}
        lib['tags']=[]; p['changes']=[]
        c['project_category_selection_type']='multi'
        c['project_category_decision_reference']='DEMO-V11-POLICY-REF'
        for i,value in enumerate(values):
            tag=copy.deepcopy(originals[('project category',value)])
            tag.update(status='Active',moka_tag_id=f'DEMO-TAG-{i}')
            lib['tags'].append(tag)
            p['changes'].append({'system':'moka','record_id':'DEMO-RECORD-1','field':'DEMO-TAG-FIELD',
                                 'operation':'add','tag_group':'project category','tag_value':value,
                                 'remote_tag_id':tag['moka_tag_id'],
                                 'evidence':[{'source_id':'DEMO-SOURCE-1','locator':'DEMO-PARAGRAPH-1',
                                              'excerpt':'DEMO continuous evidence'}]})
        out=gate.validate(p,c,lib)
        self.assertTrue(out['ready_for_confirmation'],out)
        self.assertFalse(out['authorized']); self.assertFalse(out['executed'])

    def test_original_and_new_user_decisions_recorded(self):
        self.assertTrue(any(d.get('decision_id')=='PROJECT_CATEGORY_SELECTION_2026_11_17' and
                            d.get('selection_type')=='multi' for d in self.decisions['decisions']))
        self.assertTrue(any(d.get('decision_id')=='TAXONOMY_V11_REQUEST_2026_11_17' and
                            '不冒充' in d.get('limitation','') for d in self.decisions['decisions']))

    def test_current_source_applies_project_independent_tiers(self):
        paras, _ = doc_nodes(self.version_doc)
        text = '\n'.join(element_text(p) for p in paras)
        for required in (
            'Tier assessments are contextual to each specific project and Target Profile.',
            'Each project assessment is recorded independently;',
            'There is no candidate-level highest-Tier aggregation across projects.',
            'An assessment for one project must not automatically overwrite or determine the Tier assessment of another project.',
            "Preserve each project's assessment evidence and historical values.",
            'Never infer a Tier from missing evidence or an unassessed project.',
            'Conditional — when the applicable ATS Talent Pool record requires expected hourly rate classification; not for Benchmark.',
            'Alias: farsi (recognized as an alias of the canonical Tag persian',
            'Status: Draft for review — pending Admin approval and Moka publication',
        ):
            self.assertIn(required, text)
        for obsolete in (
            'The candidate profile stores one Tier: the highest',
            'The candidate profile holds one Tier: the highest',
            'The candidate-level Tier stored on the candidate profile is single-select: record the highest',
            'classificationclassification',
        ):
            self.assertNotIn(obsolete, text)

    def test_policy_data_disallows_cross_project_rollup_and_marks_draft(self):
        selection = self.policy['selection_rules']['tier']
        tier = self.policy['tier_policy']
        self.assertEqual(selection['multiple_project_selection'], 'independent_per_project_no_aggregation')
        self.assertIs(selection['candidate_profile_tier_field_prohibited'], False)
        self.assertEqual(tier['cross_project_aggregation'], 'none')
        self.assertIs(tier['automatic_cross_project_overwrite'], False)
        self.assertIs(tier['system_project_isolation_verified'], False)
        self.assertEqual(self.policy['selection_rules']['rate']['system_applicability'],
                         {'ATS Talent Pool': True, 'Benchmark': False})
        old = next(d for d in self.decisions['decisions']
                   if d['decision_id'] == 'TIER_CANDIDATE_HIGHEST_VALID_COMPLETED_2026_11_17')
        self.assertTrue(old['status'].startswith('historical_only'))
        new = next(d for d in self.decisions['decisions']
                   if d['decision_id'] == 'PROJECT_INDEPENDENT_TIER_RATE_LANGUAGE_DRAFT_REVISION_2026_11_19')
        self.assertEqual(new['status'], 'draft_pending_admin_approval_and_moka_publication')
        self.assertEqual(new['language']['canonical'], 'persian')
        self.assertEqual(new['language']['alias'], 'farsi')
        self.assertEqual(new['source_sha256'], hashlib.sha256(self.version_doc.read_bytes()).hexdigest())

    def test_user_country_inference_guidance_is_preserved_without_claiming_verification(self):
        country = self.policy['selection_rules']['country']
        self.assertEqual(country['classification_basis'], 'candidate_actual_location')
        self.assertIs(country['inference_is_verified_fact'], False)
        self.assertIn('infer_from_consistent_sufficient_evidence', country['missing_location'])
        decisions = {d['decision_id']: d for d in self.decisions['decisions']}
        self.assertEqual(country['policy_decision_reference'], 'COUNTRY_EVIDENCE_BASED_INFERENCE_2026_11_20')
        self.assertEqual(decisions['COUNTRY_ACTUAL_LOCATION_2026_11_17']['superseded_by'], country['policy_decision_reference'])
        self.assertIn('无需再单独确认', decisions[country['policy_decision_reference']]['source_detail'])
        guide = (BASE/'references'/'evidence-based-recommendations.md').read_text(encoding='utf-8')
        for text in ('美国电话号码和过去美国求学经历', '申请美国岗位', '推断而非候选人明确填写的现居地',
                     '冲突', '不把国籍、姓名当所在地'):
            self.assertIn(text, guide)
        self.assertIn('references/evidence-based-recommendations.md', (BASE/'SKILL.md').read_text(encoding='utf-8'))

    def test_tier_provisional_recommendation_does_not_authorize_write(self):
        tier = self.policy['tier_policy']
        self.assertIs(tier['provisional_recommendation_without_note_allowed'], True)
        self.assertIs(tier['provisional_recommendation_without_approved_project_rubric_allowed'], True)
        self.assertIs(tier['recommendation_is_formal_assessment'], False)
        self.assertIs(tier['recommendation_is_write_authorization'], False)
        self.assertIs(tier['system_project_isolation_verified'], False)
        decision = next(d for d in self.decisions['decisions'] if d['decision_id'] == tier['policy_decision_reference'])
        self.assertIn('没有 Note', decision['source_detail'])
        guide = (BASE/'references'/'evidence-based-recommendations.md').read_text(encoding='utf-8')
        for text in ('专业知识、相关实践、任务复杂度、独立性、专业判断、对决定与结果的责任',
                     '`tier 1`', '`tier 2`', '`tier 3`', '`tier 4`',
                     '没有 Note 或已批准项目细分 rubric', '不是正式评估或自动写入授权', '仍阻断写入'):
            self.assertIn(text, guide)
        p, c, lib = fixture()
        target = next(t for t in lib['tags'] if t['tag_group'] == 'tier' and t['tag_value'] == 'tier 3')
        p['changes'][0].update(tag_group='tier', tag_value='tier 3', remote_tag_id=target['moka_tag_id'])
        out = gate.validate(p, c, lib)
        self.assertIn('TIER_PROJECT_CONTEXT_UNSUPPORTED', out['errors'])
        self.assertFalse(out['authorized'])
        self.assertFalse(out['executed'])

    def test_default_templates_never_self_authorize(self):
        names=('taxonomy-plan.example.json','taxonomy-context.example.json','taxonomy-library.example.json')
        plan,context,library=(load(BASE/'templates'/n) for n in names)
        out=gate.validate(plan,context,library)
        self.assertFalse(out['ready_for_confirmation'])
        self.assertFalse(out['authorized']);self.assertFalse(out['executed'])
        p=load(BASE/'templates'/'taxonomy-exception-plan.example.json')
        c=load(BASE/'templates'/'taxonomy-exception-context.example.json')
        self.assertFalse(gate.validate(p,c,library)['ready_for_confirmation'])


if __name__=='__main__':
    unittest.main(verbosity=2)
