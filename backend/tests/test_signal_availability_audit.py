from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd

from forward_validation.signal_availability_audit import (
    SESSION_COUNT,
    _clean_history,
    _risk_limit_analysis,
    run_signal_availability_audit,
)


def _history(rows: int = 280, *, low: float = 99.0) -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-07-24", periods=rows)
    return pd.DataFrame(
        {
            "Open": [100.0] * rows,
            "High": [101.0] * rows,
            "Low": [low] * rows,
            "Close": [100.0] * rows,
            "Volume": [1_000_000] * rows,
        },
        index=dates,
    )


def _analysis(regime_score: int = 70) -> dict:
    return {
        "overall_score": 82,
        "engines": {
            "market_regime": {
                "score": regime_score,
                "explanation": "Risk-on" if regime_score >= 65 else "Defensive",
            }
        },
    }


class SignalAvailabilityAuditTests(unittest.TestCase):
    def test_duplicate_ohlcv_columns_are_rejected(self):
        history = _history()
        duplicated = pd.concat([history, history], axis=1)
        self.assertTrue(duplicated.columns.duplicated().any())
        self.assertIsNone(_clean_history(duplicated))

    @patch(
        "forward_validation.production_replay.calculate_institutional_analysis",
        return_value=_analysis(),
    )
    @patch(
        "strategies.swing_strategy.calculate_institutional_analysis",
        return_value=_analysis(),
    )
    def test_audit_uses_exact_strategy_and_verifies_risk_formula(
        self, _production_analysis, _standalone_analysis
    ):
        history = _history()
        sessions = list(history.index[-SESSION_COUNT:])
        result = run_signal_availability_audit(
            {"SPY": history, "AAA": history},
            sessions,
            universes={"demo": ["AAA"]},
            generated_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        )
        demo = result["universes"]["demo"]
        self.assertEqual(demo["valid_signals"], SESSION_COUNT)
        self.assertEqual(demo["days_with_zero_signals"], 0)
        self.assertEqual(
            result["calculation_verification"]["production_standalone_mismatches"],
            [],
        )
        self.assertLess(
            result["calculation_verification"][
                "maximum_formula_error_percentage_points"
            ],
            0.0001,
        )
        self.assertFalse(
            result["calculation_verification"]["calculation_bug_found"]
        )
        self.assertTrue(result["diagnosis"]["risk_rule_functioning_as_intended"])

    @patch(
        "forward_validation.production_replay.calculate_institutional_analysis",
        return_value=_analysis(),
    )
    @patch(
        "strategies.swing_strategy.calculate_institutional_analysis",
        return_value=_analysis(),
    )
    def test_wide_stop_is_rejected_and_counted(self, _production_analysis, _standalone_analysis):
        history = _history(low=85.0)
        sessions = list(history.index[-SESSION_COUNT:])
        result = run_signal_availability_audit(
            {"SPY": history, "AAA": history},
            sessions,
            universes={"demo": ["AAA"]},
        )
        demo = result["universes"]["demo"]
        self.assertEqual(demo["valid_signals"], 0)
        self.assertEqual(demo["rejected_signals"], SESSION_COUNT)
        self.assertEqual(
            demo["rejection_reasons"]["risk_above_5_percent"], SESSION_COUNT
        )
        self.assertEqual(
            demo["risk_limit_analysis"]["above_10_percent"], SESSION_COUNT
        )

    @patch(
        "forward_validation.production_replay.calculate_institutional_analysis",
        return_value=_analysis(40),
    )
    @patch(
        "strategies.swing_strategy.calculate_institutional_analysis",
        return_value=_analysis(40),
    )
    def test_regime_rejections_and_provider_failures_are_separate(
        self, _production_analysis, _standalone_analysis
    ):
        history = _history()
        sessions = list(history.index[-SESSION_COUNT:])
        result = run_signal_availability_audit(
            {"SPY": history, "AAA": history},
            sessions,
            universes={"demo": ["AAA", "MISSING"]},
        )
        demo = result["universes"]["demo"]
        self.assertEqual(
            demo["rejection_reasons"]["market_regime_below_65"], SESSION_COUNT
        )
        self.assertEqual(demo["provider_failures"], SESSION_COUNT)
        self.assertEqual(demo["daily"][0]["provider_failures"], 1)

    def test_risk_buckets_are_exact_and_sector_dominance_is_explicit(self):
        observations = [
            {
                "ticker": "AAPL",
                "status": "rejected",
                "reasons": ["risk_above_5_percent"],
                "risk_percent": risk,
                "distance_to_swing_low_percent": risk - 1,
                "atr_buffer_percent": 1,
                "atr_percent": 2,
                "market_regime": "Risk-on",
            }
            for risk in (5.01, 7.5, 7.51, 10.0, 10.01)
        ]
        analysis = _risk_limit_analysis(observations)
        self.assertEqual(analysis["only_slightly_above_5_to_7_5_percent"], 2)
        self.assertEqual(analysis["above_7_5_percent"], 3)
        self.assertEqual(analysis["above_10_percent"], 1)
        self.assertTrue(analysis["sector_dominance_detected"])


if __name__ == "__main__":
    unittest.main()
