#!/usr/bin/env python3
"""Offline structural gate for ONE job-project marker on ONE Moka edit target.

Run (all inputs must be private JSON files):
  python3 validate_requisition_marker_plan.py --plan PLAN --context CONTEXT \
      --library LIBRARY [--max-age-minutes 60]
Exit 0: structurally ready for confirmation; 2: blocked; 3: invalid CLI/JSON.
No network, persistent writes or remote actions. Output never includes supplied IDs,
source text, references or paths. This is NOT a Taxonomy Project Category gate.
A marker denotes the job's work, NOT the candidate's actual skills or experience.

Contract (all object keys below are required, except where marked optional). IDs,
names, references and explanations are nonempty strings copied from actual records;
never invent IDs, roles, versions, quotes or verification references. Lists named
`citations` are nonempty. A citation is {"source_id":..., "locator":..., "excerpt":...}:
excerpt must occur *contiguously and exactly* in that source's matching segment.

PLAN:
  target: {job_id, requisition_id, application_id, candidate_id,
           edit_target: {type: "application" | "candidate", id}}
  tag: {id, name, group_id, group_name}; action: "add" | "skip"
  after_tags: [{id, name, group_id, group_name}, ...]  # complete intended result
  evidence: [citation, ...]   # actual work-content segment, never just the title
  semantic_review: {decision: "match", reasoning,
                    subject: "job_work_not_candidate_capability",
                    work_content_verified: true, verification_reference}
The caller/agent must independently reason from the cited duties to the intended
marker; this gate deliberately does no semantic or keyword matching. If the real
judgment is no match or uncertain, do not relabel it as match; the plan blocks.

CONTEXT:
  sources: [{source_id, kind, system, reference, captured_at, verified: true,
             verification_reference, record_id (only required for job/requisition),
             segments: [{locator, section, text}, ...]}, ...]
  Source kinds: job, requisition, moka_record, moka_tag_snapshot,
  moka_tag_library, user_instruction. `system` and `reference` are the actual
  source and a re-findable record/location; they need not be URLs. `captured_at`
  is the actual observation time in timezone-aware ISO-8601, NOT the original
  document's creation time. Sections: work_content, title, other. No source
  may be stale or in the future under the supplied window. Work evidence must
  be from the target job/requisition record's actual work_content section;
  section classification is itself an independent caller verification.
  job_requisition_link: {job_id, requisition_id, verified: true,
                         verification_reference, citations}
  application_link: {job_id, application_id, candidate_id, verified: true,
                     verification_reference, citations}
  edit_target_check: {type, id, verified: true, verification_reference, citations}
  Each link's combined exact excerpts must contain the actual relevant IDs;
  this is a consistency check, not proof that their relationship is genuine.
  scope: {job_id, tag_id, action: "add", targets: "all_applications_for_job"
          OR [{application_id, candidate_id}, ...], verified: true,
          verification_reference, citations}
  Scope citations must refer to actual user_instruction source(s). The caller
  must interpret all current instructions, authority, constraints and changes;
  the gate does not parse or establish authorization. `skip` needs this same
  add scope, but performs no write. A whole-job scope must actually include all
  applications rather than just some candidates or statuses.
  effects: {complete: true, verification_reference,
            impacted_applications: [{job_id, application_id, candidate_id,
                                     citations}, ...]}
  Record ALL applications affected by the actual edit target, including shared
  candidate-profile tags and cross-job propagation. Verify completeness from the
  real Moka behavior. The planned application must be within scope. When editing
  the candidate profile, other applications for the SAME candidate can show the
  tag as an inherent shared-profile effect, even if their jobs are outside the
  requested scope; record and disclose them, do not independently edit them, and
  stop if sharing is unverified or the user restricts those effects. When editing
  an application directly, no other application can be included. Do not claim
  unknown systems were checked.
  snapshot: {edit_target: {type, id}, complete: true,
             verification_reference, citations,
             tags: [{id, name, group_id, group_name, citations}, ...]}
  Snapshot citation(s) must include the edit target ID. Each existing tag's
  combined citations must contain its exact ID, name, group ID and group name;
  at least one of its citations must be a moka_tag_snapshot that contains the
  exact tag name. A moka_tag_library source can supplement snapshot mappings.
  Completeness includes all groups, pagination and loaded tags; never infer an
  empty snapshot from failure to load. No replacement or deletion is supported.
  conflict_review: {no_known_conflicts: true, verification_reference}

LIBRARY:
  tag: {id, name, group_id, group_name, active: true, verified: true,
        verification_reference, citations,
        active_status_verified: true, active_status_reference, active_status_citations,
        job_marker_group_verified: true, job_marker_group_reference,
        distinct_from_taxonomy_project_category_verified: true,
        distinct_from_taxonomy_project_category_reference,
        taxonomy_project_category_group_id (optional, only if actually known)}
  Library citations must be from the actual Moka library and collectively include
  the tag's ID, name, group ID and group name. Verify the actual enabled status,
  cite its actual status separately along with the tag and group IDs, verify the
  real group and mapping, and the distinction from Taxonomy Project Category;
  no same-name mapping is inferred. If an actual Taxonomy group ID is known and
  equals this group ID, the plan blocks. Active status is an asserted, independently
  checked fact: an excerpt's mere presence does not prove it.

Verification/reference fields record genuine checks, not credentials or fake
certification roles. The gate cannot establish source authenticity, completeness,
semantics, status, freshness beyond timestamps, permission or execution. Re-read
identity, scope, requisition, actual group/status, full tags and sharing immediately
before any authorized action, apply the platform's confirmation requirements, then
verify all tags afterwards. A structural pass is neither permission nor evidence
of a write. Known conflicts, uncertainty and changes require stopping for review.
"""
import argparse
import datetime as dt
import json
import re
import sys


class Blocked(Exception):
    pass


def require(test, code):
    if not test:
        raise Blocked(code)


def obj(value, required, optional=(), code='INVALID_STRUCTURE'):
    require(isinstance(value, dict), code)
    require(set(required).issubset(value) and not (set(value) - set(required) - set(optional)), code)
    return value


def text(value, code='INVALID_TEXT'):
    require(isinstance(value, str) and bool(value.strip()) and value == value.strip(), code)
    return value


def listing(value, code='INVALID_LIST', nonempty=False):
    require(isinstance(value, list) and (bool(value) or not nonempty), code)
    return value


def asserted(value, reference, code):
    require(value is True, code)
    text(reference, code)


def item_tag(tag, with_citations=False):
    fields = ['id', 'name', 'group_id', 'group_name']
    obj(tag, fields + (['citations'] if with_citations else []), code='INVALID_TAG')
    for key in fields:
        text(tag[key], 'INVALID_TAG')
    return tuple(tag[key] for key in fields)


def target_id(target):
    obj(target, ['type', 'id'], code='INVALID_EDIT_TARGET')
    require(target['type'] in ('application', 'candidate'), 'INVALID_EDIT_TARGET')
    text(target['id'], 'INVALID_EDIT_TARGET')
    return target['type'], target['id']


def parse_datetime(value):
    text(value, 'INVALID_CAPTURE_TIME')
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'INVALID_CAPTURE_TIME')
        return parsed.astimezone(dt.timezone.utc)
    except (ValueError, OverflowError):
        raise Blocked('INVALID_CAPTURE_TIME') from None


def token_in(token, body):
    # A shorter ID must not match an alphanumeric or hyphenated longer ID.
    return bool(re.search(r'(?<![\w-])' + re.escape(token) + r'(?![\w-])', body))


def validate(plan, context, library, *, now=None, max_age_minutes=60):
    """Return privacy-preserving structural result; `now` is for deterministic tests.

    Real callers should omit `now` so the actual clock is used. The window is an
    upper bound only, not proof that records are current or unchanged.
    """
    output = {'ready_for_confirmation': False, 'action': 'blocked', 'errors': [],
              'authorized': False, 'executed': False, 'semantic_match_proven': False,
              'source_authenticity_proven': False, 'candidate_capability_inferred': False,
              'pre_write_reread_required': True, 'post_write_reread_required': True}
    try:
        require(isinstance(max_age_minutes, (int, float)) and not isinstance(max_age_minutes, bool)
                and 0 < max_age_minutes <= 1440, 'INVALID_FRESHNESS_WINDOW')
        if now is None:
            now = dt.datetime.now(dt.timezone.utc)
        require(isinstance(now, dt.datetime) and now.tzinfo is not None and
                now.utcoffset() is not None, 'INVALID_CLOCK')
        now = now.astimezone(dt.timezone.utc)
        obj(plan, ['target', 'tag', 'action', 'after_tags', 'evidence', 'semantic_review'], code='INVALID_PLAN')
        obj(context, ['sources', 'job_requisition_link', 'application_link', 'edit_target_check',
                      'scope', 'effects', 'snapshot', 'conflict_review'], code='INVALID_CONTEXT')
        obj(library, ['tag'], code='INVALID_LIBRARY')

        sources = {}
        for source in listing(context['sources'], 'INVALID_SOURCES', nonempty=True):
            obj(source, ['source_id', 'kind', 'system', 'reference', 'captured_at', 'verified',
                         'verification_reference', 'segments'], ['record_id'], 'INVALID_SOURCE')
            sid = text(source['source_id'], 'INVALID_SOURCE')
            require(sid not in sources, 'DUPLICATE_SOURCE')
            require(source['kind'] in ('job', 'requisition', 'moka_record', 'moka_tag_snapshot',
                                       'moka_tag_library', 'user_instruction'), 'INVALID_SOURCE_KIND')
            text(source['system'], 'INVALID_SOURCE')
            text(source['reference'], 'INVALID_SOURCE')
            asserted(source['verified'], source['verification_reference'], 'UNVERIFIED_SOURCE')
            captured = parse_datetime(source['captured_at'])
            age = (now - captured).total_seconds()
            require(0 <= age <= max_age_minutes * 60, 'STALE_OR_FUTURE_SOURCE')
            if source['kind'] in ('job', 'requisition'):
                text(source.get('record_id'), 'INVALID_WORK_SOURCE')
            elif 'record_id' in source:
                text(source['record_id'], 'INVALID_SOURCE')
            locators = set()
            for seg in listing(source['segments'], 'INVALID_SEGMENTS', nonempty=True):
                obj(seg, ['locator', 'section', 'text'], code='INVALID_SEGMENT')
                locator = text(seg['locator'], 'INVALID_SEGMENT')
                require(locator not in locators, 'DUPLICATE_LOCATOR')
                locators.add(locator)
                require(seg['section'] in ('work_content', 'title', 'other'), 'INVALID_SEGMENT')
                require(isinstance(seg['text'], str) and bool(seg['text'].strip()), 'INVALID_SEGMENT')
            sources[sid] = source

        def citations(items, kinds, code):
            records = []
            for citation in listing(items, code, nonempty=True):
                obj(citation, ['source_id', 'locator', 'excerpt'], code=code)
                sid = text(citation['source_id'], code)
                loc = text(citation['locator'], code)
                excerpt = text(citation['excerpt'], code)
                require(sid in sources and sources[sid]['kind'] in kinds, code)
                source = sources[sid]
                segments = [s for s in source['segments'] if s['locator'] == loc]
                require(len(segments) == 1 and excerpt in segments[0]['text'], code)
                records.append((source, segments[0], excerpt))
            return records

        def has_tokens(records, tokens, code):
            for token in tokens:
                require(any(token_in(token, excerpt) for _, _, excerpt in records), code)

        target = obj(plan['target'], ['job_id', 'requisition_id', 'application_id', 'candidate_id',
                                      'edit_target'], code='INVALID_TARGET')
        for key in ('job_id', 'requisition_id', 'application_id', 'candidate_id'):
            text(target[key], 'INVALID_TARGET')
        edit = target_id(target['edit_target'])
        require(edit[1] == target['application_id' if edit[0] == 'application' else 'candidate_id'],
                'EDIT_TARGET_MISMATCH')
        tag = item_tag(plan['tag'])
        require(plan['action'] in ('add', 'skip'), 'UNSUPPORTED_ACTION')

        review = obj(plan['semantic_review'], ['decision', 'reasoning', 'subject',
                     'work_content_verified', 'verification_reference'], code='INVALID_SEMANTIC_REVIEW')
        require(review['decision'] == 'match', 'SEMANTIC_MATCH_NOT_ASSERTED')
        require(review['subject'] == 'job_work_not_candidate_capability', 'WRONG_SEMANTIC_SUBJECT')
        text(review['reasoning'], 'MISSING_REASONING')
        asserted(review['work_content_verified'], review['verification_reference'], 'WORK_CONTENT_UNVERIFIED')
        ev = citations(plan['evidence'], {'job', 'requisition'}, 'INVALID_WORK_EVIDENCE')
        for src, seg, excerpt in ev:
            require(seg['section'] == 'work_content', 'TITLE_OR_NON_WORK_EVIDENCE')
            require(src['record_id'] == target['job_id' if src['kind'] == 'job' else 'requisition_id'],
                    'CROSS_JOB_WORK_EVIDENCE')
            titles = [s['text'].strip() for s in src['segments'] if s['section'] == 'title']
            require(excerpt.strip() not in titles, 'TITLE_OR_NON_WORK_EVIDENCE')

        joblink = obj(context['job_requisition_link'], ['job_id', 'requisition_id', 'verified',
                      'verification_reference', 'citations'], code='INVALID_JOB_REQUISITION_LINK')
        asserted(joblink['verified'], joblink['verification_reference'], 'UNVERIFIED_JOB_REQUISITION_LINK')
        require(joblink['job_id'] == target['job_id'] and joblink['requisition_id'] == target['requisition_id'],
                'JOB_REQUISITION_MISMATCH')
        rec = citations(joblink['citations'], {'job', 'requisition', 'moka_record'}, 'INVALID_JOB_LINK_EVIDENCE')
        for src, _, _ in rec:
            if src['kind'] in ('job', 'requisition'):
                require(src['record_id'] == target['job_id' if src['kind'] == 'job' else 'requisition_id'],
                        'CROSS_JOB_LINK_EVIDENCE')
        has_tokens(rec, (target['job_id'], target['requisition_id']), 'INCOMPLETE_JOB_LINK_EVIDENCE')

        app = obj(context['application_link'], ['job_id', 'application_id', 'candidate_id', 'verified',
                  'verification_reference', 'citations'], code='INVALID_APPLICATION_LINK')
        asserted(app['verified'], app['verification_reference'], 'UNVERIFIED_APPLICATION_LINK')
        require(all(app[k] == target[k] for k in ('job_id', 'application_id', 'candidate_id')),
                'APPLICATION_LINK_MISMATCH')
        rec = citations(app['citations'], {'moka_record'}, 'INVALID_APPLICATION_EVIDENCE')
        has_tokens(rec, (target['job_id'], target['application_id'], target['candidate_id']),
                   'INCOMPLETE_APPLICATION_EVIDENCE')
        check = obj(context['edit_target_check'], ['type', 'id', 'verified', 'verification_reference',
                    'citations'], code='INVALID_EDIT_TARGET_CHECK')
        asserted(check['verified'], check['verification_reference'], 'EDIT_TARGET_UNVERIFIED')
        require((check['type'], check['id']) == edit, 'EDIT_TARGET_MISMATCH')
        rec = citations(check['citations'], {'moka_record'}, 'INVALID_EDIT_TARGET_EVIDENCE')
        has_tokens(rec, (edit[1],), 'INCOMPLETE_EDIT_TARGET_EVIDENCE')

        scope = obj(context['scope'], ['job_id', 'tag_id', 'action', 'targets', 'verified',
                    'verification_reference', 'citations'], code='INVALID_SCOPE')
        asserted(scope['verified'], scope['verification_reference'], 'SCOPE_UNVERIFIED')
        require(scope['job_id'] == target['job_id'] and scope['tag_id'] == tag[0]
                and scope['action'] == 'add', 'OUT_OF_SCOPE')
        citations(scope['citations'], {'user_instruction'}, 'INVALID_SCOPE_EVIDENCE')
        if scope['targets'] == 'all_applications_for_job':
            allowed = None
        else:
            allowed = set()
            for entry in listing(scope['targets'], 'INVALID_SCOPE_TARGETS', nonempty=True):
                obj(entry, ['application_id', 'candidate_id'], code='INVALID_SCOPE_TARGETS')
                pair = (text(entry['application_id'], 'INVALID_SCOPE_TARGETS'),
                        text(entry['candidate_id'], 'INVALID_SCOPE_TARGETS'))
                require(pair not in allowed, 'DUPLICATE_SCOPE_TARGET')
                allowed.add(pair)
        require(allowed is None or (target['application_id'], target['candidate_id']) in allowed,
                'OUT_OF_SCOPE')

        effects = obj(context['effects'], ['complete', 'verification_reference', 'impacted_applications'],
                      code='INVALID_EFFECTS')
        asserted(effects['complete'], effects['verification_reference'], 'SHARED_EFFECTS_UNVERIFIED')
        impacted = set()
        for impact in listing(effects['impacted_applications'], 'INVALID_EFFECTS', nonempty=True):
            obj(impact, ['job_id', 'application_id', 'candidate_id', 'citations'], code='INVALID_EFFECTS')
            ids = tuple(text(impact[k], 'INVALID_EFFECTS') for k in ('job_id', 'application_id', 'candidate_id'))
            require(ids not in impacted, 'DUPLICATE_IMPACT')
            impacted.add(ids)
            require(ids[2] == target['candidate_id'], 'IMPACT_OUT_OF_SCOPE')
            if edit[0] == 'application':
                require(ids == (target['job_id'], target['application_id'], target['candidate_id']),
                        'IMPACT_OUT_OF_SCOPE')
            rec = citations(impact['citations'], {'moka_record'}, 'INVALID_IMPACT_EVIDENCE')
            has_tokens(rec, ids, 'INCOMPLETE_IMPACT_EVIDENCE')
        require((target['job_id'], target['application_id'], target['candidate_id']) in impacted,
                'TARGET_NOT_IN_IMPACTS')

        lib = obj(library['tag'], ['id', 'name', 'group_id', 'group_name', 'active', 'verified',
                  'verification_reference', 'citations', 'active_status_verified',
                  'active_status_reference', 'active_status_citations', 'job_marker_group_verified',
                  'job_marker_group_reference', 'distinct_from_taxonomy_project_category_verified',
                  'distinct_from_taxonomy_project_category_reference'],
                  ['taxonomy_project_category_group_id'], 'INVALID_LIBRARY_TAG')
        require(tuple(lib[k] for k in ('id', 'name', 'group_id', 'group_name')) == tag, 'LIBRARY_TAG_MISMATCH')
        require(lib['active'] is True, 'TAG_NOT_ACTIVE')
        asserted(lib['verified'], lib['verification_reference'], 'LIBRARY_TAG_UNVERIFIED')
        asserted(lib['active_status_verified'], lib['active_status_reference'], 'ACTIVE_STATUS_UNVERIFIED')
        status_rec = citations(lib['active_status_citations'], {'moka_tag_library'}, 'INVALID_ACTIVE_STATUS_EVIDENCE')
        has_tokens(status_rec, (tag[0], tag[2]), 'INCOMPLETE_ACTIVE_STATUS_EVIDENCE')
        asserted(lib['job_marker_group_verified'], lib['job_marker_group_reference'], 'MARKER_GROUP_UNVERIFIED')
        asserted(lib['distinct_from_taxonomy_project_category_verified'],
                 lib['distinct_from_taxonomy_project_category_reference'], 'TAXONOMY_GROUP_DISTINCTION_UNVERIFIED')
        if 'taxonomy_project_category_group_id' in lib:
            require(text(lib['taxonomy_project_category_group_id'], 'INVALID_TAXONOMY_GROUP_ID') != tag[2],
                    'TAXONOMY_GROUP_CONFLICT')
        rec = citations(lib['citations'], {'moka_tag_library'}, 'INVALID_LIBRARY_EVIDENCE')
        has_tokens(rec, tag, 'INCOMPLETE_LIBRARY_EVIDENCE')

        snap = obj(context['snapshot'], ['edit_target', 'complete', 'verification_reference', 'citations',
                   'tags'], code='INVALID_SNAPSHOT')
        require(target_id(snap['edit_target']) == edit, 'SNAPSHOT_TARGET_MISMATCH')
        asserted(snap['complete'], snap['verification_reference'], 'SNAPSHOT_INCOMPLETE')
        rec = citations(snap['citations'], {'moka_tag_snapshot'}, 'INVALID_SNAPSHOT_EVIDENCE')
        has_tokens(rec, (edit[1],), 'INCOMPLETE_SNAPSHOT_EVIDENCE')
        existing, ids, group_names = set(), {}, {}
        for entry in listing(snap['tags'], 'INVALID_SNAPSHOT'):
            t = item_tag(entry, with_citations=True)
            require(t not in existing and t[0] not in ids, 'DUPLICATE_OR_CONFLICTING_TAG_ID')
            existing.add(t)
            ids[t[0]] = t
            require(t[2] not in group_names or group_names[t[2]] == t[3], 'CONFLICTING_GROUP_ID')
            group_names[t[2]] = t[3]
            rec = citations(entry['citations'], {'moka_tag_snapshot', 'moka_tag_library'},
                            'INVALID_EXISTING_TAG_EVIDENCE')
            require(any(s['kind'] == 'moka_tag_snapshot' and token_in(t[1], x) for s, _, x in rec),
                    'EXISTING_TAG_NOT_IN_SNAPSHOT')
            has_tokens(rec, t, 'INCOMPLETE_EXISTING_TAG_EVIDENCE')
        require(tag[0] not in ids or ids[tag[0]] == tag, 'TARGET_TAG_ID_CONFLICT')
        require(tag[2] not in group_names or group_names[tag[2]] == tag[3], 'TARGET_GROUP_ID_CONFLICT')
        require((plan['action'] == 'skip') == (tag in existing), 'ADD_SKIP_MISMATCH')
        expected = set(existing)
        expected.add(tag)
        after = [item_tag(t) for t in listing(plan['after_tags'], 'INVALID_AFTER_TAGS')]
        require(len(after) == len(set(after)), 'DUPLICATE_AFTER_TAG')
        require(set(after) == expected, 'OTHER_TAGS_NOT_PRESERVED')
        conflict = obj(context['conflict_review'], ['no_known_conflicts', 'verification_reference'],
                       code='INVALID_CONFLICT_REVIEW')
        asserted(conflict['no_known_conflicts'], conflict['verification_reference'], 'KNOWN_OR_UNREVIEWED_CONFLICT')
        output['ready_for_confirmation'] = True
        output['action'] = plan['action']
    except Blocked as exc:
        output['errors'] = [str(exc)]
    except (TypeError, KeyError, ValueError, OverflowError):
        # Malformed caller data must fail closed, never leak its contents.
        output['errors'] = ['INVALID_STRUCTURE']
    return output


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(_):
    raise ValueError('invalid JSON constant')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline structural gate; no authorization or write.')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--library', required=True)
    parser.add_argument('--max-age-minutes', type=float, default=60,
                        help='Upper age limit for all observations (default 60; >0 and <=1440).')
    args = parser.parse_args(argv)
    try:
        documents = []
        for name in (args.plan, args.context, args.library):
            with open(name, encoding='utf-8') as handle:
                documents.append(json.load(handle, object_pairs_hook=_no_duplicate_keys,
                                           parse_constant=_reject_constant))
    except (OSError, UnicodeError, ValueError, RecursionError):
        print(json.dumps({'ready_for_confirmation': False, 'action': 'blocked',
                          'errors': ['INVALID_INPUT'], 'authorized': False, 'executed': False}), file=sys.stderr)
        return 3
    result = validate(*documents, max_age_minutes=args.max_age_minutes)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['ready_for_confirmation'] else 2


if __name__ == '__main__':
    sys.exit(main())
