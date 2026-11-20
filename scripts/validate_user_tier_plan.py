#!/usr/bin/env python3
"""Disabled legacy user-confirmed Tier write-plan gate; Tier is not removed.

Run: python3 validate_user_tier_plan.py --plan PRIVATE.json --context PRIVATE.json
     --library PRIVATE.json
Input signature and JSON/CLI interface are retained. Object inputs always fail
closed with TIER_PROJECT_CONTEXT_UNSUPPORTED and exit 2; invalid JSON/CLI exits 3.
No network, authorization, write, or source/identifier output occurs.

Neither a user confirmation nor an eligibility-only Note can establish evidence
for a project-specific result, the real project/Target Profile association, or
project-isolated Tier storage in Moka. This legacy candidate-profile-only path
therefore cannot approve add, replace, or skip, even for a single project. A new
implementation must first verify those real system capabilities and independently
assess the appropriate project-specific evidence. Utility parsers remain importable
for compatibility but do not validate a write plan or prove source semantics.
"""
import argparse
import json
import re
import sys
import unicodedata

import validate_note_tier_plan as old

need = old.need
claim = old.claim

# Deliberately restrictive. Blocks uncertain, conditional, negative, revoking or
# speculative context rather than trying to reason a negation away.
USER_UNSAFE = re.compile(
    r'不|未|无|否|别|没|莫|撤回|取消|停止|暂停|仅查看|只查看|'
    r'可能|也许|或许|大概|似乎|假设|假如|倘若|如果|除非|是否|是不是|'
    r'待确认|待定|建议|考虑|疑问|存疑|尚需|尚待|尚未|暂定|预计|'
    r'示例|例子|假装|虚构|玩笑|说笑|引述|引用|错误|误会|误称|错了|'
    r'\b(?:not|no|never|without|neither|nor|except|unless|if|maybe|might|'
    r'could|possibly|perhaps|tentative|uncertain|unconfirmed|pending|suggest|'
    r'proposed|hypothetical|fictional|joke|joking|pretend\w*|incorrect|wrong|'
    r'error|denied|deny|revoke\w*|withdraw\w*|cancel\w*|stop|pause)\b|'
    r"\b(?:don't|doesn't|isn't|wasn't|can't|won't|shouldn't|wouldn't)\b", re.I)
NUMERIC_TIER = re.compile(r'(?<![A-Za-z])tier\s*[:#=]?\s*[0-9]+(?![A-Za-z0-9])', re.I)
OTHER_USER_RESULT = re.compile(
    r'(?<![A-Za-z])tier\s*[:#=]?\s*(?:one|two|three|four|一|二|三|四)(?![A-Za-z])|'
    r'(?:overall|final|candidate|actual|current|new|correct)\s*'
    r'(?:result|rating|grade|level|classification|decision|conclusion)?\s*'
    r'(?:is|was|now|[:=])\s*(?:level\s*)?[1-9]\b|'
    r'(?:总体|整体|最终|候选人|实际|当前|结论|结果|评级|等级)'
    r'[^\n。;；]{0,18}[1-9一二三四][级档]?|'
    r'(?:标|打|贴|设|改|选)[^\n。;；]{0,12}[1-4一二三四]档', re.I)
CRITERION_LINE = re.compile(
    r'^\s*(?:[-*]\s*)?(?:符合\s+Tier\s+[1-4]\s*准入(?:条件|要求)?|'
    r'Meets\s+Tier\s+[1-4]\s+eligibility(?:\s+requirements)?)\s*[。.]?\s*$', re.I)
CRITERION_INLINE = re.compile(
    r'符合\s+Tier\s+[1-4]\s*准入(?:条件|要求)?(?=\s*(?:[,，;；。.!！?？\n)]|$))', re.I)
CRITERION_UNSAFE = re.compile(
    r'不|未|无|否|非|没|莫|尚|可能|也许|或许|大概|似乎|假设|假如|倘若|'
    r'如果|除非|存疑|待定|待确认|怀疑|推测|估计|接近|几乎|疑似|'
    r'\b(?:not|no|never|without|maybe|might|could|possibly|perhaps|if|unless|'
    r'uncertain|unconfirmed|pending|hypothetical)\b', re.I)
OTHER_OVERALL = re.compile(
    r'\b(?:overall|final|candidate|actual|current|new|correct)\b[^\n.;；]{0,40}'
    r'\b(?:result|outcome|rating|grade|level|classification|decision|conclusion|tier)\b|'
    r'\b(?:result|outcome|rating|grade|level|classification|decision|conclusion)\s*'
    r'(?:(?:is|was|now)\s*|[:=]\s*)?[1-9]\b|'
    r'\b(?:overall|final)\s*(?:(?:is|was|now)\s*|[:=]\s*)[1-9]\b|'
    r'(?:总体|整体|最终|实际|当前)[^\n。;；]{0,24}(?:结论|结果|评级|等级|级别|评定|评分|档次|tier)|'
    r'(?:总体|整体|最终)[^\n。;；]{0,12}(?:不通过|未通过|没有通过|不达标|不合格)|'
    r'(?:总体|整体|最终|实际|当前|结论|结果|评级|等级|级别|评定|评分|档次)'
    r'[^\n。;；]{0,18}[1-9一二三四五六七八九十](?:级|档)?|'
    r'(?:评为|判为|定为|定级为|判定为|归为|属于)\s*'
    r'(?:[1-9一二三四五六七八九十]\s*[级档]|[A-D]\b)|'
    r'(?:评级|等级|级别|定级|档位|总评)\s+[A-D]\b|'
    r'(?:总评|总评级|定级|评为|档位|结论|结果|评级|等级|级别|评定|评分|档次)'
    r'\s*(?:为|是|:|：|=)\s*[^\s，,。;；]+|'
    r'(?:结论|结果|评级|等级|级别|评定|评分|档次)\s*(?:为|是|:|：|=)?\s*'
    r'(?:[1-9一二三四五六七八九十]|tier\b|优秀|合格|不合格)', re.I)
QUESTION_BAD = re.compile(
    r'假设|假如|倘若|如果|除非|可能|也许|或许|大概|似乎|推测|猜测|'
    r'示例|例子|虚构|玩笑|误会|误称|撤回|取消|暂停|停止|'
    r'(?:不|未|无|(?<!是)否|别|没|莫|禁止|不得|拒绝|不要|不能|无需|暂不)'
    r'\s*(?:(?:应当|应该|要|可|能|该|去|把|将|为|对|给|再|直接|自动|'
    r'进行|两人|这两人|他们|候选人|本次|分别|两位|都|均|全部|同时|\s)){0,10}'
    r'(?:标记|标为|打标|打上|贴上|设置|添加|写入|写回)|'
    r'(?:不|未|无|(?<!是)否|别|没|莫|禁止|不得|不要|不能|无需|暂不|拒绝)'
    r'[^\n。;；，,?？]{0,50}(?:标记|标为|打标|打上|贴上|设置|添加|写入|写回)|'
    r'一人|三人|四人|五人|三位|四位|五位|三个候选人|四个候选人|'
    r'[013-9]\s*(?:人|位)|第[一三四五六七八九0-9](?:人|位)|其他(?:人|候选人)|'
    r'另(?:一|二|两|三|外)(?:人|位|个候选人)|其中(?:一人|一位|一个)|'
    r'(?:仅|只)(?:给|将|把|为)?(?:一人|一位|一个候选人)|'
    r'(?:以及|还有|连同|外加)\s*(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+|'
    r'[\u4e00-\u9fff]{2,4}(?=的|也|和|与|及|、))|'
    r'\b(?:not|never|maybe|might|could|possibly|perhaps|hypothetical|fictional|'
    r'cancel|withdraw|revoke|three\s+(?:people|persons|candidates))\b', re.I)
QUESTION_ACTION = re.compile(
    r'标记|标为|打标|打上|贴上|设置|添加|写入|写回|'
    r'(?:确认|决定|选择|确定)[^\n。;；?？]{0,35}(?:tier|等级|评级|结论)', re.I)
QUESTION_OTHER_GRADE = re.compile(
    r'(?:等级|级别|评级|评定|档次|结果|结论|最终|总体|整体)\s*'
    r'(?:为|是|:|：|=|第)?\s*[1-9一二三四五六七八九十](?:级|档)?|'
    r'\b(?:tier|level|rating|grade|result)\s*(?:is|was|:|=)?\s*'
    r'(?:one|two|three|four|[1-9])\b|(?:第\s*)?[1-9一二三四五六七八九十]\s*[级档]', re.I)

# Choice-bearing questions are outside this fixed-answer contract. This is
# intentionally conservative even when the connector occurs in other context;
# it also catches choices separated from Tier by Markdown or punctuation.
QUESTION_CHOICE = re.compile(r'或|还是|/|\b(?:or|versus|vs)\b', re.I)
QUESTION_LATIN_NAME = re.compile(r'(?<![A-Za-z])[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+(?![A-Za-z])')
QUESTION_EXTRA_PERSON_ACTION = re.compile(
    r'(?:^|[。；;！!？?\n])[ \t]*(?:另(?:外|有)|还有)?[ \t]*'
    r'[\u4e00-\u9fff]{2,4}[ \t]*(?:也|亦|同样|还)[^。；;！!？?\n]{0,20}'
    r'(?:标记|标为|打标|设置|添加|写入|写回)')

# These exact factual statements are not a refusal to authorize or write tags.
# Mask them only for the separate question-level authorization-negation scan;
# never change the source, the citation, the question binding or other checks.
QUESTION_UNCONFIRMED_FACT = re.compile(
    r'没有明确写出候选人的最终总体 Tier(?![A-Za-z0-9])|'
    r'确认前不会推断这两人的最终等级')


def clean_user(raw):
    need(isinstance(raw, str) and raw.strip() and not any(
        unicodedata.category(c) in ('Cf', 'Cc') and c not in '\n\r\t' for c in raw),
        'USER_INSTRUCTION_UNSUPPORTED')
    value = unicodedata.normalize('NFKC', raw)
    need(old.INJECTION.search(value) is None and old.AUTH_NEGATION.search(value) is None
         and USER_UNSAFE.search(value) is None, 'USER_INSTRUCTION_UNSUPPORTED')
    return value


def subject_pattern(subject):
    # No punctuation, parentheses, conjunctions or concealed line breaks inside
    # a subject; the literal text must come from the original user message.
    need(old.text(subject) and len(subject) <= 120 and
         all(c.isalnum() or c in ' -_\'' for c in subject) and
         not re.search(r'\b(?:and|or)\b|和|与|及|或', subject, re.I),
         'USER_SUBJECT_INVALID')
    return re.escape(unicodedata.normalize('NFKC', subject))


def match_confirmation(raw, subjects):
    need(isinstance(subjects, list) and len(subjects) in (1, 2) and
         all(isinstance(s, str) for s in subjects), 'USER_SUBJECT_INVALID')
    parts = [subject_pattern(s) for s in subjects]
    need(len({old.norm(s) for s in subjects}) == len(subjects), 'USER_SUBJECT_INVALID')
    # Require subject order exactly as it appears in the real user message.
    if len(parts) == 2:
        people = parts[0] + r'\s*(?:和|与|及|、|,|，|and|&)\s*' + parts[1]
        group = r'\s*[,，:：.…]*\s*(?:(?:两人|二人|2人)\s*)?都\s*'
    else:
        people, group = parts[0], r'\s*[,，:：]*\s*'
    pattern = re.compile(r'(?:请\s*)?(?:把|将|给)?\s*' + people + group +
                         r'(?:标记(?:为)?|标为|设置为|打上|打|贴上)\s*'
                         r'(?:为\s*)?Tier\s+([1-4])\s*(?:标签)?\s*[。.!！]?', re.I)
    # A separate sentence could say that the statement is a joke, quotation,
    # or correction. Never discard such context to manufacture confirmation.
    match = pattern.fullmatch(raw.strip())
    need(match is not None, 'USER_CONFIRMATION_FORMAT_UNSUPPORTED')
    return old.TIERS[int(match.group(1)) - 1]


def question_source(value, kind):
    """Validate metadata, not the actual origin or trustworthiness of a capture."""
    need(isinstance(value, dict) and value.get('kind') == kind and
         old.meaningful(value.get('source_id')) and old.meaningful(value.get('system')) and
         old.meaningful(value.get('record_reference')) and old.time_ok(value.get('captured_at')),
         'QUESTION_SOURCE_INVALID')
    claim(value, 'source', 'QUESTION_SOURCE_UNVERIFIED')
    segments = value.get('segments')
    need(isinstance(segments, list) and len(segments) == 1 and isinstance(segments[0], dict) and
         old.meaningful(segments[0].get('locator')) and
         isinstance(segments[0].get('text'), str) and bool(segments[0]['text'].strip()),
         'QUESTION_SOURCE_INVALID')
    return value


def question_asks_decision(clause, subjects, number):
    # Whitelist the linking words between the question cue, the target and the
    # action. Thus "是否核实以前标记 Tier 1 的邮箱" is not a rating question.
    names = '|'.join(re.escape(unicodedata.normalize('NFKC', s)) for s in subjects)
    bridge = (r'(?:\s|是否|需要|应该|应|将|把|给|为|对|这两位候选人|两位候选人|'
              r'候选人|这两人|两人|二人|2人|两位|他们|的|均|都|全部|同时|'
              r'分别|统一|一起|直接|进行|和|与|及|、|,|，|(?i:and)|&|' + names + r'){0,40}')
    cue = r'(?:是否|请(?:确认|问|选择|决定)|要不要|应(?:该|否)|可以|希望|需要)'
    action = r'(?:标记(?:为)?|标为|打标|打上|贴上|设置(?:为)?|添加|写入|写回)'
    grade = r'(?:\*\*)?Tier\s+' + number + r'(?![0-9.])(?:\*\*)?'
    decision = cue + bridge + action + bridge + grade
    final_question = cue + bridge + r'(?:最终|总体)' + bridge + r'(?:Tier|等级|评级)'
    reverse = action + bridge + grade + r'\s*(?:吗|是否(?:合适|可以|可行|正确)|[?？])'
    return re.search(decision + '|' + final_question + '|' + reverse, clause, re.I) is not None


def match_question_reply(confirmation, reply, index):
    # The original source and all citations stay complete and unmodified. Split
    # only for parsing after an exact comparison with the assistant's source.
    user_raw = reply['segments'][0]['text']
    subjects = confirmation.get('subjects')
    need(isinstance(subjects, list) and len(subjects) == 2 and
         all(isinstance(s, str) for s in subjects), 'USER_SUBJECT_INVALID')
    for subject in subjects:
        subject_pattern(subject)
        need(len(subject) >= 2 and not any(c.isdigit() for c in subject) and
             any(c.isalpha() for c in subject), 'USER_SUBJECT_INVALID')
    need(len({old.norm(s) for s in subjects}) == 2, 'USER_SUBJECT_INVALID')
    need(reply.get('conversation_role') == 'user' and
         old.meaningful(reply.get('conversation_system')) and
         old.meaningful(reply.get('conversation_record_reference')), 'USER_ROLE_UNVERIFIED')
    claim(reply, 'conversation_role', 'USER_ROLE_UNVERIFIED')

    question = question_source(confirmation.get('question_source'), 'assistant_question')
    need(question['source_id'] not in index, 'QUESTION_SOURCE_INVALID')
    need(question.get('question_role') in ('assistant', 'ask_card'), 'QUESTION_ROLE_UNVERIFIED')
    claim(question, 'question_role', 'QUESTION_ROLE_UNVERIFIED')
    claim(question, 'question_complete', 'QUESTION_INCOMPLETE')
    for stem, code in [('question_targets', 'QUESTION_TARGETS_UNVERIFIED'),
                       ('question_intent', 'QUESTION_INTENT_UNVERIFIED'),
                       ('reply_binding', 'QUESTION_BINDING_UNVERIFIED')]:
        claim(confirmation, stem, code)
    need(question['system'] == reply['conversation_system'] and
         question['record_reference'] != reply['conversation_record_reference'],
         'QUESTION_BINDING_UNVERIFIED')
    old.citation(confirmation.get('question_citation'), {question['source_id']: question}, 'assistant_question')
    qraw = question['segments'][0]['text']
    reply_match = re.fullmatch(r'两人都标记 Tier ([1-4])', user_raw)
    full_message = reply_match is None
    if full_message:
        need(question.get('question_role') == 'assistant', 'QUESTION_ROLE_UNVERIFIED')
        claim(reply, 'user_message_complete', 'USER_MESSAGE_INCOMPLETE')
        claim(confirmation, 'conversation_platform', 'QUESTION_PLATFORM_UNVERIFIED')
        need(user_raw.startswith(qraw + '\n'), 'QUESTION_BINDING_QUOTE_MISMATCH')
        reply_raw = user_raw[len(qraw) + 1:]
        reply_match = re.fullmatch(r'两人都标记 Tier ([1-4])', reply_raw)
    else:
        reply_raw = user_raw
    need(reply_match is not None, 'USER_CONFIRMATION_FORMAT_UNSUPPORTED')
    number = reply_match.group(1)

    binding_citation = confirmation.get('binding_citation')
    direct_binding = isinstance(binding_citation, dict) and binding_citation.get('source_id') == reply['source_id']
    if direct_binding:
        need(full_message and (confirmation.get('binding_source') is None or
                               confirmation.get('binding_source') == reply), 'QUESTION_BINDING_UNVERIFIED')
        old.citation(binding_citation, index, 'user')
    else:
        binding = question_source(confirmation.get('binding_source'), 'conversation_binding')
        need(binding['source_id'] != question['source_id'] and binding['source_id'] not in index,
             'QUESTION_SOURCE_INVALID')
        claim(binding, 'binding_complete', 'QUESTION_BINDING_UNVERIFIED')
        need(binding['system'] == reply['conversation_system'], 'QUESTION_BINDING_UNVERIFIED')
        old.citation(binding_citation, {binding['source_id']: binding}, 'conversation_binding')
        capture = binding['segments'][0]['text']
        # Accept only complete, unambiguous literal capture shapes. No skipped
        # intervening messages, suffixes, alternatives, or third-party replies.
        supported = {qraw + '\n' + user_raw,
                     qraw + '\n用户: ' + user_raw, qraw + '\n用户:' + user_raw,
                     qraw + '\nuser: ' + user_raw, qraw + '\nuser:' + user_raw,
                     '助手: ' + qraw + '\n用户: ' + user_raw,
                     'assistant: ' + qraw + '\nuser: ' + user_raw}
        if full_message:
            supported.add(user_raw)
        need(capture in supported, 'QUESTION_BINDING_QUOTE_MISMATCH')
    need(not any(unicodedata.category(c) in ('Cf', 'Cc') and c not in '\n\r\t' for c in qraw),
         'QUESTION_FORMAT_UNSUPPORTED')
    q = unicodedata.normalize('NFKC', qraw)
    question_for_negation = QUESTION_UNCONFIRMED_FACT.sub(' ', q)
    need(old.INJECTION.search(q) is None and old.AUTH_NEGATION.search(question_for_negation) is None and
         QUESTION_BAD.search(q) is None, 'QUESTION_FORMAT_UNSUPPORTED')
    need(len(re.findall(r'[?？]', q)) <= 1, 'QUESTION_INTENT_UNSUPPORTED')
    # Literal full names in the actual question, in the explicitly declared order.
    pair = (r'(?<![A-Za-z0-9_])' + re.escape(subjects[0]) +
            r'\s*(?:和|与|及|、|,|，|(?i:and)|&)\s*' + re.escape(subjects[1]) +
            r'(?![A-Za-z0-9_])')
    pairs = list(re.finditer(pair, qraw))
    listed = re.findall(r'(?m)(?:^|[。；;])[ \t]*(?:[-*]|[0-9]+[.、])[ \t]*([^\n:：]{1,120}?)'
                        r'[ \t]*[:：]', qraw)
    need(not listed or listed == subjects, 'QUESTION_TARGET_MISMATCH')
    # Detect supported signs of a third named person even before the pair or
    # in a separate sentence. This remains a conservative heuristic, not a
    # substitute for verified complete target review.
    residual_names = qraw
    for subject in sorted(subjects, key=len, reverse=True):
        residual_names = residual_names.replace(subject, ' ')
    need(QUESTION_LATIN_NAME.search(residual_names) is None and
         QUESTION_EXTRA_PERSON_ACTION.search(qraw) is None, 'QUESTION_TARGET_MISMATCH')
    if pairs:
        need(len(pairs) == 1, 'QUESTION_TARGET_MISMATCH')
        before = qraw[:pairs[0].start()]
        need(re.search(r'(?:和|与|及|、|\band\b|&)\s*$', before, re.I) is None and
             re.search(r'(?:[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+|'
                       r'[\u4e00-\u9fff]{2,4})\s*[,，]\s*$', before) is None,
             'QUESTION_TARGET_MISMATCH')
        # Reject an immediately extended enumeration or Latin name suffix.
        tail = qraw[pairs[0].end():]
        need(re.match(r'\s+[A-Za-z][A-Za-z\'_-]*(?:\s|[,，。；;:：?？]|$)', tail) is None,
             'QUESTION_TARGET_MISMATCH')
        need(re.match(r'\s*(?:和|与|及|、|and|&)\s*', tail, re.I) is None,
             'QUESTION_TARGET_MISMATCH')
        need(not re.match(r'\s*[,，]\s*(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+|'
                          r'[\u4e00-\u9fff]{2,4}\s*(?:和|与|及|、))', tail),
             'QUESTION_TARGET_MISMATCH')
        need(re.match(r'\s*(?:的|两人|二人|2人|两位|均|都|[。；;？?]|$|'
                      r'[,，:：]\s*(?:两人|二人|2人|两位|均|都|他们|其|请|是否|'
                      r'需要|对应|候选人|Note|备注|各自))', tail, re.I) is not None,
             'QUESTION_TARGET_MISMATCH')
    else:
        # Separately named candidate entries must be a complete exact two-item
        # list; other numbered/bulleted name-colon entries are not ignored.
        need(listed == subjects, 'QUESTION_TARGET_MISMATCH')
    need(QUESTION_CHOICE.search(q) is None, 'QUESTION_TIER_MISMATCH')
    mentions = NUMERIC_TIER.findall(q)
    need(bool(mentions) and all(re.fullmatch(r'tier\s*[:#=]?\s*' + number, m, re.I)
                                for m in mentions), 'QUESTION_TIER_MISMATCH')
    need(re.search(r'(?<![A-Za-z])tier\s*[:#=]?\s*[0-9]+\.[0-9]+', q, re.I) is None,
         'QUESTION_TIER_MISMATCH')
    need(re.search(r'(?<![A-Za-z])tier\s*[:#=]?\s*[0-9]+\s*(?:或(?:者)?|还是|/'
                   r'|、|至|到|or\b|to\b)\s*(?:tier\s*)?(?:[0-9]+|[一二三四]|'
                   r'one\b|two\b|three\b|four\b)', q, re.I) is None,
         'QUESTION_TIER_MISMATCH')
    need(QUESTION_OTHER_GRADE.search(NUMERIC_TIER.sub(' ', q)) is None,
         'QUESTION_TIER_MISMATCH')
    # The decision clause must itself ask about a tagging/rating action; a
    # qualifying fact or an unrelated question is not the matching question.
    clauses = re.split(r'[。；;\n!！]', q)
    need(any(QUESTION_ACTION.search(clause) and question_asks_decision(clause, subjects, number)
             for clause in clauses), 'QUESTION_INTENT_UNSUPPORTED')
    return old.TIERS[int(number) - 1], reply_raw


def verify_user(plan, context, index, change, profile_id, app_ids):
    """Check legacy message and identity consistency, not evidence or capability."""
    for stem, code in [('conversation_order', 'USER_ORDER_UNVERIFIED'),
                       ('user_sources_complete', 'USER_SOURCES_INCOMPLETE'),
                       ('user_authority', 'USER_AUTHORITY_UNVERIFIED')]:
        claim(context, stem, code)
    auth = context.get('user_authorization')
    need(isinstance(auth, dict), 'USER_SCOPE_UNVERIFIED')
    claim(auth, 'scope', 'USER_SCOPE_UNVERIFIED')
    single, plural = 'instruction' in auth, 'instructions' in auth
    need(single != plural, 'USER_INSTRUCTION_UNSUPPORTED')
    instructions = [auth['instruction']] if single else auth['instructions']
    need(isinstance(instructions, list) and bool(instructions), 'USER_INSTRUCTION_UNSUPPORTED')
    seen, messages = set(), []
    for item in instructions:
        src = old.citation(item, index, 'user')
        need(src['source_id'] not in seen, 'USER_INSTRUCTION_UNSUPPORTED')
        seen.add(src['source_id'])
        raw = src['segments'][0]['text']
        messages.append((src, raw))
    need(seen == {k for k, s in index.items() if s['kind'] == 'user'}, 'USER_SOURCES_INCOMPLETE')
    expected_scope = {'candidate_moka_id': profile_id,
                      'application_ids': plan['candidate']['application_ids'],
                      'taxonomy_version': plan['taxonomy_version'], 'change': change}
    need(auth.get('scope') == expected_scope, 'USER_SCOPE_PAYLOAD_MISMATCH')
    scope_text = auth.get('scope_text')
    need(old.text(scope_text), 'USER_INSTRUCTION_UNSUPPORTED')
    confirmation = context.get('user_confirmation')
    need(isinstance(confirmation, dict), 'USER_CONFIRMATION_MISSING')
    for stem, code in [('subject_binding', 'USER_SUBJECT_BINDING_UNVERIFIED'),
                       ('direct_final_tier', 'USER_FINAL_TIER_UNVERIFIED')]:
        claim(confirmation, stem, code)
    src = old.citation(confirmation.get('citation'), index, 'user')
    need(src['source_id'] in seen, 'USER_CONFIRMATION_NOT_AUTHORIZED_SOURCE')
    subjects = confirmation.get('subjects')
    subject = confirmation.get('subject')
    need(isinstance(subjects, list) and subject in subjects, 'USER_SUBJECT_INVALID')
    mode = confirmation.get('mode', 'direct')
    need(mode in ('direct', 'question_reply'), 'USER_CONFIRMATION_FORMAT_UNSUPPORTED')
    if mode == 'question_reply':
        confirmed, actual_reply = match_question_reply(confirmation, src, index)
    else:
        confirmed = match_confirmation(clean_user(src['segments'][0]['text']), subjects)
        actual_reply = src['segments'][0]['text']
    # Treat the copied assistant question only as a question, never as a fresh
    # user instruction. All other actual messages are still checked in full.
    user_texts = [actual_reply if item['source_id'] == src['source_id'] else raw
                  for item, raw in messages]
    need(any(scope_text in raw for raw in user_texts), 'USER_INSTRUCTION_UNSUPPORTED')
    cleaned = [clean_user(raw) for raw in user_texts]
    # Any additional numeric Tier in any known message, including unselected
    # messages, blocks rather than silently choosing a revision or another target.
    need(sum(len(NUMERIC_TIER.findall(clean)) for clean in cleaned) == 1,
         'USER_TIER_CONFLICT_OR_AMBIGUOUS')
    need(not any(OTHER_USER_RESULT.search(clean) for clean in cleaned),
         'USER_TIER_CONFLICT_OR_AMBIGUOUS')
    identity = old.citation(confirmation.get('subject_identity_evidence'), index, 'identity')
    raw_identity = identity['segments'][0]['text']
    need(identity['system'] == 'moka' and
         ((identity['record_type'] == 'candidate_profile' and identity['record_id'] == profile_id) or
          (identity['record_type'] == 'application' and identity['record_id'] in app_ids)) and
         old.token_count(raw_identity, subject) >= 1 and old.token_count(raw_identity, profile_id) >= 1 and
         old.NEGATIVE_LINK.search(raw_identity) is None, 'USER_SUBJECT_IDENTITY_MISMATCH')
    return confirmed


def parse_note(src):
    """Parse a legacy note string; the result is not project-specific evidence."""
    raw = src['segments'][0]['text']
    need(old.meaningful(src.get('note_date')), 'NOTE_DATE_UNVERIFIED')
    claim(src, 'note_date', 'NOTE_DATE_UNVERIFIED')
    claim(src, 'note_overall_review', 'NOTE_OVERALL_REVIEW_UNVERIFIED')
    need(not any(unicodedata.category(c) in ('Cf', 'Cc') and c not in '\n\r\t' for c in raw),
         'NOTE_UNSAFE_OR_AMBIGUOUS')
    clean = unicodedata.normalize('NFKC', raw)
    need(old.INJECTION.search(clean) is None and old.UNSAFE.search(clean) is None,
         'NOTE_UNSAFE_OR_AMBIGUOUS')
    lines = clean.splitlines()
    if lines and old.HEADER.fullmatch(lines[0]):
        need(OTHER_OVERALL.search('\n'.join(lines[1:])) is None, 'NOTE_TIER_BODY_AMBIGUOUS')
        return old.parse_tier(raw)
    # Mask only the recognized short criterion clause for parsing, never the
    # surrounding sentence. Source, exact citation and evidence stay unchanged.
    # Two mentions on a single paragraph were unsupported by the original gate.
    residual_lines = []
    for line in lines:
        if CRITERION_LINE.fullmatch(line):
            residual_lines.append('')
            continue
        matches = list(CRITERION_INLINE.finditer(line))
        if matches:
            need(len(matches) == 1, 'NOTE_UNSAFE_OR_AMBIGUOUS')
            match = matches[0]
            # Inspect the entire sentence including comma-separated qualifications,
            # but do not import an unrelated negation from another paragraph.
            before = line[:match.start()]
            after = line[match.end():]
            begin = max((before.rfind(c) for c in '。.!！？?;；'), default=-1) + 1
            ending = re.search(r'[。.!！？?;；]', after)
            sentence_end = match.end() + (ending.start() if ending else len(after))
            need(CRITERION_UNSAFE.search(line[begin:sentence_end]) is None,
                 'NOTE_UNSAFE_OR_AMBIGUOUS')
            line = CRITERION_INLINE.sub(' ', line)
        residual_lines.append(line)
    residual = '\n'.join(residual_lines)
    need(OTHER_OVERALL.search(residual) is None, 'NOTE_TIER_FORMAT_UNSUPPORTED')
    return old.parse_tier(residual) if residual.strip() else None


def evidence(plan, index, profile_id, app_ids, confirmed):
    """Legacy aggregation entry point retained, but never selects a Tier."""
    raise old.Blocked(old.TIER_PROJECT_CONTEXT_UNSUPPORTED)

def _validate(plan, context, library):
    need(all(isinstance(v, dict) for v in (plan, context, library)), 'MALFORMED_INPUT')
    # A confirmation or caller-supplied verification flag cannot bypass this.
    raise old.Blocked(old.TIER_PROJECT_CONTEXT_UNSUPPORTED)

def validate(plan, context, library):
    try:
        return _validate(plan, context, library)
    except old.Blocked as exc:
        return old.failure(str(exc))
    except Exception:
        return old.failure('MALFORMED_INPUT')


def main(argv=None):
    try:
        parser = old.Parser(description='Disabled legacy user-confirmed Tier gate; all Tier plans are blocked.')
        parser.add_argument('--plan', required=True)
        parser.add_argument('--context', required=True)
        parser.add_argument('--library', required=True)
        args = parser.parse_args(argv)
        values = []
        for path in (args.plan, args.context, args.library):
            with open(path, encoding='utf-8') as stream:
                values.append(json.load(stream, object_pairs_hook=old.unique_object,
                                        parse_constant=old.reject_constant))
        output = validate(*values)
        code = 0 if output['ready_for_confirmation'] else 2
    except Exception:
        output, code = old.failure('INPUT_ERROR'), 3
    print(json.dumps(output, ensure_ascii=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
