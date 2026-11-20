#!/usr/bin/env python3
"""Offline Moka taxonomy structural gate; never authorizes or executes.

Country, Language, Project Category and Knowledge Domain changes are checked
against the supplied plan, context, library and literal evidence. Rate changes
use the independent validate_rate_write_plan.py numeric gate. Library flags,
references and source excerpts are caller assertions, not proof of truth,
identity, freshness, completeness, authority, semantics or platform behavior.

Tier belongs to each project or Target Profile independently, with its own
assessment evidence and history. Different projects' results do not imply a
conflict, a cross-project maximum, or automatic replacement of one another.
This gate cannot currently verify project-associated storage, safe replacement
and history preservation from actual runtime data. It therefore blocks *every*
Tier change, for every taxonomy version and field, with
TIER_PROJECT_CONTEXT_UNSUPPORTED before checking other plan details. This is a
capability limitation, not a ban on Candidate Profile fields and not a claim
that Moka does or does not provide project-isolated storage. Non-Tier changes
are not blocked merely because current tags include Tier values. The caller
must independently verify all facts; never fabricate inputs or references.
"""

import argparse
import json
import re
import sys
import unicodedata
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

GROUPS = ("country", "language", "project category", "knowledge domain", "tier")
# Historical schema constants, retained for callers; no Tier evaluation is performed.
DIMENSIONS = ("professional knowledge and expertise", "relevant practical experience",
              "task complexity", "ability to work independently", "professional judgment",
              "responsibility for decisions and outcomes")
TIER_VALUES = ("tier 1", "tier 2", "tier 3", "tier 4")
TIER_EXCEPTION = "tier not included"
DEFAULT_LIBRARY = Path(__file__).resolve().parents[1] / "assets" / "tag-library.snapshot.json"

# Generic labels cannot stand in for the actual Moka group. Even if an
# organization really names a group this way, manual review is required.
UNKNOWN_GROUPS = frozenset({
    "other", "others", "other group", "other groups", "other tags", "unknown",
    "unknown group", "unspecified", "unassigned", "unclassified", "not classified",
    "not known", "not sure", "none", "null", "n/a", "na", "unverified", "misc",
    "miscellaneous", "其他", "其它", "其他组", "其它组", "未知", "未知组", "未分类",
    "未分组", "不明", "待确认", "待核实", "待定",
})
UNKNOWN_VALUES = UNKNOWN_GROUPS | frozenset({
    "not available", "unavailable", "not applicable", "no data", "no information", "not provided",
    "not disclosed", "no value", "none specified", "not specified", "not assessed", "not_assessed",
    "unassessed", "not evaluated", "unevaluated", "n a", "n.a.", "nil", "pending", "tbd", "todo",
    "to be determined", "unknown/unspecified", "unknown/no data", "not included", "无", "暂无",
    "无数据", "未提供", "未说明", "不适用", "未评估", "未测评",
}) | frozenset(f"{group} not included" for group in GROUPS) | {"rate not included"}


class Blocked(Exception):
    def __init__(self, code, pending_count=0):
        super().__init__(code)
        self.pending_count = pending_count


def need(condition, code="MALFORMED_INPUT"):
    if not condition:
        raise Blocked(code)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return isinstance(value, list) and all(text(item) for item in value)


def normalized(value):
    # For current-label comparison and the fail-closed Tier preflight;
    # requested formal group/value must otherwise match the library exactly.
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def meaningful(value):
    if not text(value):
        return False
    value = normalized(value)
    return value not in UNKNOWN_VALUES and any(char.isalnum() for char in value)


def result(errors, pending_count=0):
    output = {"ready_for_confirmation": not errors, "authorized": False,
              "executed": False, "errors": errors}
    if pending_count:
        output["tier_pending_verification_count"] = pending_count
    # Preserve the legacy code while directing Rate callers to the numeric gate.
    if errors == ["UNKNOWN_TAG_GROUP"]:
        output["guidance"] = "Rate changes must use the independent validate_rate_write_plan.py gate."
    return output


def _parse_record(excerpt):
    """Parse a literal JSON object or semicolon-separated record, not its truth."""
    try:
        if excerpt.lstrip().startswith("{"):
            fields = json.loads(excerpt, object_pairs_hook=unique_object, parse_constant=reject_constant)
            if not isinstance(fields, dict):
                return None
        else:
            fields = {}
            for part in excerpt.strip().split(";"):
                if not part.strip():
                    continue
                match = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\r\n]+?)\s*", part)
                if not match or match.group(1) in fields:
                    return None
                fields[match.group(1)] = match.group(2).strip()
        return fields
    except (ValueError, TypeError):
        return None


def _record_matches(excerpt, expected):
    fields = _parse_record(excerpt)
    return fields is not None and all(isinstance(fields.get(key), str) and fields[key] == value
                                      for key, value in expected.items())


def _validate(plan, context, library):
    need(all(isinstance(x, dict) for x in (plan, context, library)))
    # Block before identity, current-tag conflict, library and evidence checks:
    # those checks cannot establish project-safe Tier storage or replacement.
    changes = plan.get("changes")
    if isinstance(changes, list):
        need(not any(isinstance(change, dict) and text(change.get("tag_group")) and
                     normalized(change["tag_group"]) == "tier" for change in changes),
             "TIER_PROJECT_CONTEXT_UNSUPPORTED")
    candidate, identity = plan.get("candidate"), context.get("candidate")
    need(isinstance(candidate, dict) and isinstance(identity, dict), "IDENTITY_UNVERIFIED")
    need(candidate.get("match_status") == identity.get("match_status") == "verified", "IDENTITY_UNVERIFIED")
    need(text(candidate.get("moka_id")) and candidate["moka_id"] == identity.get("moka_id"), "IDENTITY_MISMATCH")
    record_id = candidate["moka_id"]

    for key in ("allowed_record_ids", "allowed_fields", "allowed_operations", "current_tags"):
        mapping = context.get(key)
        need(isinstance(mapping, dict) and isinstance(mapping.get("moka"), list), "MALFORMED_CONTEXT")
        if key != "current_tags":
            need(strings(mapping["moka"]), "MALFORMED_CONTEXT")
    need(record_id in context["allowed_record_ids"]["moka"], "TARGET_NOT_ALLOWED")
    need(context.get("current_tags_verified") is True and text(context.get("current_tags_verification_reference")),
         "CURRENT_TAGS_UNVERIFIED")
    need(context.get("current_tag_groups_verified") is True and
         text(context.get("current_tag_groups_verification_reference")), "CURRENT_TAG_GROUPS_UNVERIFIED")
    current_by_group = {}
    for tag in context["current_tags"]["moka"]:
        need(isinstance(tag, dict) and text(tag.get("tag_group")) and text(tag.get("tag_value")), "CURRENT_TAGS_INVALID")
        group = normalized(tag["tag_group"])
        need(group not in UNKNOWN_GROUPS, "CURRENT_TAG_GROUP_UNKNOWN")
        current_by_group.setdefault(group, set()).add(normalized(tag["tag_value"]))

    changes = plan.get("changes")
    need(isinstance(changes, list), "MALFORMED_INPUT")
    need(bool(changes), "NO_CHANGES")

    need(library.get("current_approved_version_verified") is True and text(library.get("approval_reference")) and
         text(library.get("current_version_verification_reference")), "LIBRARY_NOT_APPROVED")
    need(library.get("active_status_verified") is True and text(library.get("active_status_verification_reference")),
         "ACTIVE_STATUS_UNVERIFIED")
    need(library.get("moka_id_mapping_verified") is True and text(library.get("moka_id_mapping_reference")),
         "MOKA_MAPPING_UNVERIFIED")
    need(text(plan.get("taxonomy_version")) and plan["taxonomy_version"] == library.get("taxonomy_version"),
         "TAXONOMY_VERSION_MISMATCH")
    tags = library.get("tags")
    need(isinstance(tags, list) and bool(tags), "MALFORMED_LIBRARY")
    by_pair, by_id = {}, {}
    for tag in tags:
        need(isinstance(tag, dict) and text(tag.get("tag_group")) and text(tag.get("tag_value")), "MALFORMED_LIBRARY")
        pair = (tag["tag_group"], tag["tag_value"])
        need(pair not in by_pair, "TAG_AMBIGUOUS")
        by_pair[pair] = tag
        remote_id = tag.get("moka_tag_id")
        need(remote_id is None or isinstance(remote_id, str), "MALFORMED_LIBRARY")
        if text(remote_id):
            need(remote_id not in by_id, "MOKA_ID_AMBIGUOUS")
            by_id[remote_id] = pair

    sources = context.get("sources")
    need(isinstance(sources, list), "EVIDENCE_SOURCE_INVALID")
    source_index = {}
    for source in sources:
        need(isinstance(source, dict) and all(text(source.get(k)) for k in
             ("source_id", "system", "record_id", "url", "captured_at")), "EVIDENCE_SOURCE_INVALID")
        need(source["system"] == "moka" and source["record_id"] == record_id, "SOURCE_IDENTITY_MISMATCH")
        try:
            parsed = urlsplit(source["url"])
            valid_url = (parsed.scheme in ("http", "https") and bool(parsed.hostname) and
                         parsed.username is None and parsed.password is None)
        except ValueError:
            valid_url = False
        need(valid_url, "EVIDENCE_SOURCE_INVALID")
        need(source["source_id"] not in source_index, "DUPLICATE_SOURCE_ID")
        segments = source.get("segments")
        need(isinstance(segments, list) and bool(segments), "EVIDENCE_SOURCE_INVALID")
        segment_index = {}
        for segment in segments:
            need(isinstance(segment, dict) and text(segment.get("locator")) and text(segment.get("text")),
                 "EVIDENCE_SOURCE_INVALID")
            need(segment["locator"] not in segment_index, "AMBIGUOUS_LOCATOR")
            segment_index[segment["locator"]] = segment["text"]
        source_index[source["source_id"]] = segment_index

    def quotes(evidence):
        need(isinstance(evidence, list) and bool(evidence), "EVIDENCE_MISSING")
        for quote in evidence:
            need(isinstance(quote, dict) and all(text(quote.get(k)) for k in
                 ("source_id", "locator", "excerpt")), "EVIDENCE_MISSING")
            segments = source_index.get(quote["source_id"])
            need(segments is not None, "EVIDENCE_SOURCE_NOT_FOUND")
            content = segments.get(quote["locator"])
            need(content is not None and quote["excerpt"] in content, "QUOTE_NOT_VERBATIM")

    seen, cardinality = set(), {}
    for change in changes:
        need(isinstance(change, dict) and all(text(change.get(k)) for k in
             ("system", "record_id", "field", "operation", "tag_group", "tag_value", "remote_tag_id")),
             "MALFORMED_INPUT")
        need(change["system"] == "moka" and change["record_id"] == record_id and
             change["record_id"] in context["allowed_record_ids"]["moka"], "TARGET_NOT_ALLOWED")
        need(change["field"] in context["allowed_fields"]["moka"], "FIELD_NOT_ALLOWED")
        need(change["operation"] == "add" and "add" in context["allowed_operations"]["moka"], "OPERATION_NOT_ALLOWED")
        group, value = change["tag_group"], change["tag_value"]
        need(group in GROUPS, "UNKNOWN_TAG_GROUP")
        exception_value = f"{group} not included"
        # Do not let a different group's exception or a near-spelling bypass the gate.
        if normalized(value) in {f"{g} not included" for g in GROUPS} | {"rate not included"}:
            need(value == exception_value, "EXCEPTION_GROUP_MISMATCH")
        tag = by_pair.get((group, value))
        need(tag is not None, "TAG_NOT_IN_LIBRARY")
        need(tag.get("status") == "Active", "TAG_NOT_ACTIVE")
        need(text(tag.get("moka_tag_id")) and change["remote_tag_id"] == tag["moka_tag_id"],
             "REMOTE_TAG_ID_MISMATCH")
        key = (group, value)
        need(key not in seen, "DUPLICATE_CHANGE")
        seen.add(key)

        single = group == "country"
        if group == "project category":
            need(context.get("project_category_selection_type") in ("single", "multi") and
                 text(context.get("project_category_decision_reference")), "PC_DECISION_REQUIRED")
            if library["taxonomy_version"].strip().casefold() in ("1.1", "v1.1"):
                need(context["project_category_selection_type"] == "multi", "PC_V11_MULTI_REQUIRED")
            single = context["project_category_selection_type"] == "single"
        cardinality[group] = cardinality.get(group, 0) + 1
        need(not single or cardinality[group] <= 1, "SINGLE_SELECT_CONFLICT")
        current = current_by_group.get(group, set())
        need(normalized(value) not in current, "EXISTING_TAG")
        need(not single or not current, "SINGLE_SELECT_CONFLICT")
        quotes(change.get("evidence"))

        if value == exception_value:
            assessment = change.get("exception_assessment")
            need(isinstance(assessment, dict), "EXCEPTION_ASSESSMENT_REQUIRED")
            known_value = assessment.get("known_value")
            need(meaningful(known_value), "EXCEPTION_KNOWN_VALUE_INVALID")
            need(assessment.get("no_matching_tag_verified") is True and
                 meaningful(assessment.get("comparison_reference")), "EXCEPTION_COMPARISON_UNVERIFIED")
            need(meaningful(tag.get("moka_tag_id")), "REMOTE_TAG_ID_MISMATCH")
            need(any(known_value in q["excerpt"] for q in change["evidence"]),
                 "EXCEPTION_EVIDENCE_MISMATCH")
            need(not any(normalized(t["tag_group"]) == group and t.get("status") == "Active" and
                         normalized(t["tag_value"]) != exception_value and
                         normalized(t["tag_value"]) == normalized(known_value) for t in tags),
                 "EXCEPTION_KNOWN_VALUE_MATCHES_TAG")

    return 0


def validate(plan, context, library):
    try:
        pending_count = _validate(plan, context, library)
        return result([], pending_count)
    except Blocked as exc:
        return result([str(exc)], exc.pending_count)
    except Exception:
        # Never print raw inputs, source texts, paths or exception details.
        return result(["MALFORMED_INPUT"])


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("INPUT_ERROR")


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate key")
        obj[key] = value
    return obj


def reject_constant(value):
    raise ValueError("non-finite JSON constant")


def main(argv=None):
    try:
        parser = Parser(add_help=False, description="Offline structural gate; never authorizes or executes.")
        parser.add_argument("--plan", required=True)
        parser.add_argument("--context", required=True)
        parser.add_argument("--library", default=str(DEFAULT_LIBRARY))
        args = parser.parse_args(argv)
        inputs = []
        for path in (args.plan, args.context, args.library):
            with open(path, encoding="utf-8") as stream:
                inputs.append(json.load(stream, object_pairs_hook=unique_object,
                                        parse_constant=reject_constant, parse_float=Decimal))
        output = validate(*inputs)
        code = 0 if output["ready_for_confirmation"] else 2
    except Exception:
        output, code = result(["INPUT_ERROR"]), 3
    print(json.dumps(output, ensure_ascii=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
