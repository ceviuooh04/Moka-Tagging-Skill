#!/usr/bin/env python3
"""Offline gate for one Moka Rate-tag addition, never authorization or execution.

The caller must independently verify provenance, account permissions, current tag
state, the approved current version and the actual Moka tag ID mapping. Do not
supply invented approvals or IDs merely to make this validator pass.
For mixed-group work, independently bind both gates to the same application,
current version, complete old tags, and final payload. A snapshot is not proof.
Version 1.1 and all exception plans require context.current_tags_verified and
current_tag_groups_verified plus their respective verification references;
library current-version, Active-status and Moka-mapping references are required.
Version 1.1 and all exception plans also require the asserted completeness and
reference for the exact five Active v1.1 bands. A 'rate not included' plan
additionally requires a mapped Active exception and a proven amount above 100.
Claims and references are not proof of truth, account access or authorization.
For v1.1 and exceptions, programmatic callers must pass amounts/boundaries as
decimal strings, integers or Decimal, never binary floats; a float may already
have been rounded before reaching this gate. The CLI parses JSON decimals exactly.
"""
import argparse
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse


RATE_EXCEPTION = 'rate not included'
# These are the five existing USD/hour labels, not a newly defined range.
V11_INTERVALS = {
    '0 USD ≤ Expected Rate ≤ 10 USD': (Decimal('0'), Decimal('10'), True, True),
    '10 USD < Expected Rate ≤ 20 USD': (Decimal('10'), Decimal('20'), False, True),
    '20 USD < Expected Rate ≤ 30 USD': (Decimal('20'), Decimal('30'), False, True),
    '30 USD < Expected Rate ≤ 60 USD': (Decimal('30'), Decimal('60'), False, True),
    '60 USD < Expected Rate ≤ 100 USD': (Decimal('60'), Decimal('100'), False, True),
}
PLACEHOLDERS = frozenset({
    'unknown', 'unspecified', 'n/a', 'na', 'none', 'null', 'nil', 'not available',
    'not applicable', 'no data', 'no information', 'not provided', 'not assessed',
    'unassessed', 'unverified', 'tbd', 'todo', '待定', '未知', '无', '未提供', '未评估',
})
# Keep aligned with validate_taxonomy_plan.UNKNOWN_GROUPS. These values cannot
# establish the actual old tag group, even when the caller claims verification.
UNKNOWN_GROUPS = frozenset({
    'other', 'others', 'other group', 'other groups', 'other tags', 'unknown',
    'unknown group', 'unspecified', 'unassigned', 'unclassified', 'not classified',
    'not known', 'not sure', 'none', 'null', 'n/a', 'na', 'unverified', 'misc',
    'miscellaneous', '其他', '其它', '其他组', '其它组', '未知', '未知组', '未分类',
    '未分组', '不明', '待确认', '待核实', '待定',
})


class Blocked(Exception):
    pass


def need(condition, code):
    if not condition:
        raise Blocked(code)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def normalize(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def normalized_group(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def meaningful(value):
    if not text(value):
        return False
    normalized = ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
    return normalized not in PLACEHOLDERS and bool(re.search(r'\w', normalized))


def number(value):
    need(isinstance(value, (str, int, float, Decimal)) and not isinstance(value, bool), 'INVALID_RATE')
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise Blocked('INVALID_RATE')
    need(result.is_finite(), 'INVALID_RATE')
    return result


def validate(plan, context, library):
    try:
        _validate(plan, context, library)
        return {'ready_for_confirmation': True, 'authorized': False, 'executed': False, 'errors': []}
    except Blocked as exc:
        return {'ready_for_confirmation': False, 'authorized': False, 'executed': False, 'errors': [str(exc)]}
    except Exception:
        return {'ready_for_confirmation': False, 'authorized': False, 'executed': False, 'errors': ['MALFORMED_INPUT']}


def _validate(plan, context, library):
    need(all(isinstance(x, dict) for x in (plan, context, library)), 'MALFORMED_INPUT')
    candidate, identity = plan.get('candidate'), context.get('candidate')
    need(isinstance(candidate, dict) and isinstance(identity, dict), 'IDENTITY_UNVERIFIED')
    need(candidate.get('match_status') == identity.get('match_status') == 'verified', 'IDENTITY_UNVERIFIED')
    need(text(candidate.get('moka_id')) and candidate['moka_id'] == identity.get('moka_id'), 'IDENTITY_MISMATCH')
    need(text(candidate.get('name')) and candidate['name'] == identity.get('name'), 'IDENTITY_MISMATCH')
    record_id = candidate['moka_id']

    for key in ('allowed_record_ids', 'allowed_fields', 'allowed_operations', 'current_tags'):
        mapping = context.get(key)
        need(isinstance(mapping, dict) and isinstance(mapping.get('moka'), list), 'MALFORMED_CONTEXT')
    need(context.get('current_tags_verified') is True, 'CURRENT_TAGS_UNVERIFIED')
    need(record_id in context['allowed_record_ids']['moka'], 'TARGET_NOT_ALLOWED')
    current = context['current_tags']['moka']
    need(all(isinstance(t, dict) and text(t.get('tag_group')) and text(t.get('tag_value')) for t in current), 'CURRENT_TAGS_INVALID')
    need(all(normalized_group(t['tag_group']) not in UNKNOWN_GROUPS for t in current), 'CURRENT_TAG_GROUP_UNKNOWN')
    old_rate = [t['tag_value'] for t in current if normalized_group(t['tag_group']) == 'rate']
    need(not old_rate, 'EXISTING_RATE_TAG')

    changes = plan.get('changes')
    need(isinstance(changes, list) and len(changes) == 1 and isinstance(changes[0], dict), 'CHANGE_COUNT_INVALID')
    change = changes[0]
    need(change.get('system') == 'moka' and change.get('record_id') == record_id, 'TARGET_NOT_ALLOWED')
    need(change.get('field') == 'candidate_custom_tags' and change['field'] in context['allowed_fields']['moka'], 'FIELD_NOT_ALLOWED')
    need(change.get('operation') == 'add' and change['operation'] in context['allowed_operations']['moka'], 'OPERATION_NOT_ALLOWED')
    need(change.get('tag_group') == 'rate' and text(change.get('tag_value')), 'UNKNOWN_TAG_GROUP')
    need(text(change.get('remote_tag_id')), 'MOKA_MAPPING_UNVERIFIED')
    exception = change['tag_value'] == RATE_EXCEPTION

    need(library.get('current_approved_version_verified') is True and text(library.get('approval_reference')), 'LIBRARY_NOT_APPROVED')
    need(library.get('active_status_verified') is True, 'ACTIVE_STATUS_UNVERIFIED')
    need(library.get('moka_id_mapping_verified') is True, 'MOKA_MAPPING_UNVERIFIED')
    need(text(plan.get('taxonomy_version')) and plan['taxonomy_version'] == library.get('taxonomy_version'), 'TAXONOMY_VERSION_MISMATCH')
    version_11 = library['taxonomy_version'].strip().casefold() in ('1.1', 'v1.1')
    if version_11 or exception:
        need(meaningful(context.get('current_tags_verification_reference')), 'CURRENT_TAGS_UNVERIFIED')
        need(context.get('current_tag_groups_verified') is True and
             meaningful(context.get('current_tag_groups_verification_reference')), 'CURRENT_TAG_GROUPS_UNVERIFIED')
        need(meaningful(library.get('approval_reference')) and
             meaningful(library.get('current_version_verification_reference')), 'LIBRARY_NOT_APPROVED')
        need(meaningful(library.get('active_status_verification_reference')), 'ACTIVE_STATUS_UNVERIFIED')
        need(meaningful(library.get('moka_id_mapping_reference')), 'MOKA_MAPPING_UNVERIFIED')
    tags = library.get('tags')
    need(isinstance(tags, list), 'MALFORMED_LIBRARY')
    if version_11:
        # Check every populated ID, including inactive and non-Rate entries.
        # Blank IDs of unrelated tags do not imply a mapping and are ignored.
        library_ids = set()
        for tag in tags:
            remote_id = tag.get('moka_tag_id') if isinstance(tag, dict) else None
            if text(remote_id):
                need(remote_id not in library_ids, 'TAG_AMBIGUOUS')
                library_ids.add(remote_id)
    rate_tags = [t for t in tags if isinstance(t, dict) and t.get('tag_group') == 'rate' and t.get('status') == 'Active']
    need(bool(rate_tags), 'TAG_NOT_IN_LIBRARY')
    values, ids, matching, intervals = set(), set(), [], []
    if version_11 or exception:
        need(not isinstance(plan.get('expected_rate'), float), 'RATE_PRECISION_UNVERIFIED')
    actual_rate = number(plan.get('expected_rate'))
    need(actual_rate >= 0, 'INVALID_RATE')
    if version_11 or exception:
        need(context.get('rate_intervals_complete_verified') is True and
             meaningful(context.get('rate_intervals_verification_reference')), 'RATE_INTERVALS_UNVERIFIED')
    interval_by_label = {}
    exception_tag = None
    for tag in rate_tags:
        # The exception is not an interval and must never be parsed as one.
        if tag.get('tag_value') == RATE_EXCEPTION and not exception:
            continue
        need(text(tag.get('tag_value')) and text(tag.get('moka_tag_id')), 'MOKA_MAPPING_UNVERIFIED')
        if version_11 or exception:
            need(meaningful(tag.get('moka_tag_id')), 'MOKA_MAPPING_UNVERIFIED')
        need(tag['tag_value'] not in values and tag['moka_tag_id'] not in ids, 'TAG_AMBIGUOUS')
        values.add(tag['tag_value']); ids.add(tag['moka_tag_id'])
        if tag['tag_value'] == RATE_EXCEPTION:
            exception_tag = tag
            continue
        if version_11 or exception:
            need(not isinstance(tag.get('lower'), float) and not isinstance(tag.get('upper'), float),
                 'RATE_PRECISION_UNVERIFIED')
        need(tag.get('currency') == 'USD' and tag.get('period') == 'hour', 'UNIT_MISMATCH')
        need(type(tag.get('lower_inclusive')) is bool and type(tag.get('upper_inclusive')) is bool, 'BOUNDARY_INVALID')
        lower, upper = number(tag.get('lower')), number(tag.get('upper'))
        need(lower >= 0 and lower < upper, 'BOUNDARY_INVALID')
        label = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s+USD\s*([<≤])\s*Expected Rate\s*([<≤])\s*(\d+(?:\.\d+)?)\s+USD\s*', tag['tag_value'])
        need(label is not None, 'BOUNDARY_LABEL_MISMATCH')
        need(number(label.group(1)) == lower and number(label.group(4)) == upper and
             (label.group(2) == '≤') == tag['lower_inclusive'] and
             (label.group(3) == '≤') == tag['upper_inclusive'], 'BOUNDARY_LABEL_MISMATCH')
        intervals.append((lower, upper, tag['lower_inclusive'], tag['upper_inclusive']))
        interval_by_label[tag['tag_value']] = intervals[-1]
        lower_ok = actual_rate >= lower if tag['lower_inclusive'] else actual_rate > lower
        upper_ok = actual_rate <= upper if tag['upper_inclusive'] else actual_rate < upper
        if lower_ok and upper_ok:
            matching.append(tag)
    intervals.sort(key=lambda item: (item[0], item[1]))
    for previous, current_interval in zip(intervals, intervals[1:]):
        overlap = (previous[1] > current_interval[0] or
                   (previous[1] == current_interval[0] and previous[3] and current_interval[2]))
        need(not overlap, 'RATE_INTERVAL_OVERLAP')
    if version_11 or exception:
        need(interval_by_label == V11_INTERVALS, 'RATE_INTERVALS_INCOMPLETE_OR_CHANGED')
    if exception:
        need(exception_tag is not None, 'TAG_NOT_IN_LIBRARY')
        need(all(meaningful(tag.get('moka_tag_id')) for tag in rate_tags), 'MOKA_MAPPING_UNVERIFIED')
        # Every selected/interval ID must also be unique against the entire supplied library.
        for remote_id in ids:
            need(sum(1 for tag in tags if isinstance(tag, dict) and tag.get('moka_tag_id') == remote_id) == 1,
                 'TAG_AMBIGUOUS')
        need(actual_rate > Decimal('100') and not matching, 'RATE_OUT_OF_RANGE_OR_AMBIGUOUS')
        selected = exception_tag
    else:
        need(len(matching) == 1, 'RATE_OUT_OF_RANGE_OR_AMBIGUOUS')
        selected = matching[0]
    # Even legacy normal plans must not select an ID shared by another group.
    need(sum(1 for tag in tags if isinstance(tag, dict) and
             tag.get('moka_tag_id') == selected['moka_tag_id']) == 1, 'TAG_AMBIGUOUS')
    need(change['tag_value'] == selected['tag_value'], 'RATE_TAG_MISMATCH')
    need(change['remote_tag_id'] == selected['moka_tag_id'], 'REMOTE_TAG_ID_MISMATCH')

    need(normalize(plan.get('rate_label')) == 'Expected hourly rate in USD', 'RATE_LABEL_MISMATCH')
    sources = context.get('sources')
    evidence = plan.get('evidence')
    need(isinstance(sources, list) and isinstance(evidence, list) and evidence, 'EVIDENCE_MISSING')
    source_index = {}
    for source in sources:
        need(isinstance(source, dict) and all(text(source.get(k)) for k in ('source_id', 'system', 'record_id', 'url', 'captured_at')), 'EVIDENCE_SOURCE_INVALID')
        need(source['system'] == 'moka' and source['record_id'] == record_id, 'SOURCE_IDENTITY_MISMATCH')
        parsed = urlparse(source['url'])
        need(parsed.scheme in ('https', 'http') and bool(parsed.netloc) and f'/application/{record_id}/' in parsed.path, 'SOURCE_IDENTITY_MISMATCH')
        need(source['source_id'] not in source_index, 'DUPLICATE_SOURCE_ID')
        segments = source.get('segments')
        need(isinstance(segments, list) and segments, 'EVIDENCE_MISSING')
        need(all(isinstance(s, dict) and text(s.get('locator')) and text(s.get('text')) for s in segments), 'EVIDENCE_SOURCE_INVALID')
        need(len({s['locator'] for s in segments}) == len(segments), 'AMBIGUOUS_LOCATOR')
        source_index[source['source_id']] = source
    rate_proven = False
    for quote in evidence:
        need(isinstance(quote, dict) and all(text(quote.get(k)) for k in ('source_id', 'locator', 'excerpt')), 'EVIDENCE_MISSING')
        src = source_index.get(quote['source_id'])
        need(src is not None, 'EVIDENCE_SOURCE_NOT_FOUND')
        segs = [s for s in src['segments'] if s['locator'] == quote['locator'] and quote['excerpt'] in s['text']]
        need(bool(segs), 'QUOTE_NOT_VERBATIM')
        for segment in segs:
            content = normalize(segment['text'])
            rate_raw = str(plan['expected_rate']).strip()
            paired = re.fullmatch(re.escape(normalize(plan['rate_label'])) + r'(?:\s*:\s*|\s+)' + re.escape(rate_raw), content)
            if paired and quote['excerpt'] == rate_raw:
                rate_proven = True
    need(rate_proven, 'RATE_EVIDENCE_MISMATCH')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('non-finite constant')


def main():
    parser = argparse.ArgumentParser(description='Offline Rate gate; never authorizes or executes.')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--library', required=True)
    args = parser.parse_args()
    try:
        inputs = []
        for path in (args.plan, args.context, args.library):
            with open(path, encoding='utf-8') as stream:
                inputs.append(json.load(stream, object_pairs_hook=unique_object, parse_constant=reject_constant,
                                        parse_float=Decimal))
        output = validate(*inputs)
        code = 0 if output['ready_for_confirmation'] else 2
    except Exception:
        output = {'ready_for_confirmation': False, 'authorized': False, 'executed': False, 'errors': ['INPUT_ERROR']}
        code = 3
    print(json.dumps(output, ensure_ascii=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
