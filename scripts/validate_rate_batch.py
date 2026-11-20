#!/usr/bin/env python3
"""Offline cross-record review of Moka Rate plans; never authorize or execute.

Input: {"items": [{"plan": {...}, "context": {...}, "sharing": {...}?}, ...]}.
Optional sharing metadata is meaningful only after independent verification.
A pass does not establish that evidence, identities, approval, or permissions
are genuine or current. Never fabricate fields or flags to satisfy this tool.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from validate_rate_write_plan import (Blocked, number, reject_constant, text,
                                     unique_object, validate)


def load_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=unique_object,
                         parse_constant=reject_constant)


def validate_batch(batch, library):
    result = {"authorized": False, "executed": False,
              "cross_record_review_required": True, "results": [], "errors": []}
    if not isinstance(batch, dict) or not isinstance(batch.get("items"), list) or not batch["items"]:
        result["errors"] = ["MALFORMED_OR_EMPTY_BATCH"]
        return result
    items = batch["items"]
    results = []
    for index, item in enumerate(items):
        plan = item.get("plan") if isinstance(item, dict) else None
        context = item.get("context") if isinstance(item, dict) else None
        candidate = plan.get("candidate") if isinstance(plan, dict) else None
        candidate = candidate if isinstance(candidate, dict) else {}
        rec_id = candidate.get("moka_id")
        checked = validate(plan, context, library)
        results.append({"index": index, "record_id": rec_id if text(rec_id) else None,
                        "status": "ready" if checked["ready_for_confirmation"] else "blocked",
                        "errors": list(checked["errors"])})

    def block(indices, code):
        for i in indices:
            results[i]["status"] = "blocked"
            if code not in results[i]["errors"]:
                results[i]["errors"].append(code)

    ids = collections.defaultdict(list)
    names = collections.defaultdict(list)
    verified_groups = collections.defaultdict(list)
    for i, item in enumerate(items):
        plan = item.get("plan") if isinstance(item, dict) else None
        candidate = plan.get("candidate") if isinstance(plan, dict) else None
        candidate = candidate if isinstance(candidate, dict) else {}
        if text(candidate.get("moka_id")):
            ids[candidate["moka_id"]].append(i)
        if text(candidate.get("name")):
            names[" ".join(candidate["name"].split()).casefold()].append(i)
        sharing = item.get("sharing") if isinstance(item, dict) else None
        if sharing is not None:
            if (not isinstance(sharing, dict) or sharing.get("identity_verified") is not True
                    or not text(sharing.get("candidate_key"))):
                block([i], "SHARING_IDENTITY_UNVERIFIED")
            else:
                verified_groups[sharing["candidate_key"]].append(i)
    for group in ids.values():
        if len(group) > 1:
            block(group, "DUPLICATE_APPLICATION_ID")
    for group in names.values():
        if len(group) <= 1:
            continue
        # Same names do not imply the same person. Require independently verified
        # identity keys to separate or link every member before a batch pass.
        if any(not isinstance(items[i].get("sharing"), dict)
               or items[i]["sharing"].get("identity_verified") is not True
               or not text(items[i]["sharing"].get("candidate_key")) for i in group):
            block(group, "SAME_NAME_IDENTITY_UNVERIFIED")

    for group in verified_groups.values():
        if len(group) <= 1:
            continue
        meta = [items[i]["sharing"] for i in group]
        if any(m.get("tags_shared_verified") is not True or type(m.get("tags_shared")) is not bool
               for m in meta) or len({m.get("tags_shared") for m in meta}) != 1:
            block(group, "TAG_SHARING_UNVERIFIED_OR_CONFLICTING")
            continue
        try:
            rates = {number(items[i]["plan"]["expected_rate"]) for i in group}
            targets = {items[i]["plan"]["changes"][0]["tag_value"] for i in group}
        except (Blocked, KeyError, TypeError, IndexError):
            block(group, "CANDIDATE_RATE_CONFLICT_OR_INVALID")
            continue
        if len(rates) != 1 or len(targets) != 1:
            block(group, "CANDIDATE_RATE_CONFLICT_OR_INVALID")
            continue
        if any(results[i]["status"] == "blocked" for i in group):
            block(group, "RELATED_RECORD_BLOCKED")
            continue
        if meta[0]["tags_shared"]:
            # One ready record only. Re-read every related application after
            # that write; it may already display the shared tag.
            for i in group[1:]:
                results[i]["status"] = "deferred_shared"
                results[i]["errors"].append("RECHECK_AFTER_RELATED_RECORD")

    result["results"] = results
    result["counts"] = dict(collections.Counter(x["status"] for x in results))
    result["all_ready"] = all(x["status"] == "ready" for x in results)
    return result


def main():
    parser = argparse.ArgumentParser(description="Offline batch review; never authorizes or executes")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--output", required=True, help="Private output JSON file")
    args = parser.parse_args()
    try:
        batch, library = load_json(args.batch), load_json(args.library)
        result = validate_batch(batch, library)
        target = Path(args.output)
        if target.resolve() in (Path(args.batch).resolve(), Path(args.library).resolve()):
            raise ValueError("output must not overwrite input")
        # Avoid writing personal application data to a world-readable file.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(target, flags, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"counts": result.get("counts", {}),
                          "all_ready": result.get("all_ready", False),
                          "authorized": False, "executed": False,
                          "errors": result["errors"]}, ensure_ascii=False))
        return 2 if result["errors"] or result["counts"].get("blocked", 0) else 0
    except (OSError, ValueError, TypeError):
        print(json.dumps({"authorized": False, "executed": False,
                          "errors": ["INPUT_OR_OUTPUT_ERROR"]}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
