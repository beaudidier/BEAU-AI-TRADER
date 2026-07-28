"""Reproducible adversarial and malformed-input verification."""

from __future__ import annotations

import copy
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from contract import (
    ContractError,
    MANIFEST_PATH,
    POLICY_PATH,
    ROOT,
    SCHEMA_PATH,
    VECTORS_PATH,
    canonical_json,
    evaluate,
    load_json,
    validate_artifact_manifest,
    validate_policy,
    validate_vector,
)


class AdversarialContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_json(POLICY_PATH)
        cls.schema = load_json(SCHEMA_PATH)
        cls.vectors = load_json(VECTORS_PATH)
        cls.manifest = load_json(MANIFEST_PATH)
        cls.mutations = load_json(ROOT / "mutation_fixtures.json")

    def assert_policy_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.policy)
        mutation(candidate)
        with self.assertRaises(ContractError):
            validate_policy(candidate, self.schema)

    def base_vector(self) -> dict:
        return copy.deepcopy(
            next(item for item in self.vectors if item["vector_id"] == "TV-054-POINT-IN-TIME-ORIGINAL")
        )

    def assert_event_fail_closed(self, **changes) -> None:
        vector = self.base_vector()
        vector["events"][0].update(changes)
        result = evaluate(self.policy, vector)
        self.assertEqual("S3", result["severity"])
        self.assertEqual("trade_block", result["action"])
        self.assertIn("NER_CRITICAL_INPUT_INVALID", result["reason_codes"])
        self.assertEqual("none", result["direction_effect"])
        self.assertEqual(0.0, result["size_multiplier_max"])

    def test_mutation_catalog_is_unique_and_complete(self) -> None:
        ids = [item["mutation_id"] for item in self.mutations]
        self.assertEqual(32, len(ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            {f"MUT-{number:03d}" for number in range(1, 33)},
            set(ids),
        )
        for item in self.mutations:
            self.assertEqual(
                {"mutation_id", "invariant", "expected", "test_name"},
                set(item),
            )
            self.assertTrue(hasattr(self, item["test_name"]))

    def test_manifest_rejects_corrupted_artifact(self) -> None:
        validate_artifact_manifest(self.manifest)
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            for name in ["policy.json", "policy.schema.json", "test_vectors.json"]:
                shutil.copyfile(ROOT / name, temporary_root / name)
            with (temporary_root / "policy.json").open("ab") as handle:
                handle.write(b"\n")
            with self.assertRaises(ContractError):
                validate_artifact_manifest(self.manifest, temporary_root)
        malformed = copy.deepcopy(self.manifest)
        malformed["artifacts"]["policy.json"] = "not-a-digest"
        with self.assertRaises(ContractError):
            validate_artifact_manifest(malformed)

    def test_schema_mutations_are_rejected(self) -> None:
        wrong_identity = copy.deepcopy(self.schema)
        wrong_identity["$id"] = "urn:attacker:replacement"
        with self.assertRaises(ContractError):
            validate_policy(self.policy, wrong_identity)
        unsatisfied = copy.deepcopy(self.schema)
        unsatisfied["required"].append("override_authority")
        with self.assertRaises(ContractError):
            validate_policy(self.policy, unsatisfied)

    def test_policy_identity_and_precedence_mutations(self) -> None:
        self.assert_policy_rejected(
            lambda policy: policy["rules"][1].update(rule_id=policy["rules"][0]["rule_id"])
        )
        self.assert_policy_rejected(
            lambda policy: policy["rules"][1].update(reason_code=policy["rules"][0]["reason_code"])
        )
        self.assert_policy_rejected(lambda policy: policy["rules"][0].pop("rule_id"))
        self.assert_policy_rejected(lambda policy: policy["rules"].pop(10))
        self.assert_policy_rejected(lambda policy: policy["rules"][2].update(priority=2))

    def test_policy_shape_and_semantic_mutations(self) -> None:
        self.assert_policy_rejected(lambda policy: policy["rules"][8].update(action="buy"))
        self.assert_policy_rejected(lambda policy: policy["rules"][8]["audit_payload"].remove("expiry"))
        self.assert_policy_rejected(lambda policy: policy.update(override_authority="operator"))
        self.assert_policy_rejected(lambda policy: policy.update(rules=None))
        self.assert_policy_rejected(lambda policy: policy.update(event_categories=[]))
        self.assert_policy_rejected(
            lambda policy: policy["rules"][9].update(
                condition={"kind": "window", "parameters": {"start_seconds": -1}}
            )
        )
        self.assert_policy_rejected(
            lambda policy: policy["rules"][0].update(
                condition={"kind": "critical_invalid", "unexpected": True}
            )
        )

    def test_conflicting_recovery_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.policy)
        conflicting = copy.deepcopy(candidate["rules"][-1])
        conflicting["rule_id"] = "NER-999"
        conflicting["reason_code"] = "NER_CONFLICTING_RECOVERY"
        conflicting["priority"] = len(candidate["rules"]) + 1
        conflicting["condition"] = copy.deepcopy(candidate["rules"][8]["condition"])
        conflicting["severity"] = candidate["rules"][8]["severity"]
        conflicting["action"] = candidate["rules"][8]["action"]
        conflicting["recovery_condition"] = "operator may override without evidence"
        candidate["rules"].append(conflicting)
        with self.assertRaises(ContractError):
            validate_policy(candidate)

    def test_numeric_and_unit_boundary_mutations(self) -> None:
        self.assert_policy_rejected(
            lambda policy: policy["rules"][9]["condition"].update(
                start_seconds=3601, end_seconds=3600
            )
        )
        self.assert_policy_rejected(
            lambda policy: policy["rules"][18]["condition"].update(seconds=-1)
        )
        self.assert_policy_rejected(
            lambda policy: policy["rules"][18]["condition"].update(seconds=31_536_001)
        )
        self.assert_policy_rejected(
            lambda policy: policy["rules"][18]["condition"].update(seconds=True)
        )
        self.assert_policy_rejected(
            lambda policy: policy["rules"][9]["condition"].update(
                start_seconds=-36_000_000, end_seconds=36_000_000
            )
        )

    def test_malformed_vector_types_and_ranges(self) -> None:
        mutations = []
        null_events = self.base_vector()
        null_events["events"] = None
        mutations.append(null_events)
        empty_events = self.base_vector()
        empty_events["events"] = []
        mutations.append(empty_events)
        unexpected = self.base_vector()
        unexpected["unexpected"] = True
        mutations.append(unexpected)
        unsafe_size = self.base_vector()
        unsafe_size["expected"]["size_multiplier_max"] = 1.000001
        mutations.append(unsafe_size)
        positive_confidence = self.base_vector()
        positive_confidence["expected"]["confidence_delta_max"] = 1
        mutations.append(positive_confidence)
        wrong_nested_type = self.base_vector()
        wrong_nested_type["expected"]["reason_codes"] = {}
        mutations.append(wrong_nested_type)
        invalid_severity = self.base_vector()
        invalid_severity["expected"]["severity"] = "S9"
        mutations.append(invalid_severity)
        for index, candidate in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ContractError):
                validate_vector(candidate)

    def test_timestamp_mutations_fail_closed(self) -> None:
        self.assert_event_fail_closed(published_at="2026-01-15T14:00:00")
        self.assert_event_fail_closed(published_at="2026-01-15T09:00:00-05:00")
        self.assert_event_fail_closed(published_at="2026-03-08T01:59:59-05:00")
        self.assert_event_fail_closed(
            published_at="2026-01-15T14:00:02Z",
            first_seen_at="2026-01-15T14:00:01Z",
            ingested_at="2026-01-15T14:00:00Z",
        )
        self.assert_event_fail_closed(
            published_at="2026-01-15T14:00:11Z",
            first_seen_at="2026-01-15T14:00:12Z",
            ingested_at="2026-01-15T14:00:13Z",
        )
        self.assert_event_fail_closed(
            revision_state="revised",
            supersedes_event_id="evt-0",
            superseded_published_at="2026-01-15T14:00:00Z",
        )
        self.assert_event_fail_closed(
            published_at="1900-01-01T00:00:00Z",
            first_seen_at="1900-01-01T00:00:01Z",
            ingested_at="1900-01-01T00:00:02Z",
        )

    def test_randomized_order_permutations_are_identical(self) -> None:
        vector = copy.deepcopy(
            next(item for item in self.vectors if item["vector_id"] == "TV-053-PRIORITY-BLOCK-BEATS-WARNING")
        )
        vector["events"].extend(copy.deepcopy(vector["events"]) for _ in [])
        vector["events"] = vector["events"] * 3
        baseline = canonical_json(evaluate(self.policy, vector))
        for seed in range(20):
            rng = random.Random(seed)
            policy = copy.deepcopy(self.policy)
            candidate = copy.deepcopy(vector)
            rng.shuffle(policy["rules"])
            rng.shuffle(candidate["events"])
            candidate = json.loads(canonical_json(candidate))
            validate_policy(policy)
            self.assertEqual(baseline, canonical_json(evaluate(policy, candidate)))

    def test_duplicate_revision_conflict_mapping_permutations(self) -> None:
        base = copy.deepcopy(
            next(item for item in self.vectors if item["vector_id"] == "TV-053-PRIORITY-BLOCK-BEATS-WARNING")
        )
        duplicate = copy.deepcopy(base["events"][0])
        duplicate.update(duplicate_state="duplicate", duplicate_cluster_id="dup-1")
        revision = copy.deepcopy(base["events"][0])
        revision.update(
            event_id="evt-2",
            revision_state="revised",
            supersedes_event_id="evt-1",
            superseded_published_at="2026-01-15T13:00:00Z",
        )
        base["events"].extend([duplicate, revision])
        for order in [base["events"], list(reversed(base["events"]))]:
            candidate = copy.deepcopy(base)
            candidate["events"] = order
            result = evaluate(self.policy, candidate)
            self.assertEqual("S3", result["severity"])
            self.assertEqual("trade_block", result["action"])
            self.assertIn("NER_SOURCE_CONFLICT_UNRESOLVED", result["reason_codes"])
        unmapped = copy.deepcopy(base)
        unmapped["events"][0]["mapping_status"] = "ambiguous"
        self.assertEqual("trade_block", evaluate(self.policy, unmapped)["action"])

    def test_mandatory_safety_rules_cannot_be_weakened(self) -> None:
        for rule_id, changes in [
            ("NER-001", {"severity": "S1", "action": "warning"}),
            ("NER-002", {"severity": "S0", "action": "informational"}),
            ("NER-003", {"severity": "S1", "action": "warning"}),
            ("NER-004", {"severity": "S1", "action": "warning"}),
            ("NER-005", {"severity": "S1", "action": "warning"}),
            ("NER-006", {"severity": "S1", "action": "warning"}),
        ]:
            candidate = copy.deepcopy(self.policy)
            next(item for item in candidate["rules"] if item["rule_id"] == rule_id).update(changes)
            with self.subTest(rule_id=rule_id), self.assertRaises(ContractError):
                validate_policy(candidate)

        live = copy.deepcopy(
            next(item for item in self.vectors if item["vector_id"] == "TV-002-UNRESOLVED-LIVE")
        )
        self.assertEqual("paper_only", evaluate(self.policy, live)["action"])
        for vector_id in [
            "TV-004-SOCIAL-PROHIBITED",
            "TV-005-SOCIAL-PROHIBITED",
            "TV-006-SOCIAL-PROHIBITED",
        ]:
            vector = next(item for item in self.vectors if item["vector_id"] == vector_id)
            result = evaluate(self.policy, vector)
            self.assertEqual("none", result["direction_effect"])
            self.assertLessEqual(result["confidence_delta_max"], 0)
            self.assertLessEqual(result["size_multiplier_max"], 1)


if __name__ == "__main__":
    unittest.main()
