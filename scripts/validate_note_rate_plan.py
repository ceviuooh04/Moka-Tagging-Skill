#!/usr/bin/env python3
"""Fail-closed offline Moka Note/Profile Rate write-plan gate; no writes/network.

Contract (one JSON object each for --plan, --context, --library):

* plan: candidate {moka_id (application ID), name, match_status:'verified'},
  taxonomy_version ('1.1' or 'v1.1'), expected_rate (decimal STRING),
  rate_source ('note' or 'profile'), rate_evidence {source_id, locator, excerpt},
  changes: exactly one change. A change has system:'moka', record_id, field:
  'candidate_custom_tags', operation:'add' or 'replace', tag_group:'rate',
  tag_value, remote_tag_id; a replace also has old_tag_value and old_remote_tag_id.
  No other change keys are accepted. 'replace' is a single explicit proposed
  transition, not authorization to implement it as an unverified add/delete.
* context: same candidate; allowed_record_ids/allowed_fields/allowed_operations,
  each {'moka':[...]} and current_tags {'moka':[...]} containing the *complete,
  unmodified* actual snapshot. Every tag has tag_group, tag_value, remote_tag_id,
  and remote_group_id. context.tag_group_registry holds verified actual Moka
  group identities, including Rate and each current tag's group: entries are
  {tag_group,moka_group_name,remote_group_id,system:'moka',classification:
  'taxonomy'|'independent',group_verified:true,group_verification_reference}.
  IDs and names must be captured from the actual tenant; never use example IDs.
  Canonical groups use their canonical name. The only supported independent
  group is manual_project_marker, with actual name '手动项目标签'; it is NOT
  Project Category. Its group ID must be independently verified and distinct
  from Rate's. Unknown groups block; Rate IDs/values cannot masquerade as
  independent tags. At most one Rate may exist. For each of
  current_tags_verified, current_tag_groups_verified,
  rate_intervals_complete_verified, notes_complete_verified,
  rate_single_select_verified and write_permission_verified require exactly True
  and the companion <flag without _verified>_verification_reference: a real,
  non-placeholder reference. For replace also require
  replacement_semantics_verified and replacement_semantics_verification_reference
  (atomic or otherwise verified safe one-for-one operation, preserving other tags).
  moka_host identifies the verified Moka tenant host (not a guessed host).
* context.sources is the complete set of relevant captured Moka sources including
  ALL Notes. Each source: source_id, kind ('note','profile','communication'),
  system:'moka', record_id, https url for /application/<application ID>/... on
  moka_host, ISO 8601 captured_at with timezone, source_verified:true and
  source_verification_reference, and segments [{locator,text}]. Note/profile
  sources each contain exactly one segment, holding the complete raw Note or
  complete raw profile field, never a paraphrase. Each Note also requires
  raw_note_complete_verified:true and raw_note_complete_verification_reference;
  these must reflect a real check of the entire source, not a fabricated claim.
  Communication sources can have
  multiple segments, all complete verbatim source text. Unique source IDs and
  segment locators are required. notes_complete_verified and its reference must
  actually attest that all applicable Notes were loaded and examined.
* Every citation {source_id,locator,excerpt} quotes a WHOLE raw segment exactly.
  Captured Note segments are the complete Note, including whitespace and newlines.
  If any Note has a rate, context.note_reliability_rule must be
  {'confirmed':true,'reference':<user citation>}. context.user_sources is a list
  of independently captured, genuine user messages, each {source_id,kind:'user',
  system:'user',captured_at,source_verified:true,source_verification_reference,
  segments:[{locator,text}]}; each segment is the COMPLETE original message.
  Its reference must support the actual user rule that Notes contain expected
  hourly rates confirmed by TA and candidate. Never invent a source, paraphrase
  or manufacture individual communication. The basic lexical sanity checks are
  not semantic verification. The operator must verify the source meaning.
  A bare dollar sign additionally needs either context.bare_dollar_usd_hour_rule
  {'confirmed':true,'reference':<user citation>} citing explicit USD/hour, OR a
  case-specific bare_dollar_currency_context citing the full actual USD/hour
  profile field, the genuine user Note-priority instruction and an independently
  verified reference explaining why USD/hour applies to the Note. The operator
  must examine the whole case and not infer USD when a different currency is
  plausible; a profile number never substitutes for the Note amount.
* Supported multiline Notes have one unambiguous standalone 'Expected rate' or
  'Expected hourly rate' clause at the beginning of a line, or a standalone
  explicit currency/hour amount or range, optionally '(negotiable)', terminated
  by a semicolon, full stop or line end. Simple one-line statements remain supported.
  Additional monetary/rate indicators, instructions, unexplained numeric tokens,
  negations, unknown units/currencies and ambiguous text block. Work experience,
  year/year ranges, tier numbers and hours/week are not rates. Other formats
  require human investigation, not truncation of the Note. Identical rate Notes
  may coexist; all must agree in value and original endpoints. If a Note rate
  exists it takes precedence over Profile; plan.rate_evidence identifies one
  full Note; context.other_note_rate_evidence cites every additional rate Note
  exactly once, in full. For ranges require context.range_midpoint_rule as before,
  preserving both endpoints and calculating the exact Decimal midpoint.
* Every Note without a recognized rate requires context.note_no_rate_reviews
  entry {note_source_id,reviewed:true,reviewer,reviewed_at,conclusion:
  'no_expected_hourly_rate',reference,note_citation}. The reference identifies a
  genuine independent human review performed at or after the Note capture;
  note_citation quotes that whole Note, and
  conservative scans still block money symbols, salary/rate/hourly/pay keywords,
  unknown currencies, and suspicious instructions. No review can override scans.
  An empty verified Note collection needs no reviews. With no rate Note, exactly
  one profile must quote 'Expected hourly rate in USD: <number>'.
* Legacy context.note_confirmations is optional. If present and nonempty it is
  still checked strictly against every rate Note and the complete original real
  communication; it never replaces user-rule evidence. Do not fabricate it.
  Old plans without new rule/review/replacement-plan evidence fail closed.
* Every replace additionally requires context.replacement_plan with mode 'atomic'
  or 'verified_non_atomic_ui', exact PRECONDITIONS and mode-specific steps below,
  ui_verification_reference and FAILURE_ACTION. For non-atomic UI also require
  intermediate_no_rate_verified and non_atomic_steps_permission_verified, each
  true with its verification reference. A separate replacement_plan_confirmation
  is checked if actually obtained; it must not be fabricated. Ordinary steps do
  not require redundant method confirmation if the exact change is authorized.
  The UI operation must really have been verified in the field. The plan
  describes future checks, not completed checks.
* context.write_confirmation has confirmed:true, a genuine meaningful reference,
  and scope exactly {'taxonomy_version':plan.taxonomy_version,'change':change}.
  The reference must point to the real approval of that exact payload; merely
  asserting it here cannot prove approval. A changed payload needs a new approval.
* library uses the existing Rate library schema: all five v1.1 Active intervals,
  exact USD/hour boundary metadata, globally unique real IDs, current approval,
  Active status and mapping flags/references. Other supplied tags must use one
  of the canonical groups or the verified independent group; independent library
  tags must include moka_group_id matching the verified registry. An optional Active 'rate not
  included' requires an ID and can only be selected for a rate strictly >100.
  The old Rate must be present and Active in the supplied verified library with
  its exact ID. A correct already-present rate is a skip, never a write.

No checker can establish the external truth or completeness of flags, references,
identity, notes, permissions, approvals, or tag mappings. Never invent them.
Passing is NOT authorization, execution, permission to discard other tags, or
proof of an available one-for-one Moka operation. Recheck all facts immediately
before execution and verify after any separately authorized write. The input is
never changed; no production data should be placed in the skill directory.
"""
import argparse
import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, localcontext
from urllib.parse import urlsplit, unquote

# Reuse only constants/primitives, never the old addition validator; that validator
# rejects actual old Rate labels and only accepts profile evidence.
from validate_rate_write_plan import (Blocked, RATE_EXCEPTION, UNKNOWN_GROUPS,
                                     V11_INTERVALS, meaningful, need, normalized_group,
                                     number, unique_object, reject_constant)

NUM = r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?'
# USD can be before or after the amount; bare $ is conditional on corroboration.
MONEY = rf'(?:\$\s*(?:(?P<pre>USD)\s*)?(?P<dollar>{NUM})(?:\s*(?P<post>USD))?|(?P<plain>{NUM})\s*USD|USD\s*\$?\s*(?P<usd_first>{NUM}))'
PER_HOUR = r'(?:\s*/\s*(?:hr|hour)|\s+per\s+(?:hr|hour))'
NOTE_RATE = re.compile(rf'^(?:Expected\s+(?:hourly\s+)?rate\s*(?::|=)?\s*)?{MONEY}{PER_HOUR}(?:\s*\(negotiable\))?\s*[.;]?$', re.IGNORECASE)
CONFIRM_RATE = re.compile(rf'^TA\s+and\s+candidate\s+confirmed\s+(?:the\s+)?expected\s+(?:hourly\s+)?rate\s*(?::|is)\s*{MONEY}{PER_HOUR}\s*[.;]?$', re.IGNORECASE)
RANGE = rf'(?P<currency1>\$|USD)?\s*(?P<low>{NUM})\s*(?P<currency2>USD)?\s*(?:-|–|—|\bto\b)\s*(?P<currency3>\$|USD)?\s*(?P<high>{NUM})\s*(?P<currency4>USD)?'
NOTE_RANGE = re.compile(rf'^(?:Expected\s+(?:hourly\s+)?rate\s*(?::|=)?\s*)?{RANGE}{PER_HOUR}(?:\s*\(negotiable\))?\s*[.;]?$', re.IGNORECASE)
CONFIRM_RANGE = re.compile(rf'^TA\s+and\s+candidate\s+confirmed\s+(?:the\s+)?expected\s+(?:hourly\s+)?rate\s*(?::|is)\s*{RANGE}{PER_HOUR}\s*[.;]?$', re.IGNORECASE)
PROFILE = re.compile(rf'^Expected hourly rate in USD(?:\s*:\s*|\s+)(?P<amount>{NUM})$')
IDENT = re.compile(r'^[A-Za-z0-9_-]+$')
CANONICAL_GROUPS = frozenset(('rate', 'country', 'language', 'project category', 'knowledge domain', 'tier'))
INDEPENDENT_GROUP_NAMES = {'manual_project_marker': frozenset(('手动项目标签',))}
CANONICAL_GROUP_NAMES = {'rate': frozenset(('rate', 'rate 标签')),
                         'language': frozenset(('language', '手动语言标签'))}
RATE_INDICATORS = re.compile(
    r'(?<![a-z])(?:rates?|salary|salaries|compensation|hourly|wages?|pay|paid|payment|'
    r'earnings?|income|remuneration|fees?|budget|cost|price|expected|expectation|'
    r'dollars?|bucks?|euros?|pounds?|yen|rupees?|currency|USD|CAD|AUD|EUR|GBP|'
    r'CNY|RMB|JPY|INR|SGD|HKD|NZD|CHF)(?![a-z])|'
    r'时薪|小时薪|薪资|薪水|薪酬|工资|薪金|报酬|费率|薪|收入|美元|美金|欧元|人民币|'
    r'每小时|每月|报价|期望收入|佣金|酬劳|'
    r'[0-9][ \t]*(?:/|per[ \t]+|an?[ \t]+|each[ \t]+)(?:h|hrs?|hours?)\b', re.IGNORECASE)
UNKNOWN_CURRENCY = re.compile(r'(?<![A-Za-z])[A-Z]{3}[ \t]*[+-]?[ \t]*[0-9]|'
                              r'[0-9][ \t]*[A-Z]{3}(?![A-Za-z])')
INJECTION = re.compile(
    r'\b(?:ignore|disregard|override|bypass|forget|pretend|jailbreak)\b|'
    r'\b(?:system|developer|assistant)\s*(?:prompt|message|instruction|:)|'
    r'<\s*/?\s*(?:system|assistant|developer)\s*>|'
    r'忽略|无视|绕过|提示词|系统消息|系统指令|开发者指令', re.IGNORECASE)
QUALIFIER = re.compile(
    r'\b(?:not|never|no longer|previous(?:ly)?|former(?:ly)?|prior(?:ly)?|'
    r'outdated|instead|changed|declined|rejected|incorrect|wrong|example|'
    r'hypothetical|maybe|perhaps|unclear|unknown|unconfirmed|unverified|tbd)\b|'
    r'并非|不是|未确认|不再|此前|先前|原来|历史|过期|假设|示例|待确认|待定', re.IGNORECASE)
KNOWN_NUMBERS = re.compile(
    r'(?<![0-9])(?:tier[ \t]*[1-4]|'
    r'[0-9]+(?:[ \t]*[-–—][ \t]*[0-9]+)?[ \t]*(?:hrs?|hours?)[ \t]*(?:/|per[ \t]+)[ \t]*(?:wk|week)|'
    r'[0-9]+(?:\+|[ \t]*[-–—][ \t]*[0-9]+)?[ \t]+years?|'
    r'(?:19|20)[0-9]{2}(?:[ \t]*[-–—][ \t]*(?:19|20)[0-9]{2})?)(?![0-9])', re.IGNORECASE)
PRECONDITIONS = [
    'recheck_identity_and_target', 'recheck_complete_notes_and_rate_evidence',
    'recheck_current_tags_and_single_selection', 'recheck_approved_library_and_mapping',
    'recheck_permissions_and_exact_approval', 'recheck_ui_and_recovery_authority',
]
REPLACEMENT_STEPS = {
    'atomic': ['replace_old_with_new_one_for_one', 'verify_new_rate_and_preserved_non_rate_tags'],
    'verified_non_atomic_ui': ['remove_old_rate_only', 'verify_no_rate_and_preserved_non_rate_tags',
                               'add_new_rate_only', 'verify_new_rate_and_preserved_non_rate_tags'],
}
FAILURE_ACTION = 'stop_reread_restore_old_only_if_authorized_then_verify_or_escalate'


def exact_string(value):
    return isinstance(value, str) and value == value.strip() and meaningful(value)


def claim(obj, flag, code):
    # Never synthesize flags or references; both must be supplied by the caller.
    stem = flag.removesuffix('_verified')
    need(obj.get(flag) is True and exact_string(obj.get(stem + '_verification_reference')), code)


def amount_match(match):
    value = next((match.group(name) for name in ('dollar', 'plain', 'usd_first') if match.group(name) is not None), None)
    explicit_usd = bool(match.group('plain') or match.group('usd_first') or match.group('pre') or match.group('post'))
    return Decimal(value), explicit_usd


def range_match(match):
    currencies = [match.group(f'currency{i}') for i in range(1, 5)]
    need(any(currencies), 'RANGE_CURRENCY_MISSING')
    low_raw, high_raw = match.group('low'), match.group('high')
    # Avoid rounding even when either endpoint has hundreds of decimal digits.
    need(len(low_raw) <= 512 and len(high_raw) <= 512, 'RATE_PRECISION_UNSUPPORTED')
    low, high = Decimal(low_raw), Decimal(high_raw)
    need(low < high, 'RANGE_ORDER_INVALID')
    with localcontext() as ctx:
        ctx.prec = len(low_raw) + len(high_raw) + 8
        midpoint = (low + high) / Decimal(2)
    return (low, high, midpoint), any(c and c.upper() == 'USD' for c in currencies)


def iso_time(value):
    if not exact_string(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (ValueError, OverflowError):
        return False


def valid_url(value, host, app_id):
    if not exact_string(value) or not exact_string(host):
        return False
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or url.hostname != host or url.username is not None or url.password is not None or url.port not in (None, 443):
            return False
        # Reject encoded separators/dot segments and URL path tricks, not just substrings.
        if unquote(url.path) != url.path or any(s in ('.', '..') for s in url.path.split('/')):
            return False
        parts = url.path.split('/')
        application_positions = [i for i, part in enumerate(parts) if part == 'application']
        if len(application_positions) != 1:
            return False
        i = application_positions[0]
        return i + 2 < len(parts) and parts[i + 1] == app_id and bool(parts[i + 2])
    except (ValueError, TypeError):
        return False


def source_index(context, app_id):
    sources, host = context.get('sources'), context.get('moka_host')
    need(exact_string(host) and host == host.lower() and re.fullmatch(r'[a-z0-9.-]+', host) is not None,
         'MOKA_HOST_INVALID')
    need(isinstance(sources, list), 'EVIDENCE_SOURCE_INVALID')
    index = {}
    for src in sources:
        need(isinstance(src, dict), 'EVIDENCE_SOURCE_INVALID')
        need(all(exact_string(src.get(k)) for k in ('source_id', 'kind', 'system', 'record_id', 'url')),
             'EVIDENCE_SOURCE_INVALID')
        need(src['source_id'] not in index, 'DUPLICATE_SOURCE_ID')
        need(src['kind'] in ('note', 'profile', 'communication'), 'EVIDENCE_SOURCE_INVALID')
        need(src['system'] == 'moka' and src['record_id'] == app_id and valid_url(src['url'], host, app_id),
             'SOURCE_IDENTITY_MISMATCH')
        need(iso_time(src.get('captured_at')), 'EVIDENCE_SOURCE_INVALID')
        claim(src, 'source_verified', 'EVIDENCE_SOURCE_UNVERIFIED')
        segments = src.get('segments')
        need(isinstance(segments, list) and bool(segments), 'EVIDENCE_SOURCE_INVALID')
        if src['kind'] in ('note', 'profile'):
            need(len(segments) == 1, 'SOURCE_RAW_TEXT_AMBIGUOUS')
        if src['kind'] == 'note':
            claim(src, 'raw_note_complete_verified', 'NOTE_RAW_COMPLETENESS_UNVERIFIED')
        locators = set()
        for seg in segments:
            need(isinstance(seg, dict) and exact_string(seg.get('locator')) and
                 isinstance(seg.get('text'), str) and bool(seg['text'].strip()), 'EVIDENCE_SOURCE_INVALID')
            need(seg['locator'] not in locators, 'AMBIGUOUS_LOCATOR')
            locators.add(seg['locator'])
        index[src['source_id']] = src
    user_sources = context.get('user_sources', [])
    need(isinstance(user_sources, list), 'USER_SOURCE_INVALID')
    for src in user_sources:
        need(isinstance(src, dict) and exact_string(src.get('source_id')) and
             src.get('kind') == 'user' and src.get('system') == 'user' and
             iso_time(src.get('captured_at')), 'USER_SOURCE_INVALID')
        need(src['source_id'] not in index, 'DUPLICATE_SOURCE_ID')
        claim(src, 'source_verified', 'USER_SOURCE_UNVERIFIED')
        segments = src.get('segments')
        need(isinstance(segments, list) and len(segments) == 1, 'USER_SOURCE_INVALID')
        seg = segments[0]
        need(isinstance(seg, dict) and exact_string(seg.get('locator')) and
             isinstance(seg.get('text'), str) and bool(seg['text'].strip()), 'USER_SOURCE_INVALID')
        index[src['source_id']] = src
    return index


def cited_segment(citation, index, kind):
    need(isinstance(citation, dict) and set(citation) == {'source_id', 'locator', 'excerpt'} and
         all(exact_string(citation.get(k)) for k in ('source_id', 'locator')) and
         isinstance(citation.get('excerpt'), str) and bool(citation['excerpt'].strip()), 'EVIDENCE_MISSING')
    src = index.get(citation['source_id'])
    need(src is not None and src['kind'] == kind, 'EVIDENCE_SOURCE_NOT_FOUND')
    matches = [s for s in src['segments'] if s['locator'] == citation['locator']]
    need(len(matches) == 1 and citation['excerpt'] == matches[0]['text'], 'QUOTE_NOT_VERBATIM_FULL')
    return citation['excerpt']


def scan_note(text, rate_present):
    # NFKC is only for conservative detection, never for source evidence.
    normalized = unicodedata.normalize('NFKC', text)
    need(not any(unicodedata.category(ch) in ('Cf', 'Cc') and ch not in '\n\r\t' for ch in text),
         'NOTE_AMBIGUOUS_OR_UNSUPPORTED')
    need(INJECTION.search(normalized) is None, 'NOTE_AMBIGUOUS_OR_UNSUPPORTED')
    need(not any(unicodedata.category(ch) == 'Sc' for ch in normalized), 'NOTE_AMBIGUOUS_OR_UNSUPPORTED')
    need(UNKNOWN_CURRENCY.search(normalized) is None, 'NOTE_AMBIGUOUS_OR_UNSUPPORTED')
    # The allowlisted work-duration and experience numbers are never rates.
    remainder = KNOWN_NUMBERS.sub(' ', normalized)
    need(RATE_INDICATORS.search(remainder) is None, 'NOTE_AMBIGUOUS_OR_UNSUPPORTED')
    if rate_present:
        need(QUALIFIER.search(normalized) is None and
             not re.search(r'\b(?:or|versus|vs)\s+[0-9]', normalized, re.I) and
             not re.search(r'[0-9]', remainder),
             'NOTE_AMBIGUOUS_OR_UNSUPPORTED')


def parse_note(raw):
    # A supported rate is an entire first semicolon-delimited clause on a line.
    # Unlike stripping the Note, this preserves the full raw citation unchanged.
    matches, offset = [], 0
    lines = raw.splitlines(keepends=True)
    legacy_single = len(raw.splitlines()) == 1
    for line in lines:
        content = line.rstrip('\r\n')
        clause = content.split(';', 1)[0]
        statement = clause.strip()
        named = re.match(r'^Expected\s+(?:hourly\s+)?rate\b', statement, re.IGNORECASE)
        standalone = bool(NOTE_RATE.fullmatch(statement) or NOTE_RANGE.fullmatch(statement))
        if named or standalone or (legacy_single and len(content.split(';')) <= 2 and
                     not content.partition(';')[2].strip()):
            match = NOTE_RANGE.fullmatch(statement)
            if match:
                (low, high, midpoint), explicit = range_match(match)
                matches.append((('range', low, high, midpoint), explicit, offset, offset + len(clause)))
            else:
                match = NOTE_RATE.fullmatch(statement)
                if match:
                    value, explicit = amount_match(match)
                    matches.append((('amount', value), explicit, offset, offset + len(clause)))
        offset += len(line)
    need(len(matches) <= 1, 'MULTIPLE_NOTE_RATE_EXPRESSIONS')
    if matches:
        value, explicit, start, end = matches[0]
        scan_note(raw[:start] + ' ' + raw[end:], True)
        # Negations/instructions in the recognized line itself are not accepted by
        # the rate grammar; check the entire Note for wider semantic qualifiers.
        need(QUALIFIER.search(unicodedata.normalize('NFKC', raw)) is None,
             'NOTE_AMBIGUOUS_OR_UNSUPPORTED')
        return value, explicit
    scan_note(raw, False)
    return None, None


def user_rule(context, key, index, purpose):
    rule = context.get(key)
    need(isinstance(rule, dict) and set(rule) == {'confirmed', 'reference'} and
         rule.get('confirmed') is True, 'USER_RULE_UNCONFIRMED')
    raw = cited_segment(rule['reference'], index, 'user')
    text = unicodedata.normalize('NFKC', raw)
    if purpose == 'reliability':
        need(re.search(r'(?<![A-Za-z])note(?![A-Za-z])|备注', text, re.I) and
             re.search(r'(?<![A-Za-z])TA(?![A-Za-z])|recruiter|招聘', text, re.I) and
             re.search(r'candidate|候选人', text, re.I) and
             re.search(r'confirm|确认', text, re.I) and
             re.search(r'expected.{0,30}(?:rate|hourly)|期望.{0,12}(?:时薪|小时薪)', text, re.I),
             'USER_RULE_CONTENT_UNSUPPORTED')
        need(not re.search(r'\b(?:not|never|unconfirmed)\b.{0,40}\bconfirm|未.{0,20}确认',
                           text, re.I), 'USER_RULE_CONTENT_UNSUPPORTED')
    else:
        need(re.search(r'(?:USD|美元|美金|U\.?S\.?\s+dollars?).{0,40}'
                       r'(?:/\s*(?:hr|hour|小时)|per\s+(?:hr|hour)|每\s*(?:hour|小时)|时薪)|'
                       r'(?:hourly|时薪).{0,40}(?:USD|美元|美金)', text, re.I | re.S),
             'USD_HOUR_RULE_CONTENT_UNSUPPORTED')
        need(not re.search(r'\b(?:not|never)\b.{0,12}(?:USD|dollars?)|'
                           r'(?:并非|不是|不按).{0,12}(?:USD|美元|美金)', text, re.I),
             'USD_HOUR_RULE_CONTENT_UNSUPPORTED')


def contextual_usd_hour(context, index):
    """Validate recorded context; the operator must decide whether it proves USD."""
    evidence = context.get('bare_dollar_currency_context')
    need(isinstance(evidence, dict) and set(evidence) == {
        'same_unit_verified', 'verification_reference', 'profile_citation', 'user_instruction_citation'
    } and evidence.get('same_unit_verified') is True and exact_string(evidence.get('verification_reference')),
         'BARE_DOLLAR_CONTEXT_UNVERIFIED')
    profile = cited_segment(evidence['profile_citation'], index, 'profile')
    need(PROFILE.fullmatch(profile.strip()) is not None, 'USD_PROFILE_CONTEXT_UNSUPPORTED')
    instruction = cited_segment(evidence['user_instruction_citation'], index, 'user')
    need(re.search(r'(?<![A-Za-z])note(?![A-Za-z])|备注', instruction, re.I) and
         re.search(r'candidate\s+profile|候选人档案', instruction, re.I) and
         re.search(r'时薪|hourly|rate', instruction, re.I), 'USD_USER_CONTEXT_UNSUPPORTED')


def verify_no_rate_reviews(context, index, note_ids):
    reviews = context.get('note_no_rate_reviews', [])
    need(isinstance(reviews, list), 'NOTE_REVIEW_MISSING')
    seen = set()
    for item in reviews:
        need(isinstance(item, dict) and set(item) == {
            'note_source_id', 'reviewed', 'reviewer', 'reviewed_at', 'conclusion', 'reference', 'note_citation'
        } and item.get('reviewed') is True and item.get('conclusion') == 'no_expected_hourly_rate' and
             exact_string(item.get('reviewer')) and iso_time(item.get('reviewed_at')) and
             exact_string(item.get('reference')) and item.get('note_source_id') in note_ids and
             item['note_source_id'] not in seen, 'NOTE_REVIEW_MISSING')
        need(item['note_citation'].get('source_id') == item['note_source_id']
             if isinstance(item['note_citation'], dict) else False, 'NOTE_REVIEW_MISSING')
        cited_segment(item['note_citation'], index, 'note')
        reviewed_at = datetime.fromisoformat(item['reviewed_at'].replace('Z', '+00:00'))
        captured_at = datetime.fromisoformat(index[item['note_source_id']]['captured_at'].replace('Z', '+00:00'))
        need(reviewed_at >= captured_at, 'NOTE_REVIEW_STALE')
        seen.add(item['note_source_id'])
    need(seen == note_ids, 'NOTE_REVIEW_MISSING')


def validate_evidence(plan, context, index, expected):
    notes = [s for s in index.values() if s['kind'] == 'note']
    profiles = [s for s in index.values() if s['kind'] == 'profile']
    need(len(profiles) <= 1, 'PROFILE_AMBIGUOUS')
    found, bare, no_rate = {}, set(), set()
    for src in notes:
        raw = src['segments'][0]['text']
        value, explicit = parse_note(raw)
        if value:
            found[src['source_id']] = value
            if not explicit:
                bare.add(src['source_id'])
        else:
            no_rate.add(src['source_id'])
    verify_no_rate_reviews(context, index, no_rate)
    confirmations = context.get('note_confirmations', [])
    need(isinstance(confirmations, list), 'NOTE_CONFIRMATION_MISSING')
    if found:
        user_rule(context, 'note_reliability_rule', index, 'reliability')
        if bare:
            if context.get('bare_dollar_usd_hour_rule') is not None:
                user_rule(context, 'bare_dollar_usd_hour_rule', index, 'usd_hour')
            else:
                contextual_usd_hour(context, index)
        need(len(set(found.values())) == 1, 'CONFLICTING_NOTE_RATES')
        value = next(iter(found.values()))
        need((value[-1] if value[0] == 'range' else value[1]) == expected, 'RATE_EVIDENCE_MISMATCH')
        if value[0] == 'range':
            rule = context.get('range_midpoint_rule')
            need(isinstance(rule, dict) and rule.get('confirmed') is True and
                 rule.get('method') == 'decimal_midpoint' and exact_string(rule.get('reference')),
                 'RANGE_RULE_UNCONFIRMED')
        need(plan.get('rate_source') == 'note', 'NOTE_PRECEDENCE_REQUIRED')
        selected = plan.get('rate_evidence')
        cited_segment(selected, index, 'note')
        need(selected['source_id'] in found, 'RATE_EVIDENCE_MISMATCH')
        other_quotes = context.get('other_note_rate_evidence', [])
        need(isinstance(other_quotes, list), 'NOTE_RATE_CITATIONS_MISSING')
        quoted = {selected['source_id']}
        for quote in other_quotes:
            cited_segment(quote, index, 'note')
            need(quote['source_id'] in found and quote['source_id'] not in quoted, 'NOTE_RATE_CITATIONS_MISSING')
            quoted.add(quote['source_id'])
        need(quoted == set(found), 'NOTE_RATE_CITATIONS_MISSING')
        seen = set()
        for item in confirmations:
            need(isinstance(item, dict) and set(item) == {'note_source_id', 'confirmed', 'reference'} and
                 item.get('confirmed') is True and item.get('note_source_id') in found and
                 item['note_source_id'] not in seen, 'NOTE_CONFIRMATION_MISSING')
            seen.add(item['note_source_id'])
            raw = cited_segment(item.get('reference'), index, 'communication')
            original = found[item['note_source_id']]
            if original[0] == 'range':
                match = CONFIRM_RANGE.fullmatch(raw.strip())
                need(match is not None, 'NOTE_CONFIRMATION_UNSUPPORTED')
                confirmed, explicit_usd = range_match(match)
                need(explicit_usd and confirmed == original[1:], 'NOTE_CONFIRMATION_MISMATCH')
            else:
                match = CONFIRM_RATE.fullmatch(raw.strip())
                need(match is not None, 'NOTE_CONFIRMATION_UNSUPPORTED')
                confirmed, explicit_usd = amount_match(match)
                need(explicit_usd and confirmed == original[1], 'NOTE_CONFIRMATION_MISMATCH')
        if confirmations:
            need(seen == set(found), 'NOTE_CONFIRMATION_MISSING')
        if value[0] == 'range':
            return {'method': 'decimal_midpoint', 'lower': format(value[1], 'f'),
                    'upper': format(value[2], 'f'), 'midpoint': format(value[3], 'f'), 'unit': 'USD/hour'}
    else:
        need(not confirmations, 'NOTE_CONFIRMATION_MISMATCH')
        need(context.get('other_note_rate_evidence', []) == [], 'NOTE_RATE_CITATIONS_MISSING')
        need(plan.get('rate_source') == 'profile' and len(profiles) == 1, 'PROFILE_FALLBACK_UNAVAILABLE')
        raw = cited_segment(plan.get('rate_evidence'), index, 'profile')
        match = PROFILE.fullmatch(raw.strip())
        need(match is not None and Decimal(match.group('amount')) == expected, 'RATE_EVIDENCE_MISMATCH')
    return None


def validate_group_registry(context):
    entries = context.get('tag_group_registry')
    need(isinstance(entries, list) and entries, 'GROUP_REGISTRY_UNVERIFIED')
    registry, ids, names = {}, set(), set()
    for entry in entries:
        keys = {'tag_group', 'moka_group_name', 'remote_group_id', 'system',
                'classification', 'group_verified', 'group_verification_reference'}
        need(isinstance(entry, dict) and set(entry) == keys and entry.get('system') == 'moka' and
             all(exact_string(entry.get(k)) for k in ('tag_group', 'moka_group_name', 'remote_group_id')),
             'GROUP_REGISTRY_UNVERIFIED')
        claim(entry, 'group_verified', 'GROUP_REGISTRY_UNVERIFIED')
        key = entry['tag_group']
        if key in CANONICAL_GROUPS:
            need(entry['classification'] == 'taxonomy' and
                 normalized_group(entry['moka_group_name']) in CANONICAL_GROUP_NAMES.get(key, frozenset((key,))),
                 'GROUP_IDENTITY_MISMATCH')
        elif key in INDEPENDENT_GROUP_NAMES:
            need(entry['classification'] == 'independent' and
                 entry['moka_group_name'] in INDEPENDENT_GROUP_NAMES[key], 'GROUP_IDENTITY_MISMATCH')
        else:
            raise Blocked('CURRENT_TAG_GROUP_UNSUPPORTED')
        name = normalized_group(entry['moka_group_name'])
        rid = entry['remote_group_id']
        need(key not in registry and rid not in ids and name not in names, 'GROUP_IDENTITY_AMBIGUOUS')
        registry[key] = entry
        ids.add(rid)
        names.add(name)
    need('rate' in registry, 'RATE_GROUP_UNVERIFIED')
    return registry


def validate_library(plan, context, library, expected, registry):
    need(plan.get('taxonomy_version') in ('1.1', 'v1.1') and
         plan['taxonomy_version'] == library.get('taxonomy_version'), 'TAXONOMY_VERSION_MISMATCH')
    need(library.get('current_approved_version_verified') is True and
         exact_string(library.get('approval_reference')) and
         exact_string(library.get('current_version_verification_reference')), 'LIBRARY_NOT_APPROVED')
    claim(library, 'active_status_verified', 'ACTIVE_STATUS_UNVERIFIED')
    # Existing schema calls this reference moka_id_mapping_reference.
    need(library.get('moka_id_mapping_verified') is True and
         exact_string(library.get('moka_id_mapping_reference')), 'MOKA_MAPPING_UNVERIFIED')
    claim(context, 'rate_intervals_complete_verified', 'RATE_INTERVALS_UNVERIFIED')
    tags = library.get('tags')
    need(isinstance(tags, list) and all(isinstance(t, dict) for t in tags), 'MALFORMED_LIBRARY')
    all_ids = set()
    active = {}
    intervals = {}
    for tag in tags:
        rid = tag.get('moka_tag_id')
        if rid is not None and rid != '':
            need(exact_string(rid) and rid not in all_ids, 'TAG_AMBIGUOUS')
            all_ids.add(rid)
        group = tag.get('tag_group')
        need(exact_string(group) and (normalized_group(group) in CANONICAL_GROUPS or
             group in INDEPENDENT_GROUP_NAMES), 'LIBRARY_GROUP_UNSUPPORTED')
        if group in INDEPENDENT_GROUP_NAMES:
            need(group in registry and tag.get('moka_group_id') == registry[group]['remote_group_id'],
                 'LIBRARY_GROUP_UNSUPPORTED')
        if isinstance(group, str) and normalized_group(group) == 'rate':
            need(group == 'rate', 'MALFORMED_LIBRARY')
            if tag.get('status') != 'Active':
                continue
            value = tag.get('tag_value')
            need(exact_string(value) and exact_string(rid) and value not in active, 'TAG_AMBIGUOUS')
            active[value] = tag
            if value == RATE_EXCEPTION:
                # It is not an interval; do not fabricate interval metadata.
                need(not any(k in tag for k in ('lower', 'upper', 'lower_inclusive', 'upper_inclusive')),
                     'EXCEPTION_METADATA_INVALID')
                need(tag.get('currency') in (None, 'USD') and tag.get('period') in (None, 'hour'),
                     'UNIT_MISMATCH')
                continue
            need(value in V11_INTERVALS, 'RATE_INTERVALS_INCOMPLETE_OR_CHANGED')
            need(tag.get('currency') == 'USD' and tag.get('period') == 'hour', 'UNIT_MISMATCH')
            need(type(tag.get('lower_inclusive')) is bool and type(tag.get('upper_inclusive')) is bool,
                 'BOUNDARY_INVALID')
            need(not isinstance(tag.get('lower'), float) and not isinstance(tag.get('upper'), float),
                 'RATE_PRECISION_UNVERIFIED')
            lower, upper = number(tag.get('lower')), number(tag.get('upper'))
            interval = (lower, upper, tag['lower_inclusive'], tag['upper_inclusive'])
            need(interval == V11_INTERVALS[value], 'BOUNDARY_LABEL_MISMATCH')
            intervals[value] = interval
    need(intervals == V11_INTERVALS, 'RATE_INTERVALS_INCOMPLETE_OR_CHANGED')
    matches = [active[label] for label, (low, high, li, ui) in intervals.items()
               if (expected >= low if li else expected > low) and (expected <= high if ui else expected < high)]
    if expected > Decimal('100'):
        need(not matches and RATE_EXCEPTION in active, 'RATE_OUT_OF_RANGE_OR_AMBIGUOUS')
        return active[RATE_EXCEPTION], active
    need(len(matches) == 1, 'RATE_OUT_OF_RANGE_OR_AMBIGUOUS')
    return matches[0], active


def validate_replacement_plan(context, change):
    replacement = context.get('replacement_plan')
    need(isinstance(replacement, dict), 'REPLACEMENT_PLAN_MISSING')
    mode = replacement.get('mode')
    need(mode in REPLACEMENT_STEPS, 'REPLACEMENT_PLAN_INVALID')
    keys = {'mode', 'ui_verification_reference', 'preconditions', 'steps', 'on_failure'}
    if mode == 'verified_non_atomic_ui':
        keys |= {'intermediate_no_rate_verified', 'intermediate_no_rate_verification_reference',
                 'non_atomic_steps_permission_verified', 'non_atomic_steps_permission_verification_reference'}
    need(set(replacement) == keys and exact_string(replacement.get('ui_verification_reference')) and
         replacement.get('preconditions') == PRECONDITIONS and
         replacement.get('steps') == REPLACEMENT_STEPS[mode] and
         replacement.get('on_failure') == FAILURE_ACTION, 'REPLACEMENT_PLAN_INVALID')
    if mode == 'verified_non_atomic_ui':
        claim(replacement, 'intermediate_no_rate_verified', 'INTERMEDIATE_STATE_UNVERIFIED')
        claim(replacement, 'non_atomic_steps_permission_verified', 'NON_ATOMIC_STEP_PERMISSION_UNVERIFIED')
    approval = context.get('replacement_plan_confirmation')
    if approval is not None:
        need(isinstance(approval, dict) and approval.get('confirmed') is True and
             exact_string(approval.get('reference')) and
             approval.get('scope') == {'change': change, 'replacement_plan': replacement},
             'REPLACEMENT_PLAN_CONFIRMATION_MISSING_OR_MISMATCH')


def _validate(plan, context, library):
    need(all(isinstance(x, dict) for x in (plan, context, library)), 'MALFORMED_INPUT')
    candidate, identity = plan.get('candidate'), context.get('candidate')
    need(isinstance(candidate, dict) and isinstance(identity, dict), 'IDENTITY_UNVERIFIED')
    need(candidate.get('match_status') == identity.get('match_status') == 'verified', 'IDENTITY_UNVERIFIED')
    app_id = candidate.get('moka_id')
    need(exact_string(app_id) and IDENT.fullmatch(app_id) and app_id == identity.get('moka_id') and
         exact_string(candidate.get('name')) and candidate['name'] == identity.get('name'), 'IDENTITY_MISMATCH')
    for key in ('allowed_record_ids', 'allowed_fields', 'allowed_operations', 'current_tags'):
        need(isinstance(context.get(key), dict) and isinstance(context[key].get('moka'), list), 'MALFORMED_CONTEXT')
    for flag, code in (('current_tags_verified', 'CURRENT_TAGS_UNVERIFIED'),
                       ('current_tag_groups_verified', 'CURRENT_TAG_GROUPS_UNVERIFIED'),
                       ('notes_complete_verified', 'NOTES_INCOMPLETE'),
                       ('rate_single_select_verified', 'SINGLE_SELECT_UNVERIFIED'),
                       ('write_permission_verified', 'WRITE_PERMISSION_UNVERIFIED')):
        claim(context, flag, code)
    need(app_id in context['allowed_record_ids']['moka'], 'TARGET_NOT_ALLOWED')
    changes = plan.get('changes')
    need(isinstance(changes, list) and len(changes) == 1 and isinstance(changes[0], dict), 'CHANGE_COUNT_INVALID')
    change = changes[0]
    fields = {'system', 'record_id', 'field', 'operation', 'tag_group', 'tag_value', 'remote_tag_id'}
    if change.get('operation') == 'replace':
        fields |= {'old_tag_value', 'old_remote_tag_id'}
    need(set(change) == fields, 'CHANGE_SHAPE_INVALID')
    need(change['system'] == 'moka' and change['record_id'] == app_id, 'TARGET_NOT_ALLOWED')
    need(change['field'] == 'candidate_custom_tags' and change['field'] in context['allowed_fields']['moka'], 'FIELD_NOT_ALLOWED')
    need(change['operation'] in ('add', 'replace') and change['operation'] in context['allowed_operations']['moka'], 'OPERATION_NOT_ALLOWED')
    need(change['tag_group'] == 'rate' and exact_string(change['tag_value']) and exact_string(change['remote_tag_id']), 'TAG_INVALID')
    current = context['current_tags']['moka']
    need(all(isinstance(t, dict) and exact_string(t.get('tag_group')) and exact_string(t.get('tag_value')) for t in current), 'CURRENT_TAGS_INVALID')
    need(all(normalized_group(t['tag_group']) not in UNKNOWN_GROUPS for t in current), 'CURRENT_TAG_GROUP_UNKNOWN')
    registry = validate_group_registry(context)
    seen_tag_ids = set()
    for tag in current:
        group = normalized_group(tag['tag_group'])
        need(group in CANONICAL_GROUPS or tag['tag_group'] in INDEPENDENT_GROUP_NAMES,
             'CURRENT_TAG_GROUP_UNSUPPORTED')
        need(group in registry and exact_string(tag.get('remote_group_id')) and
             tag['remote_group_id'] == registry[group]['remote_group_id'] and
             exact_string(tag.get('remote_tag_id')), 'CURRENT_TAG_GROUP_OR_ID_UNVERIFIED')
        need(tag['remote_tag_id'] not in seen_tag_ids, 'CURRENT_TAG_ID_AMBIGUOUS')
        seen_tag_ids.add(tag['remote_tag_id'])
    old = [t for t in current if normalized_group(t['tag_group']) == 'rate']
    need(len(old) <= 1, 'MULTIPLE_EXISTING_RATE_TAGS')
    if old:
        need(exact_string(old[0].get('remote_tag_id')), 'OLD_TAG_ID_UNVERIFIED')
        need(change['operation'] == 'replace', 'REPLACEMENT_REQUIRED')
        claim(context, 'replacement_semantics_verified', 'REPLACEMENT_SEMANTICS_UNVERIFIED')
        validate_replacement_plan(context, change)
        need(change['old_tag_value'] == old[0]['tag_value'] and
             change['old_remote_tag_id'] == old[0]['remote_tag_id'], 'OLD_TAG_MISMATCH')
        need(change['tag_value'] != old[0]['tag_value'] and
             change['remote_tag_id'] != old[0]['remote_tag_id'], 'RATE_ALREADY_PRESENT_OR_ID_COLLISION')
    else:
        need(change['operation'] == 'add', 'NO_OLD_RATE_TO_REPLACE')
    confirmation = context.get('write_confirmation')
    need(isinstance(confirmation, dict) and confirmation.get('confirmed') is True and
         exact_string(confirmation.get('reference')) and
         confirmation.get('scope') == {'taxonomy_version': plan.get('taxonomy_version'), 'change': change},
         'WRITE_CONFIRMATION_MISSING_OR_MISMATCH')
    rate = plan.get('expected_rate')
    need(isinstance(rate, str) and len(rate) <= 1024 and re.fullmatch(NUM, rate) is not None, 'INVALID_RATE')
    expected = Decimal(rate)
    selected, active = validate_library(plan, context, library, expected, registry)
    rate_library = [t for t in library['tags'] if normalized_group(t['tag_group']) == 'rate']
    rate_ids = {t.get('moka_tag_id') for t in rate_library if exact_string(t.get('moka_tag_id'))}
    rate_values = {normalized_group(t.get('tag_value')) for t in rate_library if exact_string(t.get('tag_value'))}
    rate_values.add(normalized_group(RATE_EXCEPTION))
    need(all(normalized_group(t['tag_group']) == 'rate' or
             (t['remote_tag_id'] not in rate_ids and normalized_group(t['tag_value']) not in rate_values)
             for t in current), 'RATE_GROUP_MASQUERADE')
    need(change['tag_value'] == selected['tag_value'] and change['remote_tag_id'] == selected['moka_tag_id'], 'RATE_TAG_OR_ID_MISMATCH')
    if old:
        prior = active.get(old[0]['tag_value'])
        need(prior is not None and prior['moka_tag_id'] == old[0]['remote_tag_id'], 'OLD_TAG_MAPPING_UNVERIFIED')
        # A tag of another group with the same old or new ID makes the snapshot ambiguous.
        need(all(t is old[0] or t.get('remote_tag_id') not in (old[0]['remote_tag_id'], change['remote_tag_id'])
                 for t in current), 'CURRENT_TAG_ID_AMBIGUOUS')
    else:
        need(all(t.get('remote_tag_id') != change['remote_tag_id'] for t in current), 'CURRENT_TAG_ID_AMBIGUOUS')
    index = source_index(context, app_id)
    return validate_evidence(plan, context, index, expected)


def validate(plan, context, library):
    try:
        calculation = _validate(plan, context, library)
        return {'ready_for_confirmation': True, 'authorized': False, 'executed': False,
                'rate_calculation': calculation, 'errors': []}
    except Blocked as exc:
        return {'ready_for_confirmation': False, 'authorized': False, 'executed': False, 'errors': [str(exc)]}
    except Exception:
        return {'ready_for_confirmation': False, 'authorized': False, 'executed': False, 'errors': ['MALFORMED_INPUT']}


def main():
    parser = argparse.ArgumentParser(description='Offline Note Rate plan gate: no authorization, no execution.')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--library', required=True)
    args = parser.parse_args()
    try:
        values = []
        for path in (args.plan, args.context, args.library):
            with open(path, encoding='utf-8') as stream:
                values.append(json.load(stream, object_pairs_hook=unique_object, parse_constant=reject_constant, parse_float=Decimal))
        result = validate(*values)
        code = 0 if result['ready_for_confirmation'] else 2
    except Exception:
        result = {'ready_for_confirmation': False, 'authorized': False, 'executed': False, 'errors': ['INPUT_ERROR']}
        code = 3
    print(json.dumps(result, ensure_ascii=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
