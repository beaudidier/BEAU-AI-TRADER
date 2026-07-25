"""Focused deterministic checks for the isolated trade-plan experiment."""

from __future__ import annotations

import unittest

import pandas as pd

from calibration.trade_plan_variant_experiment import breakout_plan, next_open_atr_plan, pullback_plan


def _data(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"])


def _candidate(**overrides: float | int) -> dict:
    candidate = {"index": 0, "atr": 2.0, "ema20": 100.0, "swing_low_20": 97.1, "signal_high": 102.0, "signal_low": 100.5}
    candidate.update(overrides)
    return candidate


class TradePlanVariantExperimentTests(unittest.TestCase):
    def test_next_open_uses_open_and_atr_stop(self) -> None:
        plan, reason = next_open_atr_plan(_candidate(), _data([(100, 101, 99, 100), (105, 106, 104, 105)]))
        self.assertIsNone(reason)
        self.assertAlmostEqual(plan["stop"], 102.0)
        self.assertGreater(plan["target_1"], plan["entry"])

    def test_pullback_waits_for_limit(self) -> None:
        data = _data([(100, 101, 99, 100), (104, 105, 102, 104), (102, 103, 99, 101), (101, 102, 99, 100)])
        plan, reason = pullback_plan(_candidate(), data)
        self.assertIsNone(reason)
        self.assertEqual(plan["entry_index"], 2)

    def test_pullback_rejects_excess_risk(self) -> None:
        data = _data([(100, 101, 99, 100), (101, 102, 99, 100), (101, 102, 99, 100), (101, 102, 99, 100)])
        plan, reason = pullback_plan(_candidate(swing_low_20=80.0), data)
        self.assertIsNone(plan)
        self.assertEqual(reason, "Position risk exceeds 5% of entry price")

    def test_breakout_uses_gap_open_when_triggered(self) -> None:
        data = _data([(100, 102, 98, 100), (105, 106, 103, 105), (100, 101, 99, 100), (100, 101, 99, 100)])
        plan, reason = breakout_plan(_candidate(), data)
        self.assertIsNone(reason)
        self.assertEqual(plan["entry_index"], 1)
        self.assertGreater(plan["entry"], 105.0)

    def test_breakout_rejects_unreached_trigger(self) -> None:
        data = _data([(100, 102, 98, 100), (100, 102, 99, 100), (100, 102, 99, 100), (100, 102, 99, 100)])
        plan, reason = breakout_plan(_candidate(), data)
        self.assertIsNone(plan)
        self.assertEqual(reason, "Breakout trigger was not reached within 3 candles")


if __name__ == "__main__":
    unittest.main()
