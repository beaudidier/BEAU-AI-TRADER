#!/usr/bin/env python3
"""Deterministic adversarial tests for the research guardrail contract."""

from __future__ import annotations

import copy
import hashlib
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_contract
from generate_contract import OUT, build_contract, canonical_json
from validate_contract import primary_reason


CORPUS = json.loads((OUT / "mutation_corpus.json").read_text(encoding="utf-8"))


def descend(document: object, path: list[object]) -> tuple[object, object]:
    if not path:
        raise ValueError("root has no parent")
    current = document
    for part in path[:-1]:
        current = current[part]  # type: ignore[index]
    return current, path[-1]


def mutate(document: object, fixture: dict) -> object:
    changed = copy.deepcopy(document)
    operation = fixture["operation"]
    if operation == "null_root":
        return None
    parent, key = descend(changed, fixture["path"])
    if operation in {"set", "add"}:
        parent[key] = fixture["value"]  # type: ignore[index]
    elif operation == "delete":
        del parent[key]  # type: ignore[index]
    elif operation == "delete_index":
        del parent[key][fixture["value"]]  # type: ignore[index]
    elif operation == "duplicate_index":
        parent[key].append(copy.deepcopy(parent[key][fixture["value"]]))  # type: ignore[index]
    else:
        raise ValueError(f"unknown corpus operation: {operation}")
    return changed


class AdversarialContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads((OUT / "policy.json").read_text(encoding="utf-8"))
        cls.vectors = json.loads((OUT / "testvectors.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))

    def assert_fixture_rejected(self, fixture: dict) -> None:
        artifacts = {
            "policy": copy.deepcopy(self.policy),
            "vectors": copy.deepcopy(self.vectors),
            "manifest": copy.deepcopy(self.manifest),
        }
        artifacts[fixture["artifact"]] = mutate(
            artifacts[fixture["artifact"]], fixture
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "policy.json").write_text(
                canonical_json(artifacts["policy"]), encoding="utf-8"
            )
            (target / "testvectors.json").write_text(
                canonical_json(artifacts["vectors"]), encoding="utf-8"
            )
            (target / "manifest.json").write_text(
                canonical_json(artifacts["manifest"]), encoding="utf-8"
            )
            with patch.object(validate_contract, "OUT", target):
                with self.assertRaises(
                    (
                        ValueError, TypeError, KeyError, AttributeError, IndexError,
                        StopIteration,
                    )
                ):
                    validate_contract.validate()

    def test_fixed_mutation_corpus_fails_closed(self) -> None:
        self.assertEqual(len(CORPUS["mutations"]), 30)
        for fixture in CORPUS["mutations"]:
            with self.subTest(mutation_id=fixture["id"]):
                self.assert_fixture_rejected(fixture)

    def test_truncated_and_malformed_json_are_rejected(self) -> None:
        payloads = ["", "{", "[]", "null", "true", '"string"', "123"]
        for index, payload in enumerate(payloads):
            with self.subTest(payload=index):
                with tempfile.TemporaryDirectory() as directory:
                    target = Path(directory)
                    (target / "policy.json").write_text(payload, encoding="utf-8")
                    (target / "testvectors.json").write_text(
                        canonical_json(self.vectors), encoding="utf-8"
                    )
                    (target / "manifest.json").write_text(
                        canonical_json(self.manifest), encoding="utf-8"
                    )
                    with patch.object(validate_contract, "OUT", target):
                        with self.assertRaises(Exception):
                            validate_contract.validate()

    def test_priority_property_across_random_input_order(self) -> None:
        policy = build_contract()
        priorities = {r["reason_code"]: r["priority"] for r in policy["rules"]}
        codes = sorted(priorities)
        rng = random.Random(20260728)
        for sample_size in range(1, 20):
            selected = rng.sample(codes, sample_size)
            expected = primary_reason(selected, priorities)
            for _ in range(25):
                rng.shuffle(selected)
                self.assertEqual(primary_reason(selected, priorities), expected)

    def test_priority_property_ignores_duplicates(self) -> None:
        policy = build_contract()
        priorities = {r["reason_code"]: r["priority"] for r in policy["rules"]}
        active = ["SPREAD_MAX", "QUOTE_STALE", "SPREAD_MAX", "QUOTE_STALE"]
        self.assertEqual(
            primary_reason(active, priorities),
            primary_reason(["QUOTE_STALE", "SPREAD_MAX"], priorities),
        )

    def test_object_key_order_does_not_change_hash(self) -> None:
        text_a = canonical_json(self.policy)
        reversed_root = dict(reversed(list(self.policy.items())))
        text_b = canonical_json(reversed_root)
        self.assertEqual(text_a, text_b)
        self.assertEqual(
            hashlib.sha256(text_a.encode()).hexdigest(),
            hashlib.sha256(text_b.encode()).hexdigest(),
        )

    def test_canonical_artifact_hashes_are_unchanged(self) -> None:
        self.assertEqual(
            hashlib.sha256(canonical_json(self.policy).encode()).hexdigest(),
            self.manifest["contract_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(canonical_json(self.vectors).encode()).hexdigest(),
            self.manifest["testvectors_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
