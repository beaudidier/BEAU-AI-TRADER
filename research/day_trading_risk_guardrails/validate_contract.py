#!/usr/bin/env python3
"""Strict validator/evaluator for the research-only guardrail contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

from generate_contract import DOC, OUT, build_contract, build_vectors, canonical_json, triggers


REQUIRED_RULE_FIELDS = {
    "rule_id", "reason_code", "category", "priority", "condition",
    "missing_or_conflicting_input", "user_message", "recovery_action",
    "override_allowed", "override_authority", "future_live_status",
    "unresolved_dependencies", "source",
}
REQUIRED_MODES = {"BEGINNER", "ADVANCED", "PAPER", "FUTURE_LIVE"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def primary_reason(active: list[str], priorities: dict[str, int]) -> tuple[str, list[str]]:
    ordered = sorted(set(active), key=lambda code: (priorities[code], code))
    return ordered[0], ordered


def validate() -> tuple[dict, dict, list[dict]]:
    errors: list[str] = []
    policy = load_json(OUT / "policy.json")
    vectors_doc = load_json(OUT / "testvectors.json")
    manifest = load_json(OUT / "manifest.json")

    expected_policy = build_contract()
    expected_vectors = build_vectors(expected_policy)
    if canonical_json(policy) != canonical_json(expected_policy):
        errors.append("policy.json is not the canonical generator output")
    if canonical_json(vectors_doc) != canonical_json(expected_vectors):
        errors.append("testvectors.json is not the canonical generator output")

    if policy.get("status") != "RESEARCH_PAPER_ONLY":
        errors.append("policy status must be RESEARCH_PAPER_ONLY")
    if policy.get("live_execution") != "HARD_DISABLED":
        errors.append("live execution must be HARD_DISABLED")
    if policy.get("legal_or_regulatory_compliance_claim") is not False:
        errors.append("compliance claim must be false")
    if set(policy.get("modes", {})) != REQUIRED_MODES:
        errors.append("exactly four required modes must be defined")

    rules = policy.get("rules", [])
    rule_ids = [rule.get("rule_id") for rule in rules]
    codes = [rule.get("reason_code") for rule in rules]
    priorities = [rule.get("priority") for rule in rules]
    if len(rule_ids) != len(set(rule_ids)):
        errors.append("duplicate rule_id")
    if len(codes) != len(set(codes)):
        errors.append("duplicate reason_code")
    if sorted(priorities) != list(range(1, len(rules) + 1)):
        errors.append("priorities must be unique and contiguous")

    for rule in rules:
        missing = REQUIRED_RULE_FIELDS - set(rule)
        if missing:
            errors.append(f"{rule.get('rule_id')}: missing fields {sorted(missing)}")
        if rule.get("override_allowed") is not False:
            errors.append(f"{rule.get('rule_id')}: override must be false")
        if rule.get("override_authority") != "NONE":
            errors.append(f"{rule.get('rule_id')}: override authority must be NONE")
        if not rule.get("recovery_action"):
            errors.append(f"{rule.get('rule_id')}: recovery action missing")
        condition = rule.get("condition", {})
        if condition.get("kind") == "threshold":
            key = condition.get("mode_limit_key")
            for mode, limits in policy["modes"].items():
                value = limits.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    errors.append(f"{rule['rule_id']}: invalid {mode}.{key}")
            flags = [
                condition.get("max_allows_equality"),
                condition.get("min_allows_equality"),
                condition.get("tripwire_blocks_equality"),
            ]
            if sum(flag is True for flag in flags) != 1:
                errors.append(f"{rule['rule_id']}: conflicting boundary flags")

    vector_results = []
    covered: dict[str, set[str]] = {code: set() for code in codes}
    priority_map = {rule["reason_code"]: rule["priority"] for rule in rules}
    vector_ids: set[str] = set()
    for vector in vectors_doc.get("vectors", []):
        vector_id = vector.get("testvector_id")
        if not vector_id or vector_id in vector_ids:
            errors.append(f"missing or duplicate testvector_id: {vector_id}")
            continue
        vector_ids.add(vector_id)
        kind = vector["kind"]
        passed = True
        if vector.get("reason_code") in covered:
            covered[vector["reason_code"]].add(kind)
        if kind == "boundary":
            rule = next(r for r in rules if r["reason_code"] == vector["reason_code"])
            observed = vector["input"]["observed"]
            limit = vector["input"]["limit"]
            blocked = triggers(rule["condition"]["boundary"], observed, limit)
            actual = "BLOCK" if blocked else "ALLOW"
            passed = actual == vector["expected"]["decision"]
        elif kind == "boolean":
            actual = "BLOCK" if vector["input"]["violation"] else "ALLOW"
            passed = actual == vector["expected"]["decision"]
        elif kind == "fail_closed":
            passed = vector["expected"] == {
                "decision": "BLOCK", "primary_reason": "RISK_STATE_UNAVAILABLE"
            }
        elif kind == "multi_block":
            first, ordered = primary_reason(vector["active_reasons"], priority_map)
            shuffled = list(vector["active_reasons"])
            random.Random(42).shuffle(shuffled)
            shuffled_first, shuffled_ordered = primary_reason(shuffled, priority_map)
            passed = (
                first == vector["expected"]["primary_reason"]
                and ordered == vector["expected"]["all_reasons"]
                and first == shuffled_first
                and ordered == shuffled_ordered
            )
        elif kind == "stateful":
            passed = (
                len(vector["steps"]) >= 2
                and vector["expected"]["primary_reason"] in priority_map
                and vector["expected"]["decision"] == "BLOCK"
            )
            covered[vector["expected"]["primary_reason"]].add(kind)
        elif kind == "future_live_fail_closed":
            passed = (
                vector["mode"] == "FUTURE_LIVE"
                and vector["expected"]["decision"] == "BLOCK"
                and vector["expected"]["primary_reason"] == "LIVE_TRADING_DISABLED"
            )
            covered["LIVE_TRADING_DISABLED"].add(kind)
        else:
            errors.append(f"{vector_id}: unknown kind {kind}")
            passed = False
        if not passed:
            errors.append(f"{vector_id}: expected result mismatch")
        vector_results.append(
            {
                "testvector_id": vector_id,
                "rule_id": vector.get("rule_id", "STATE_OR_COMBINATION"),
                "reason_code": vector.get(
                    "reason_code", vector["expected"].get("primary_reason")
                ),
                "result": "PASS" if passed else "FAIL",
            }
        )

    for code, kinds in covered.items():
        required = "boundary" if next(
            r for r in rules if r["reason_code"] == code
        )["condition"]["kind"] == "threshold" else "boolean"
        if required not in kinds:
            errors.append(f"{code}: no {required} vector")
        if "fail_closed" not in kinds:
            errors.append(f"{code}: no fail-closed missing-input vector")

    policy_hash = hashlib.sha256(canonical_json(policy).encode()).hexdigest()
    vectors_hash = hashlib.sha256(canonical_json(vectors_doc).encode()).hexdigest()
    if manifest.get("contract_sha256") != policy_hash:
        errors.append("contract manifest hash mismatch")
    if manifest.get("testvectors_sha256") != vectors_hash:
        errors.append("testvector manifest hash mismatch")

    if errors:
        raise ValueError("\n".join(errors))
    return policy, vectors_doc, vector_results


def write_coverage(policy: dict, vector_results: list[dict]) -> None:
    by_code: dict[str, list[str]] = {}
    for result in vector_results:
        if result["reason_code"] in {rule["reason_code"] for rule in policy["rules"]}:
            by_code.setdefault(result["reason_code"], []).append(result["testvector_id"])
    lines = [
        "# Day-Trading Guardrail Contract Coverage",
        "",
        "Generated by the standalone research validator. This is not a legal or",
        "regulatory compliance report and does not enable live execution.",
        "",
        "| Rule ID | Reason code | Test vectors | Result |",
        "|---|---|---|---|",
    ]
    for rule in policy["rules"]:
        ids = ", ".join(sorted(by_code.get(rule["reason_code"], [])))
        lines.append(
            f"| `{rule['rule_id']}` | `{rule['reason_code']}` | {ids} | PASS |"
        )
    lines.extend(
        [
            "",
            f"- Rules: {len(policy['rules'])}",
            f"- Test vectors: {len(vector_results)}",
            "- Duplicate, missing, and unused reason codes: 0",
            "- Missing or undefined recovery actions: 0",
            "- Overrides permitted: 0",
            "- Future live execution: HARD_DISABLED",
            "",
        ]
    )
    (OUT / "COVERAGE.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-coverage", action="store_true")
    args = parser.parse_args()
    try:
        policy, _, results = validate()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    if args.write_coverage:
        write_coverage(policy, results)
    print(
        f"PASS: {len(policy['rules'])} rules, {len(results)} vectors, "
        "0 overrides, live HARD_DISABLED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
