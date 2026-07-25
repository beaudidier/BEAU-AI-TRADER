from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from forward_validation.engine import STRATEGY_VERSION, build_dashboard, build_live_signal, evaluate_signal


def _history(rows: int = 220) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=rows, freq="D")
    return pd.DataFrame({"Open": [100.0] * rows, "High": [101.0] * rows, "Low": [99.0] * rows, "Close": [100.0] * rows, "Volume": [1_000_000] * rows}, index=dates)


def _signal(data_timestamp: str) -> dict:
    return {
        "id": "signal-1", "ticker": "TEST", "data_timestamp": data_timestamp,
        "proposed_pullback_entry": 100.0, "expected_entry_fill": 100.05,
        "stop_loss": 97.05, "target_1": 106.05, "target_2": 112.05,
    }


class ForwardValidationEngineTests(unittest.TestCase):
    @patch("strategies.swing_strategy.calculate_institutional_analysis")
    def test_builds_exact_frozen_signal_snapshot(self, analysis):
        analysis.return_value = {"overall_score": 82, "engines": {"market_regime": {"score": 65, "explanation": "Risk-on"}}}
        signal = build_live_signal("test", _history(), _history(), signal_timestamp="2026-01-01T00:00:00+00:00")
        self.assertEqual(signal["ticker"], "TEST")
        self.assertEqual(signal["strategy_version"], STRATEGY_VERSION)
        self.assertEqual(signal["confidence"], 82)
        self.assertGreater(signal["target_2"], signal["target_1"])

    @patch("strategies.swing_strategy.calculate_institutional_analysis")
    def test_rejects_defensive_market(self, analysis):
        analysis.return_value = {"overall_score": 82, "engines": {"market_regime": {"score": 35, "explanation": "Defensive"}}}
        self.assertIsNone(build_live_signal("TEST", _history(), _history()))

    def test_tracks_tp1_then_tp2_with_partial_exit(self):
        base = _history()
        first = base.index[-1] + pd.Timedelta(days=1)
        future = pd.DataFrame(
            {"Open": [100, 106], "High": [107, 113], "Low": [99, 100], "Close": [106, 112], "Volume": [1_000_000, 1_000_000]},
            index=[first, first + pd.Timedelta(days=1)],
        )
        result = evaluate_signal(_signal(base.index[-1].isoformat()), pd.concat([base, future]))
        self.assertEqual(result["status"], "TP2_hit")
        self.assertTrue(result["tp1_hit"])
        self.assertTrue(result["tp2_hit"])
        self.assertFalse(result["stop_hit"])
        self.assertGreater(result["realized_r"], 0)

    def test_stop_wins_same_candle_ambiguity(self):
        base = _history()
        first = base.index[-1] + pd.Timedelta(days=1)
        future = pd.DataFrame({"Open": [100], "High": [113], "Low": [96], "Close": [100], "Volume": [1_000_000]}, index=[first])
        result = evaluate_signal(_signal(base.index[-1].isoformat()), pd.concat([base, future]))
        self.assertEqual(result["status"], "stopped")
        self.assertTrue(result["stop_hit"])
        self.assertFalse(result["tp1_hit"])

    def test_tracks_open_tp1_state_and_excursions(self):
        base = _history()
        first = base.index[-1] + pd.Timedelta(days=1)
        future = pd.DataFrame({"Open": [100], "High": [107], "Low": [99], "Close": [106], "Volume": [1_000_000]}, index=[first])
        result = evaluate_signal(_signal(base.index[-1].isoformat()), pd.concat([base, future]))
        self.assertEqual(result["status"], "TP1_hit")
        self.assertTrue(result["tp1_hit"])
        self.assertFalse(result["tp2_hit"])
        self.assertEqual(result["remaining_fraction"], 0.5)
        self.assertGreater(result["mfe_r"], 0)
        self.assertLess(result["mae_r"], 0)

    def test_expires_after_three_unfilled_candles(self):
        base = _history()
        dates = pd.date_range(base.index[-1] + pd.Timedelta(days=1), periods=3)
        future = pd.DataFrame({"Open": [105] * 3, "High": [106] * 3, "Low": [104] * 3, "Close": [105] * 3, "Volume": [1_000_000] * 3}, index=dates)
        result = evaluate_signal(_signal(base.index[-1].isoformat()), pd.concat([base, future]))
        self.assertEqual(result["status"], "expired")
        self.assertIsNone(result["entry_price"])

    def test_approval_requires_one_hundred_completed_forward_trades(self):
        signals = [{"id": str(index), "ticker": "TEST", "signal_timestamp": str(index)} for index in range(100)]
        outcomes = [{"signal_id": str(index), "status": "completed", "realized_r": .25, "double_cost_realized_r": .1} for index in range(100)]
        dashboard = build_dashboard(signals, outcomes)
        self.assertEqual(dashboard["metrics"]["total_sample_size"], 100)
        self.assertTrue(dashboard["metrics"]["approval"]["approved"])


if __name__ == "__main__":
    unittest.main()
