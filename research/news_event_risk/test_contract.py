"""Contract, boundary, traceability, and determinism tests."""

from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
import unittest
from pathlib import Path

from contract import (
    ContractError,
    POLICY_PATH,
    SCHEMA_PATH,
    VECTORS_PATH,
    canonical_json,
    contract_digest,
    evaluate,
    load_json,
    validate_policy,
    validate_vector,
)


ROOT = Path(__file__).resolve().parent


class PolicyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_json(POLICY_PATH)
        cls.schema = load_json(SCHEMA_PATH)
        cls.vectors = load_json(VECTORS_PATH)

    def test_policy_and_schema_validate(self) -> None:
        validate_policy(self.policy, self.schema)

    def test_every_vector_matches_exact_expected_result(self) -> None:
        for vector in self.vectors:
            with self.subTest(vector=vector["vector_id"]):
                validate_vector(vector)
                self.assertEqual(vector["expected"], evaluate(self.policy, vector))

    def test_every_rule_and_reason_code_is_unique_used_and_traced(self) -> None:
        rules = self.policy["rules"]
        rule_ids = [item["rule_id"] for item in rules]
        reasons = [item["reason_code"] for item in rules]
        traced = {rule_id for vector in self.vectors for rule_id in vector["rule_ids"]}
        observed = {
            reason
            for vector in self.vectors
            for reason in evaluate(self.policy, vector)["reason_codes"]
        }
        self.assertEqual(len(rule_ids), len(set(rule_ids)))
        self.assertEqual(len(reasons), len(set(reasons)))
        self.assertEqual(set(rule_ids), traced)
        self.assertEqual(set(reasons), observed)

    def test_order_independence_for_events_rules_and_object_keys(self) -> None:
        vector = next(item for item in self.vectors if item["vector_id"] == "TV-053-PRIORITY-BLOCK-BEATS-WARNING")
        baseline = evaluate(self.policy, vector)
        shuffled_policy = copy.deepcopy(self.policy)
        shuffled_policy["rules"].reverse()
        # Validation rejects unordered priority definitions only if values change;
        # evaluator sorts matches by explicit priority, never file order.
        validate_policy(shuffled_policy)
        shuffled_vector = copy.deepcopy(vector)
        shuffled_vector["events"].reverse()
        shuffled_vector = json.loads(canonical_json(shuffled_vector))
        self.assertEqual(baseline, evaluate(shuffled_policy, shuffled_vector))

    def test_duplicate_event_does_not_raise_severity(self) -> None:
        vector = next(item for item in self.vectors if item["vector_id"] == "TV-050-DUPLICATE")
        baseline = evaluate(self.policy, vector)
        duplicated = copy.deepcopy(vector)
        duplicated["events"] = duplicated["events"] * 3
        self.assertEqual(baseline, evaluate(self.policy, duplicated))

    def test_point_in_time_revision_does_not_mutate_original(self) -> None:
        original = next(item for item in self.vectors if item["vector_id"] == "TV-054-POINT-IN-TIME-ORIGINAL")
        revised = next(item for item in self.vectors if item["vector_id"] == "TV-055-POINT-IN-TIME-REVISED")
        first = evaluate(self.policy, original)
        self.assertEqual("S0", first["severity"])
        self.assertEqual("S1", evaluate(self.policy, revised)["severity"])
        self.assertEqual(first, evaluate(self.policy, original))

    def test_social_can_never_change_direction_or_increase_confidence_or_size(self) -> None:
        social = [
            item for item in self.vectors
            if any(event.get("event_type") in {"ceo_company_social", "x_social_sentiment"} for event in item["events"])
        ]
        self.assertTrue(social)
        for vector in social:
            result = evaluate(self.policy, vector)
            self.assertEqual("none", result["direction_effect"])
            self.assertLessEqual(result["confidence_delta_max"], 0)
            self.assertLessEqual(result["size_multiplier_max"], 1.0)

    def test_warning_cannot_lower_or_cancel_block(self) -> None:
        vector = next(item for item in self.vectors if item["vector_id"] == "TV-053-PRIORITY-BLOCK-BEATS-WARNING")
        result = evaluate(self.policy, vector)
        self.assertEqual("trade_block", result["action"])
        self.assertEqual("S3", result["severity"])

    def test_validator_rejects_duplicate_reason_and_bad_boundary(self) -> None:
        duplicate = copy.deepcopy(self.policy)
        duplicate["rules"][1]["reason_code"] = duplicate["rules"][0]["reason_code"]
        with self.assertRaises(ContractError):
            validate_policy(duplicate)
        bad = copy.deepcopy(self.policy)
        bad["rules"][9]["freshness_limit_seconds"] = -1
        with self.assertRaises(ContractError):
            validate_policy(bad)

    def test_validator_rejects_missing_rule_field_unknown_condition_and_severity(self) -> None:
        missing = copy.deepcopy(self.policy)
        del missing["rules"][0]["recovery_condition"]
        with self.assertRaises(ContractError):
            validate_policy(missing)
        unknown = copy.deepcopy(self.policy)
        unknown["rules"][0]["condition"] = {"kind": "magic"}
        with self.assertRaises(ContractError):
            validate_policy(unknown)
        severity = copy.deepcopy(self.policy)
        severity["rules"][0]["severity"] = "S9"
        with self.assertRaises(ContractError):
            validate_policy(severity)

    def test_generation_is_reproducible(self) -> None:
        tracked = {
            name: (ROOT / name).read_bytes()
            for name in [
                "policy.json", "test_vectors.json", "artifact_manifest.json",
                "TRACEABILITY.md", "GAPS.md",
            ]
        }
        subprocess.run(
            [sys.executable, str(ROOT / "generate_artifacts.py")],
            check=True,
            cwd=ROOT.parents[1],
        )
        self.assertEqual(tracked, {name: (ROOT / name).read_bytes() for name in tracked})

    def test_contract_digest_is_stable(self) -> None:
        self.assertEqual(64, len(contract_digest(self.policy)))
        shuffled = json.loads(canonical_json(self.policy))
        self.assertEqual(contract_digest(self.policy), contract_digest(shuffled))


if __name__ == "__main__":
    unittest.main()
