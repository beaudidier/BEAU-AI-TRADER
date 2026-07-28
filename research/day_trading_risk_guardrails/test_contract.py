#!/usr/bin/env python3
"""Deterministic unit checks for the standalone research contract."""

from __future__ import annotations

import json
import unittest

from generate_contract import MODES, OUT, build_contract, build_vectors, triggers
from validate_contract import primary_reason, validate


class ContractTests(unittest.TestCase):
    def test_generated_contract_is_valid(self) -> None:
        policy, vectors, results = validate()
        self.assertEqual(len(policy["rules"]), 62)
        self.assertEqual(len(vectors["vectors"]), len(results))

    def test_maximum_allows_equality(self) -> None:
        self.assertFalse(triggers("max", 100, 100))
        self.assertTrue(triggers("max", 101, 100))

    def test_minimum_allows_equality(self) -> None:
        self.assertFalse(triggers("min", 100, 100))
        self.assertTrue(triggers("min", 99, 100))

    def test_tripwire_blocks_equality(self) -> None:
        self.assertFalse(triggers("tripwire", 99, 100))
        self.assertTrue(triggers("tripwire", 100, 100))

    def test_priority_is_order_independent(self) -> None:
        policy = build_contract()
        priorities = {r["reason_code"]: r["priority"] for r in policy["rules"]}
        first_a, all_a = primary_reason(
            ["SPREAD_MAX", "DAILY_LOSS_MAX", "KILL_SWITCH_ACTIVE"], priorities
        )
        first_b, all_b = primary_reason(
            ["KILL_SWITCH_ACTIVE", "SPREAD_MAX", "DAILY_LOSS_MAX"], priorities
        )
        self.assertEqual((first_a, all_a), (first_b, all_b))

    def test_every_rule_has_vectors(self) -> None:
        policy = build_contract()
        vectors = build_vectors(policy)["vectors"]
        covered = {v.get("reason_code") for v in vectors}
        self.assertEqual(
            {r["reason_code"] for r in policy["rules"]}, covered - {None}
        )

    def test_unknown_input_fails_closed(self) -> None:
        vectors = build_vectors(build_contract())["vectors"]
        missing = [v for v in vectors if v["kind"] == "fail_closed"]
        self.assertEqual(len(missing), 62)
        self.assertTrue(
            all(v["expected"]["primary_reason"] == "RISK_STATE_UNAVAILABLE" for v in missing)
        )

    def test_future_live_is_hard_disabled_and_unresolved(self) -> None:
        policy = build_contract()
        self.assertEqual(policy["live_execution"], "HARD_DISABLED")
        unresolved = [
            rule for rule in policy["rules"]
            if rule["future_live_status"] == "UNRESOLVED_FAIL_CLOSED"
        ]
        self.assertGreaterEqual(len(unresolved), 5)
        self.assertTrue(all(rule["unresolved_dependencies"] for rule in unresolved))

    def test_policy_artifact_is_order_canonical(self) -> None:
        policy = json.loads((OUT / "policy.json").read_text(encoding="utf-8"))
        priorities = [r["priority"] for r in policy["rules"]]
        self.assertEqual(priorities, list(range(1, len(priorities) + 1)))

    def test_integer_numeric_limits_only(self) -> None:
        for limits in MODES.values():
            for key, value in limits.items():
                if key.endswith(("_ppm", "_cents", "_micros", "_ms")) or key in {
                    "consecutive_losses", "position_count", "bid_ask_size_shares"
                }:
                    self.assertIs(type(value), int)
                    self.assertGreaterEqual(value, 0)


if __name__ == "__main__":
    unittest.main()
