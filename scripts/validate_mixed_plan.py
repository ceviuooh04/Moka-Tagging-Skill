#!/usr/bin/env python3
"""Offline consistency gate for paired taxonomy and Rate plans; never authorizes or executes.

JSON input layout is supplied as five files: --taxonomy-plan, --taxonomy-context,
--rate-plan, --rate-context, and the separately supplied --library. The plans
and contexts have the schemas expected by validate_taxonomy_plan.validate and
validate_rate_write_plan.validate. Both plans identify their candidate via
candidate.moka_id and taxonomy_version. Every change must use system="moka",
the same record_id as both candidate IDs, field="candidate_custom_tags", and
operation="add"; at least one taxonomy change and exactly one Rate change are
required. Both plan versions must equal library.taxonomy_version.

All Tier changes are blocked with TIER_PROJECT_CONTEXT_UNSUPPORTED, including
Tier+Rate pairs, because project-associated storage and safe replacement are
not verified by the taxonomy gate. Candidate Profile fields are not prohibited
by this limitation. A separate cross-record identity binding is also not
established by this mixed gate; a future Tier capability must verify that binding
as well as project context and preservation of evidence and history.

Both contexts must contain current_tags.moka as complete lists of
{tag_group, tag_value} objects and must assert current_tags_verified=true,
current_tag_groups_verified=true, nonempty current_tags_verification_reference
and current_tag_groups_verification_reference, plus current_tags_snapshot_verified=true,
nonempty current_tags_snapshot_verification_reference and nonempty snapshot_id.
The snapshot IDs must match. Their normalized (NFKC, case-folded, whitespace
collapsed) group/value pairs are compared as a multiset, preserving duplicates.
Each context also needs evidence provenance: at least one sources entry with
nonempty source_id, system="moka", matching record_id, url, captured_at, and
nonempty segments. This verifies only shape/consistency, not that the statements,
sources, snapshot freshness, completeness, or identity are true. A caller must
independently establish those facts from this run's genuine Moka read; do not
fabricate flags, references, IDs, or data. This module contains no site access.

Only if the cross-plan checks pass are both existing validators called with the
same supplied library. Ready means both return ready_for_confirmation=true;
authorized and executed are always false. CLI emits only bounded error codes,
never input values or personal evidence. Exit codes: 0 ready for confirmation,
2 structurally blocked, 3 input/CLI error. This is not permission to write.
"""
import argparse
import json
import sys
import unicodedata
from collections import Counter
from decimal import Decimal

import validate_rate_write_plan
import validate_taxonomy_plan


class Blocked(Exception):
    pass


def need(ok, code):
    if not ok:
        raise Blocked(code)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def norm(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def context_tags(context):
    need(isinstance(context, dict), "MALFORMED_CONTEXT")
    tags_obj = context.get("current_tags")
    need(isinstance(tags_obj, dict) and isinstance(tags_obj.get("moka"), list), "MALFORMED_CONTEXT")
    need(context.get("current_tags_verified") is True and text(context.get("current_tags_verification_reference")),
         "CURRENT_TAGS_UNVERIFIED")
    need(context.get("current_tag_groups_verified") is True and text(context.get("current_tag_groups_verification_reference")),
         "CURRENT_TAG_GROUPS_UNVERIFIED")
    need(context.get("current_tags_snapshot_verified") is True and
         text(context.get("current_tags_snapshot_verification_reference")) and text(context.get("snapshot_id")),
         "SNAPSHOT_UNVERIFIED")
    identity = context.get("candidate")
    need(isinstance(identity, dict) and identity.get("match_status") == "verified" and text(identity.get("moka_id")),
         "IDENTITY_UNVERIFIED")
    sources = context.get("sources")
    need(isinstance(sources, list) and any(
        isinstance(s, dict) and s.get("system") == "moka" and s.get("record_id") == identity["moka_id"] and
        all(text(s.get(k)) for k in ("source_id", "url", "captured_at")) and
        isinstance(s.get("segments"), list) and bool(s["segments"]) and
        all(isinstance(seg, dict) and text(seg.get("locator")) and text(seg.get("text")) for seg in s["segments"])
        for s in sources), "SNAPSHOT_PROVENANCE_MISSING")
    normalized = []
    for tag in tags_obj["moka"]:
        need(isinstance(tag, dict) and text(tag.get("tag_group")) and text(tag.get("tag_value")),
             "CURRENT_TAGS_INVALID")
        normalized.append((norm(tag["tag_group"]), norm(tag["tag_value"])))
    return identity["moka_id"], context["snapshot_id"], Counter(normalized)


def changes_for(plan, expected_id, *, rate):
    need(isinstance(plan, dict), "MALFORMED_INPUT")
    candidate = plan.get("candidate")
    need(isinstance(candidate, dict) and text(candidate.get("moka_id")), "IDENTITY_UNVERIFIED")
    need(candidate["moka_id"] == expected_id, "IDENTITY_MISMATCH")
    changes = plan.get("changes")
    need(isinstance(changes, list), "MALFORMED_INPUT")
    need(len(changes) == (1 if rate else len(changes)) and (bool(changes) if not rate else len(changes) == 1),
         "CHANGE_COUNT_INVALID")
    for change in changes:
        need(isinstance(change, dict) and change.get("system") == "moka" and
             change.get("record_id") == expected_id, "TARGET_NOT_ALLOWED")
        need(change.get("field") == "candidate_custom_tags", "FIELD_NOT_ALLOWED")
        need(change.get("operation") == "add", "OPERATION_NOT_ALLOWED")
    return candidate


def validate(taxonomy_plan, taxonomy_context, rate_plan, rate_context, library):
    try:
        need(all(isinstance(x, dict) for x in (taxonomy_plan, taxonomy_context, rate_plan, rate_context, library)),
             "MALFORMED_INPUT")
        for plan in (taxonomy_plan, rate_plan):
            changes = plan.get("changes")
            need(not (isinstance(changes, list) and any(
                isinstance(change, dict) and text(change.get("tag_group")) and
                norm(change["tag_group"]) == "tier" for change in changes)),
                 "TIER_PROJECT_CONTEXT_UNSUPPORTED")
        tc = taxonomy_plan.get("candidate")
        rc = rate_plan.get("candidate")
        need(isinstance(tc, dict) and isinstance(rc, dict) and text(tc.get("moka_id")) and
             tc.get("moka_id") == rc.get("moka_id"), "IDENTITY_MISMATCH")
        record_id = tc["moka_id"]
        changes_for(taxonomy_plan, record_id, rate=False)
        changes_for(rate_plan, record_id, rate=True)
        version = library.get("taxonomy_version")
        need(text(version) and taxonomy_plan.get("taxonomy_version") == version and
             rate_plan.get("taxonomy_version") == version, "TAXONOMY_VERSION_MISMATCH")
        tid, tsid, ttags = context_tags(taxonomy_context)
        rid, rsid, rtags = context_tags(rate_context)
        need(tid == rid == record_id, "IDENTITY_MISMATCH")
        need(text(tsid) and tsid == rsid, "SNAPSHOT_MISMATCH")
        need(ttags == rtags, "CURRENT_TAGS_MISMATCH")
        taxonomy_result = validate_taxonomy_plan.validate(taxonomy_plan, taxonomy_context, library)
        rate_result = validate_rate_write_plan.validate(rate_plan, rate_context, library)
        ready = taxonomy_result.get("ready_for_confirmation") is True and rate_result.get("ready_for_confirmation") is True
        errors = []
        if taxonomy_result.get("ready_for_confirmation") is not True:
            errors.append("TAXONOMY_GATE_BLOCKED")
        if rate_result.get("ready_for_confirmation") is not True:
            errors.append("RATE_GATE_BLOCKED")
        return {"ready_for_confirmation": ready, "authorized": False, "executed": False, "errors": errors}
    except Blocked as exc:
        return {"ready_for_confirmation": False, "authorized": False, "executed": False, "errors": [str(exc)]}
    except Exception:
        return {"ready_for_confirmation": False, "authorized": False, "executed": False, "errors": ["MALFORMED_INPUT"]}


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
        parser = Parser(add_help=False, description="Offline mixed-plan consistency gate; never authorizes or executes.")
        parser.add_argument("--taxonomy-plan", required=True)
        parser.add_argument("--taxonomy-context", required=True)
        parser.add_argument("--rate-plan", required=True)
        parser.add_argument("--rate-context", required=True)
        parser.add_argument("--library", required=True)
        args = parser.parse_args(argv)
        inputs = []
        for path in (args.taxonomy_plan, args.taxonomy_context, args.rate_plan, args.rate_context, args.library):
            with open(path, encoding="utf-8") as stream:
                inputs.append(json.load(stream, object_pairs_hook=unique_object,
                                        parse_constant=reject_constant, parse_float=Decimal))
        output = validate(*inputs)
        code = 0 if output["ready_for_confirmation"] else 2
    except Exception:
        output, code = {"ready_for_confirmation": False, "authorized": False,
                        "executed": False, "errors": ["INPUT_ERROR"]}, 3
    print(json.dumps(output, ensure_ascii=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
