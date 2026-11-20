#!/usr/bin/env python3
"""Disabled legacy Note Tier write-plan gate; the Tier field still exists.

Usage: python3 validate_note_tier_plan.py --plan P.json --context C.json --library L.json
Input signature and JSON/CLI interface are retained for callers. With object inputs,
all plans (including an apparent no-op/skip) fail closed with
TIER_PROJECT_CONTEXT_UNSUPPORTED and CLI exit 2. Invalid JSON/CLI exits 3.
No network, authorization, write, or source/identifier output occurs.

The old candidate-profile-only contract cannot establish actual project and Target
Profile association for each independent assessment or prove project-isolated Moka
Tier storage and preservation of other projects. Single-project assertions, Note
results and user confirmation do not prove those capabilities. A safe future gate
requires verified system behavior plus project-specific evidence and must not reuse
cross-project grade aggregation. Parsing/utility functions below remain available
for existing imports; they do not validate a write plan or prove source semantics.
"""
import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit

TIERS = tuple(f'tier {i}' for i in range(1, 5))
TIER_PROJECT_CONTEXT_UNSUPPORTED = 'TIER_PROJECT_CONTEXT_UNSUPPORTED'
PRECONDITIONS = ['recheck_identity_and_target', 'recheck_visible_notes_and_known_tier_evidence',
                 'recheck_complete_current_tags_and_groups', 'recheck_approved_active_library_and_mapping',
                 'recheck_permission_and_user_scope']
POSTCONDITIONS = ['reread_candidate_profile_tier', 'verify_all_previous_non_tier_tags_preserved']
FAILURE_ACTION = 'stop_reread_escalate_no_unapproved_changes'
UNKNOWN = {'unknown', 'none', 'null', 'n/a', 'na', 'tbd', 'todo', 'unverified',
           'other', 'others', 'other group', 'unclassified', 'misc', 'miscellaneous',
           'not specified', 'not available', 'unknown group', '未核实', '未知', '其他', '其它', '待定'}
HEADER = re.compile(r'^[ \t]*tier[ \t]+([1-4])[ \t]*\.?[ \t]*$', re.I)
MENTION = re.compile(r'(?<![a-z])tier(?:s)?(?=$|[^a-z])', re.I)
INJECTION = re.compile(r'\b(?:ignore|disregard|override|bypass|jailbreak|forget)\b|'
                       r'\b(?:system|developer|assistant)\s*(?:prompt|message|instruction|:)|'
                       r'<\s*/?\s*(?:system|assistant|developer)\s*>|'
                       r'忽略|无视|绕过|提示词|系统消息|系统指令|开发者指令', re.I)
UNSAFE = re.compile(r'\b(?:draft|tentative|provisional|pending|unconfirmed|unverified|'
                    r'example|hypothetical|outdated|superseded|revised|incorrect|invalid|'
                    r'not\s+(?:(?:the|a)\s+)?(?:final|actual|candidate)|not\s+assigned|'
                    r'not\s+valid|no\s+longer\s+valid|another\s+(?:candidate|applicant)|'
                    r'unrelated\s+to\s+(?:this\s+)?(?:candidate|applicant))\b|'
                    r'未确认|待确认|待定|仅供参考|假设|示例|已作废|已失效|尚未完成|草稿|非本候选人', re.I)
CRITERIA = r'(?:education|experience|years?|knowledge|expertise|skill|skills|criterion|criteria|requirement|requirements|threshold|dimension|background|学历|经验|知识|技能|要求|维度)'
NEGATIVE_LINK = re.compile(r'\b(?:not\s+(?:linked|associated|related|matched|matching|belongs)|'
                           r'does\s+not\s+(?:match|belong)|mismatch|unrelated|different\s+(?:person|candidate|profile))\b|'
                           r'不关联|无关联|不匹配|非同一|不是同一|不同候选人', re.I)
# ASCII boundaries allow natural code-switching such as 'tier根据note里面',
# while preventing matches inside words such as 'tiered' or 'notebook'.
AUTH_TIER = r'(?<![a-z])tier(?![a-z])|等级'
AUTH_NOTE = r'(?<![a-z])notes?(?![a-z])|备注'
AUTH_ADD = re.compile(r'(?:添加|加上|打上|打|标注|贴上|贴|设置|补充)[^。；;\n]{0,25}'
                      r'(?:标签|(?<![a-z])tags?(?![a-z])|(?<![a-z])tier(?![a-z]))|打标|'
                      r'\b(?:add|apply)\b[^.;!?\n]{0,50}\b(?:tags?|labels?|tier)\b|'
                      r'\b(?:tag|label)\b\s+(?:the\s+)?(?:candidates?|profiles?|them)\b', re.I)
AUTH_RELATION = re.compile(r'(?:根据|依据|按照|基于|参考|按|from|based\s+on|according\s+to|using|per)'
                           r'\s*(?:the\s+)?(?:' + AUTH_NOTE + r')', re.I)
AUTH_CONTINUATION = re.compile(r'(?:同意|批准|允许)[^。；;\n]{0,16}(?:扩展|继续)|'
                               r'\b(?:agree|approv\w*|allow)\b[^.;!?\n]{0,35}'
                               r'\b(?:extend\w*|continu\w*)\b', re.I)
AUTH_NEGATION = re.compile(
    r'(?:未经|未|不|无|没有|从未|尚未|并未|无意)'
    r'(?:\s|明确|真正|任何|正式|完全|曾经|实际|事先|对此|本次|这次|该次|此项|相关){0,5}'
    r'(?:授权|批准|同意|允许|许可)|'
    r'(?:拒绝|撤回|取消)\s*(?:授权|批准|同意|许可)|'
    r'(?:不要|不得|禁止|不准|不许|不可以|不可|不能|不应|请勿|暂不|别|拒绝|撤回|取消|停止|暂停|不|未|没有)'
    r'[^。；;\n]{0,25}(?:添加|打标|标签|标注|贴标签|修改|写入|写回|执行|处理|'
    r'(?<![a-z])tier(?![a-z])|等级)|'
    r'(?:仅|只)\s*(?:查看|检查|建议|推荐|列出|阅读)'
    r'(?=$|[，,。；;\s]|(?<![a-z])tier(?![a-z])|标签|等级)|'
    r'(?:先停(?:一下|止)?|暂停|停止)(?=$|[。；;！!\s])|'
    r'\b(?:stop|pause|halt)(?:\s+(?:this|now|processing|tagging|writing))?\s*[.!?]?(?=\s*$)|'
    r'\b(?:not|never|no|without|deny|denied|declin\w*|revok\w*|withdraw\w*|rescind\w*|withhold|'
    r'don\'t|doesn\'t|didn\'t|cannot|can\'t)\b[^.;!?\n]{0,35}'
    r'\b(?:authori[sz]\w*|allow\w*|permit\w*|approv\w*|consent\w*|permission|agree\w*)\b|'
    r'\b(?:do\s+not|don\'t|never|must\s+not|cannot|can\'t|should\s+not|no|prohibit|forbid|'
    r'avoid|refrain\s+from|not\s+to)\b[^.;!?\n]{0,60}'
    r'\b(?:add\w*|tags?|tagging|labels?|labell?ing|modify\w*|writ\w*|apply\w*|tier)\b|'
    r'\b(?:tier|tags?|labels?)\b[^.;!?\n]{0,40}'
    r'\b(?:must\s+not|should\s+not|cannot|not\s+to\s+be|not\s+be|are\s+not|is\s+not|never)\b'
    r'[^.;!?\n]{0,25}\b(?:add\w*|tag\w*|label\w*|appl\w*|writ\w*)\b', re.I)


class Blocked(Exception):
    pass


def need(condition, code):
    if not condition:
        raise Blocked(code)


def norm(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def meaningful(value):
    return text(value) and norm(value) not in UNKNOWN and any(c.isalnum() for c in value)


def group_label(value):
    return meaningful(value) or (text(value) and norm(value) in {'other', 'others', '其他', '其它'})


def claim(obj, stem, code):
    need(isinstance(obj, dict) and obj.get(stem + '_verified') is True and
         meaningful(obj.get(stem + '_verification_reference')), code)


def time_ok(value):
    try:
        if not text(value):
            return False
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (ValueError, OverflowError):
        return False


def url_ok(url, host=None):
    try:
        u = urlsplit(url)
        return (text(url) and u.scheme == 'https' and bool(u.hostname) and
                u.username is None and u.password is None and u.port in (None, 443) and
                (host is None or u.hostname == host))
    except (TypeError, ValueError):
        return False


def token_count(raw, value):
    return len(re.findall(r'(?<![\w-])' + re.escape(value) + r'(?![\w-]|\.[\w])', raw))


def both_identifiers(raw, a, b):
    return token_count(raw, a) >= (2 if a == b else 1) and (a == b or token_count(raw, b) >= 1)


def parse_tier(raw):
    """Parse a first-line string only; this proves no project context or evidence."""
    need(isinstance(raw, str) and bool(raw.strip()), 'SOURCE_TEXT_INVALID')
    need(not any(unicodedata.category(c) in ('Cf', 'Cc') and c not in '\n\r\t' for c in raw),
         'NOTE_UNSAFE_OR_AMBIGUOUS')
    clean = unicodedata.normalize('NFKC', raw)
    need(INJECTION.search(clean) is None, 'NOTE_UNSAFE_OR_AMBIGUOUS')
    lines = clean.splitlines()
    first = HEADER.fullmatch(lines[0]) if lines else None
    if not first:
        need(MENTION.search(clean) is None, 'NOTE_TIER_FORMAT_UNSUPPORTED')
        return None
    number = int(first.group(1))
    body = '\n'.join(lines[1:])
    need(UNSAFE.search(body) is None, 'NOTE_UNSAFE_OR_AMBIGUOUS')
    need(re.search(r'\b(?:overall|final|candidate|new)\b[^\n]{0,40}'
                   r'\b(?:tier|level|rating|grade|result|outcome|decision|classification|conclusion|verdict)'
                   r'\s*(?:(?:is|was)\s*|[:=]\s*)?[1-4]\b|'
                   r'\b(?:overall|final)\s*(?:is|[:=])\s*(?:now\s+)?[1-4]\b|'
                   r'\b(?:overall|final)\b[^\n]{0,40}\btier\s+[1-4]\b|'
                   r'\b(?:(?:overall|final|candidate|actual|current|new|correct)\s+)?'
                   r'(?:result|outcome|decision|conclusion|verdict|rating|grade)\s*'
                   r'(?:is|was|[:=])\s*[1-4]\b|'
                   r'\b(?:this|that|it)\s+(?:is|was)\s+(?:the\s+)?'
                   r'(?:overall|final|actual|correct)\s+(?:result|rating|outcome|conclusion)\b',
                   body, re.I) is None, 'NOTE_TIER_BODY_AMBIGUOUS')
    for line in lines[1:]:
        if not MENTION.search(line):
            continue
        # Remove only recognized criterion statements, wherever embedded; any
        # remaining Tier mention still requires review, including a revision.
        # Require a clause boundary so a following overall conclusion cannot be
        # absorbed into a criterion or left as a misleading unnumbered fragment.
        end_clause = r'(?=\s*(?:[.;!?]|$))'
        remaining = re.sub(rf'(?:\bmeets?\s+tier\s+[1-4]\s+{CRITERIA}\b|'
                           rf'\bnot\s+met\s+for\s+tier\s+[1-4](?:\s+{CRITERIA})?\b){end_clause}',
                           ' ', line, flags=re.I)
        remaining = re.sub(r'\btier\s+[1-4]\s*:\s*not\s+shown\s+for\s+coding\s+tasks\b' + end_clause,
                           ' ', remaining, flags=re.I)
        remaining = re.sub(r'^\s*(?:[-*]\s*)?difficult[- ]case\s+handling\s*'
                           r'\(\s*tier\s+[1-4]\s*\)\s*:\s*partial\b' + end_clause,
                           ' ', remaining, flags=re.I)
        def remove_other_negative(match):
            if int(match.group(1) or match.group(2)) == number:
                raise Blocked('NOTE_TIER_BODY_AMBIGUOUS')
            return ' '
        # A colon after "Not Tier 1" introduces an explanation, not a new
        # positive result. Subsequent Tier mentions remain subject to review.
        end_negative = r'(?=\s*(?:[.:;!?]|$))'
        remaining = re.sub(r'(?:\bnot\s+tier\s+([1-4])\b|\btier\s+([1-4])\s*:\s*not\s+met\b)' + end_negative,
                           remove_other_negative, remaining, flags=re.I)
        need(MENTION.search(remaining) is None, 'NOTE_TIER_BODY_AMBIGUOUS')
    return TIERS[number - 1]


def source_index(context):
    host = context.get('moka_host')
    need(text(host) and host == host.lower() and re.fullmatch(r'[a-z0-9.-]+', host) is not None,
         'MOKA_HOST_INVALID')
    sources = context.get('sources')
    need(isinstance(sources, list), 'SOURCES_INVALID')
    index = {}
    for src in sources:
        need(isinstance(src, dict) and meaningful(src.get('source_id')) and
             src.get('source_id') not in index and src.get('kind') in
             ('note', 'identity', 'tag_snapshot', 'other_tier', 'user') and
             time_ok(src.get('captured_at')), 'SOURCES_INVALID')
        claim(src, 'source', 'SOURCE_UNVERIFIED')
        segments = src.get('segments')
        need(isinstance(segments, list) and len(segments) == 1 and isinstance(segments[0], dict) and
             meaningful(segments[0].get('locator')) and isinstance(segments[0].get('text'), str) and
             bool(segments[0]['text'].strip()), 'SOURCE_TEXT_INVALID')
        kind = src['kind']
        if kind == 'user':
            need(src.get('system') == 'user', 'SOURCE_SYSTEM_INVALID')
        else:
            need(meaningful(src.get('system')) and meaningful(src.get('record_type')) and
                 meaningful(src.get('record_id')) and
                 url_ok(src.get('url'), host if src['system'] == 'moka' else None), 'SOURCE_INVALID')
        if kind in ('note', 'tag_snapshot'):
            need(src.get('system') == 'moka', 'SOURCE_SYSTEM_INVALID')
        if kind == 'note':
            need(meaningful(src.get('author')), 'NOTE_AUTHOR_UNVERIFIED')
            claim(src, 'raw_note_complete', 'NOTE_RAW_COMPLETENESS_UNVERIFIED')
        index[src['source_id']] = src
    return index


def citation(value, index, kind):
    need(isinstance(value, dict) and set(value) == {'source_id', 'locator', 'excerpt'} and
         text(value.get('source_id')) and text(value.get('locator')) and
         isinstance(value.get('excerpt'), str), 'CITATION_INVALID')
    src = index.get(value['source_id'])
    need(src is not None and src['kind'] == kind, 'CITATION_SOURCE_MISMATCH')
    seg = src['segments'][0]
    need(value['locator'] == seg['locator'] and value['excerpt'] == seg['text'], 'QUOTE_NOT_VERBATIM_FULL')
    return src


def all_citations(citations, index, kind):
    need(isinstance(citations, list), 'CITATIONS_INCOMPLETE')
    expected = {key for key, source in index.items() if source['kind'] == kind}
    seen = set()
    for item in citations:
        src = citation(item, index, kind)
        need(src['source_id'] not in seen, 'CITATIONS_INCOMPLETE')
        seen.add(src['source_id'])
    need(seen == expected, 'CITATIONS_INCOMPLETE')


def verify_identity(plan, context, index):
    candidate = plan.get('candidate')
    need(isinstance(candidate, dict) and set(candidate) == {'moka_id', 'application_ids'} and
         meaningful(candidate.get('moka_id')) and isinstance(candidate.get('application_ids'), list) and
         candidate['application_ids'] and all(meaningful(v) for v in candidate['application_ids']) and
         len(candidate['application_ids']) == len(set(candidate['application_ids'])) and
         candidate == context.get('candidate'), 'IDENTITY_MISMATCH')
    profile_id, app_ids = candidate['moka_id'], candidate['application_ids']
    need(isinstance(context.get('allowed_profile_ids'), list) and profile_id in context['allowed_profile_ids'] and
         isinstance(context.get('allowed_application_ids'), list) and
         all(a in context['allowed_application_ids'] for a in app_ids), 'TARGET_NOT_ALLOWED')
    links = context.get('identity_links')
    need(isinstance(links, list), 'IDENTITY_LINK_UNVERIFIED')
    found = set()
    for link in links:
        need(isinstance(link, dict) and link.get('verified') is True and
             meaningful(link.get('verification_reference')) and link.get('candidate_moka_id') == profile_id and
             link.get('application_id') in app_ids and link['application_id'] not in found,
             'IDENTITY_LINK_UNVERIFIED')
        src = citation(link.get('evidence'), index, 'identity')
        raw = src['segments'][0]['text']
        need(src['system'] == 'moka' and
             ((src['record_type'] == 'application' and src['record_id'] == link['application_id']) or
              (src['record_type'] == 'candidate_profile' and src['record_id'] == profile_id)) and
             both_identifiers(raw, profile_id, link['application_id']) and NEGATIVE_LINK.search(raw) is None,
             'IDENTITY_LINK_EVIDENCE_MISMATCH')
        found.add(link['application_id'])
    need(found == set(app_ids), 'IDENTITY_LINK_UNVERIFIED')
    return profile_id, set(app_ids)


def associated(src, profile_id, app_ids, index):
    if src['system'] == 'moka':
        need((src['record_type'] == 'candidate_profile' and src['record_id'] == profile_id) or
             (src['record_type'] == 'application' and src['record_id'] in app_ids), 'SOURCE_IDENTITY_MISMATCH')
    else:
        need(src['kind'] == 'other_tier', 'SOURCE_SYSTEM_INVALID')
        claim(src, 'identity', 'EXTERNAL_IDENTITY_UNVERIFIED')
        identity = citation(src.get('identity_evidence'), index, 'identity')
        raw = identity['segments'][0]['text']
        need(both_identifiers(raw, profile_id, src['record_id']) and NEGATIVE_LINK.search(raw) is None,
             'EXTERNAL_IDENTITY_EVIDENCE_MISMATCH')


def verify_evidence(plan, context, index, profile_id, app_ids):
    """Legacy aggregation entry point retained, but never selects a Tier."""
    raise Blocked(TIER_PROJECT_CONTEXT_UNSUPPORTED)

def verify_registry(context):
    entries = context.get('tag_group_registry')
    need(isinstance(entries, list) and bool(entries), 'GROUP_REGISTRY_UNVERIFIED')
    by_name, ids, actual_names, tier = {}, set(), set(), None
    for entry in entries:
        need(isinstance(entry, dict) and entry.get('system') == 'moka' and
             group_label(entry.get('tag_group')) and group_label(entry.get('moka_group_name')) and
             meaningful(entry.get('remote_group_id')) and
             entry.get('role') in ('tier', 'other'), 'GROUP_REGISTRY_UNVERIFIED')
        claim(entry, 'group', 'GROUP_REGISTRY_UNVERIFIED')
        name, rid, actual = entry['tag_group'], entry['remote_group_id'], norm(entry['moka_group_name'])
        if norm(name) in {'other', 'others', '其他', '其它'}:
            need(norm(name) == actual, 'GROUP_IDENTITY_MISMATCH')
        need(norm(name) not in {norm(n) for n in by_name} and rid not in ids and actual not in actual_names,
             'GROUP_IDENTITY_AMBIGUOUS')
        need((name == 'tier') == (entry['role'] == 'tier'), 'GROUP_IDENTITY_MISMATCH')
        known_non_tier = {'手动项目标签', '手动语言标签', 'rate', 'rate 标签', 'rate标签'}
        if name == 'tier':
            need(actual not in known_non_tier, 'GROUP_IDENTITY_MISMATCH')
        else:
            need(actual not in {'tier', 'tier 标签', 'tier标签'}, 'GROUP_IDENTITY_MISMATCH')
        if name == 'tier':
            tier = entry
        by_name[name] = entry
        ids.add(rid)
        actual_names.add(actual)
    need(tier is not None, 'TIER_GROUP_UNVERIFIED')
    return by_name, tier


def verify_library(plan, library, tier_group):
    need(isinstance(library, dict) and meaningful(plan.get('taxonomy_version')) and
         plan['taxonomy_version'] == library.get('taxonomy_version'), 'TAXONOMY_VERSION_MISMATCH')
    need(library.get('current_approved_version_verified') is True and meaningful(library.get('approval_reference')) and
         meaningful(library.get('current_version_verification_reference')), 'LIBRARY_NOT_APPROVED')
    claim(library, 'active_status', 'ACTIVE_STATUS_UNVERIFIED')
    claim(library, 'tier_library_complete', 'TIER_LIBRARY_INCOMPLETE')
    need(library.get('moka_id_mapping_verified') is True and meaningful(library.get('moka_id_mapping_reference')),
         'MOKA_MAPPING_UNVERIFIED')
    tags = library.get('tags')
    need(isinstance(tags, list) and bool(tags), 'LIBRARY_INVALID')
    values, ids = {}, set()
    for tag in tags:
        need(isinstance(tag, dict) and tag.get('tag_group') == 'tier' and
             tag.get('tag_value') in TIERS + ('tier not included',) and
             tag.get('status') in ('Active', 'Inactive') and meaningful(tag.get('moka_tag_id')) and
             tag.get('moka_group_id') == tier_group['remote_group_id'], 'LIBRARY_TAG_INVALID')
        need(tag['tag_value'] not in values and tag['moka_tag_id'] not in ids, 'LIBRARY_TAG_AMBIGUOUS')
        values[tag['tag_value']] = tag
        ids.add(tag['moka_tag_id'])
    return values, ids


def verify_current(context, index, registry, library_ids, profile_id, app_ids, change):
    """Check a legacy snapshot only; add/skip is not a project-write approval."""
    current = context.get('current_tags')
    need(isinstance(current, dict) and set(current) == {'moka'} and isinstance(current['moka'], list),
         'CURRENT_TAGS_INVALID')
    snapshot = citation(context.get('current_tags_evidence'), index, 'tag_snapshot')
    need(snapshot['system'] == 'moka' and
         ((snapshot['record_type'] == 'candidate_profile' and snapshot['record_id'] == profile_id) or
          (snapshot['record_type'] == 'application' and snapshot['record_id'] in app_ids)),
         'CURRENT_TAGS_TARGET_MISMATCH')
    if snapshot['record_type'] == 'application':
        # verify_identity already requires a real link for every app_id. The
        # separate assertion is essential: same person does not prove sharing.
        claim(snapshot, 'candidate_target', 'CURRENT_TAGS_SHARING_UNVERIFIED')
    raw = snapshot['segments'][0]['text']
    ids, old = set(), []
    for tag in current['moka']:
        need(isinstance(tag, dict) and group_label(tag.get('tag_group')) and text(tag.get('tag_value')) and
             meaningful(tag.get('remote_tag_id')) and meaningful(tag.get('remote_group_id')), 'CURRENT_TAGS_INVALID')
        group = registry.get(tag['tag_group'])
        need(group is not None and group['remote_group_id'] == tag['remote_group_id'],
             'CURRENT_TAG_GROUP_OR_ID_UNVERIFIED')
        need(tag['remote_tag_id'] not in ids and tag['tag_value'] in raw, 'CURRENT_TAGS_EVIDENCE_MISMATCH')
        ids.add(tag['remote_tag_id'])
        if tag['tag_group'] == 'tier':
            old.append(tag)
        else:
            need(tag['remote_tag_id'] not in library_ids, 'TIER_GROUP_MASQUERADE')
    need(len(old) <= 1, 'MULTIPLE_EXISTING_TIER_TAGS')
    if old:
        need(old[0]['tag_value'] == change['tag_value'] and old[0]['remote_tag_id'] == change['remote_tag_id'] and
             old[0]['remote_group_id'] == change['remote_group_id'], 'OLD_TIER_DIFFERENT_OR_UNVERIFIED')
        return 'skip'
    need(change['remote_tag_id'] not in ids, 'CURRENT_TAG_ID_AMBIGUOUS')
    return 'add'


def verify_authorization(plan, context, index, change):
    """Check legacy instruction consistency only, never system capability or evidence."""
    auth = context.get('user_authorization')
    need(isinstance(auth, dict), 'USER_SCOPE_UNVERIFIED')
    claim(auth, 'scope', 'USER_SCOPE_UNVERIFIED')
    single, plural = 'instruction' in auth, 'instructions' in auth
    need(single != plural, 'USER_INSTRUCTION_UNSUPPORTED')
    instructions = [auth['instruction']] if single else auth['instructions']
    need(isinstance(instructions, list) and bool(instructions), 'USER_INSTRUCTION_UNSUPPORTED')
    seen, raw_messages = set(), []
    has_addition, has_note_tier_rule = False, False
    for item in instructions:
        src = citation(item, index, 'user')
        need(src['source_id'] not in seen, 'USER_INSTRUCTION_UNSUPPORTED')
        seen.add(src['source_id'])
        raw = src['segments'][0]['text']
        raw_messages.append(raw)
        clean = unicodedata.normalize('NFKC', raw)
        # Never make one fictitious message from several quotations; each
        # source is independently checked, in the caller-verified order.
        need(AUTH_NEGATION.search(clean) is None, 'USER_INSTRUCTION_UNSUPPORTED')
        has_addition |= AUTH_ADD.search(clean) is not None
        has_note_tier_rule |= (re.search(AUTH_TIER, clean, re.I) is not None and
                               re.search(AUTH_NOTE, clean, re.I) is not None and
                               AUTH_RELATION.search(clean) is not None)
        if AUTH_CONTINUATION.search(clean):
            need(has_addition and has_note_tier_rule, 'USER_INSTRUCTION_UNSUPPORTED')
    for src in index.values():
        if src['kind'] == 'user' and src['source_id'] not in seen:
            need(AUTH_NEGATION.search(unicodedata.normalize('NFKC', src['segments'][0]['text'])) is None,
                 'USER_INSTRUCTION_UNSUPPORTED')
    scope_text = auth.get('scope_text')
    need(text(scope_text) and any(scope_text in raw for raw in raw_messages) and
         has_addition and has_note_tier_rule,
         'USER_INSTRUCTION_UNSUPPORTED')
    expected = {'candidate_moka_id': plan['candidate']['moka_id'],
                'application_ids': plan['candidate']['application_ids'],
                'taxonomy_version': plan['taxonomy_version'], 'change': change}
    need(auth.get('scope') == expected, 'USER_SCOPE_PAYLOAD_MISMATCH')


def _validate(plan, context, library):
    need(all(isinstance(v, dict) for v in (plan, context, library)), 'MALFORMED_INPUT')
    # Assertions, extra fields and manual confirmation cannot prove system
    # capabilities. No legacy path supports even a safe project-specific skip.
    raise Blocked(TIER_PROJECT_CONTEXT_UNSUPPORTED)

def failure(code):
    result = {'ready_for_confirmation': False, 'authorized': False, 'executed': False,
              'action': 'blocked', 'post_write_reread_required': True, 'errors': [code]}
    if code == TIER_PROJECT_CONTEXT_UNSUPPORTED:
        result['explanation'] = (
            'The Tier field still exists, but this legacy gate cannot verify real project and '
            'Target Profile association, project-specific evidence, or isolated Moka storage. '
            'All Tier plans, including add and skip, are blocked; user confirmation cannot '
            'substitute for evidence or verified system capabilities.'
        )
        result['limitations'] = [
            'project_target_profile_and_evidence_association_not_verified',
            'moka_project_isolated_storage_and_other_project_preservation_not_verified',
            'manual_confirmation_cannot_bypass_evidence_or_system_verification',
        ]
    return result


def validate(plan, context, library):
    try:
        return _validate(plan, context, library)
    except Blocked as exc:
        return failure(str(exc))
    except Exception:
        # Never echo source texts, candidate identifiers, paths or exceptions.
        return failure('MALFORMED_INPUT')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('invalid JSON constant')


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('invalid input')


def main(argv=None):
    try:
        parser = Parser(description='Disabled legacy Note Tier gate; all Tier plans are blocked.')
        parser.add_argument('--plan', required=True)
        parser.add_argument('--context', required=True)
        parser.add_argument('--library', required=True)
        args = parser.parse_args(argv)
        values = []
        for path in (args.plan, args.context, args.library):
            with open(path, encoding='utf-8') as stream:
                values.append(json.load(stream, object_pairs_hook=unique_object, parse_constant=reject_constant))
        output = validate(*values)
        code = 0 if output['ready_for_confirmation'] else 2
    except Exception:
        output, code = failure('INPUT_ERROR'), 3
    print(json.dumps(output, ensure_ascii=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
