import unittest

import pandas as pd

from engines.trade_plan_engine import calculate_trade_plan


def _prices(close=100):
    return pd.DataFrame({"Close": [close]})


class ExecutableEntryTradePlanTests(unittest.TestCase):
    def plan(self, *, entry, support=90, resistance=125, atr=5, account_size=10_000):
        return calculate_trade_plan("TEST", _prices(), account_size, 1, {"confidence": 80}, support, resistance, atr, executable_entry=entry)

    def test_normal_next_open_fill_recalculates_levels(self):
        plan = self.plan(entry=95)
        self.assertTrue(plan["trade_allowed"])
        self.assertEqual(plan["proposed_executable_entry"], 95)
        self.assertLess(plan["stop_loss"], plan["entry"])
        self.assertGreater(plan["target_1"], plan["entry"])

    def test_gap_above_original_target_is_rejected(self):
        plan = self.plan(entry=126)
        self.assertFalse(plan["trade_allowed"])
        self.assertTrue(any("original Target 1" in reason for reason in plan["rejection_reasons"]))

    def test_gap_with_rr_below_minimum_is_rejected(self):
        plan = self.plan(entry=105, resistance=110)
        self.assertFalse(plan["trade_allowed"])
        self.assertLess(plan["risk_reward_target_1"], 1.5)
        self.assertTrue(any("risk/reward" in reason for reason in plan["rejection_reasons"]))

    def test_invalid_stop_after_gap_is_rejected_by_validation(self):
        with self.assertRaises(ValueError):
            self.plan(entry=10, support=20, resistance=50, atr=10)

    def test_valid_gap_recalculates_position_size(self):
        base = self.plan(entry=95)
        gap = self.plan(entry=96)
        self.assertNotEqual(base["risk_per_share"], gap["risk_per_share"])
        self.assertNotEqual(base["position_size"], gap["position_size"])


if __name__ == "__main__":
    unittest.main()
