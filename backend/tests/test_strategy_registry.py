from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

import api
from forward_validation.engine import build_live_signal as legacy_build_live_signal
from strategies import StrategyNotFoundError, StrategyUnavailableError, strategy_registry
from strategies.base_strategy import StrategyStatus
from strategies.swing_strategy import STRATEGY_VERSION, build_live_signal, swing_trading_strategy


def _history(rows: int = 220) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0] * rows,
            "High": [101.0] * rows,
            "Low": [99.0] * rows,
            "Close": [100.0] * rows,
            "Volume": [1_000_000] * rows,
        },
        index=dates,
    )


class StrategyRegistryTests(unittest.TestCase):
    def test_registry_lists_every_strategy_and_status(self):
        strategies = strategy_registry.serialize()
        self.assertEqual(
            [strategy["id"] for strategy in strategies],
            ["day_trading", "swing_trading", "long_term", "crypto"],
        )
        self.assertEqual(
            {strategy["status"] for strategy in strategies},
            {StrategyStatus.FORWARD_VALIDATION.value, StrategyStatus.COMING_SOON.value},
        )
        self.assertEqual(len(api.list_strategies()), 4)

    def test_valid_swing_selection_is_usable(self):
        selected = strategy_registry.require_usable("swing_trading")
        self.assertIs(selected, swing_trading_strategy)
        self.assertEqual(selected.status, StrategyStatus.FORWARD_VALIDATION)

    def test_invalid_strategy_is_rejected(self):
        with self.assertRaises(StrategyNotFoundError):
            strategy_registry.require_usable("unknown")
        with self.assertRaises(HTTPException) as error:
            api.scan(market="stocks", universe="demo", strategy="unknown")
        self.assertEqual(error.exception.status_code, 404)

    def test_inactive_strategy_cannot_produce_recommendations(self):
        for strategy_id in ("day_trading", "long_term", "crypto"):
            with self.subTest(strategy_id=strategy_id):
                strategy = strategy_registry.require(strategy_id)
                with self.assertRaises(StrategyUnavailableError):
                    strategy.scan()
                with self.assertRaises(HTTPException) as error:
                    api.scan(market="stocks", universe="demo", strategy=strategy_id)
                self.assertEqual(error.exception.status_code, 409)
                self.assertEqual(error.exception.detail, "Coming soon. This engine is not yet validated.")

    @patch.object(api, "WATCHLIST", [])
    def test_swing_scan_selection_preserves_existing_scan_results(self):
        self.assertEqual(
            api.scan(market="stocks", universe="demo", strategy=None),
            api.scan(market="stocks", universe="demo", strategy="swing_trading"),
        )

    @patch("strategies.swing_strategy.calculate_institutional_analysis")
    def test_existing_frozen_swing_signal_is_unchanged(self, analysis):
        analysis.return_value = {
            "overall_score": 82,
            "engines": {"market_regime": {"score": 65, "explanation": "Risk-on"}},
        }
        history = _history()
        timestamp = "2026-01-01T00:00:00+00:00"

        legacy = legacy_build_live_signal("test", history, history, signal_timestamp=timestamp)
        moved = build_live_signal("test", history, history, signal_timestamp=timestamp)
        selected = swing_trading_strategy.scan(
            ticker="test",
            history=history,
            benchmark=history,
            signal_timestamp=timestamp,
        )

        self.assertEqual(legacy, moved)
        self.assertEqual(moved, selected)
        self.assertEqual(moved["strategy_version"], STRATEGY_VERSION)
        self.assertEqual(moved["expected_entry_fill"], 100.05)
        self.assertEqual(moved["stop_loss"], 96.0)
        self.assertEqual(moved["target_1"], 108.15)
        self.assertEqual(moved["target_2"], 116.25)


if __name__ == "__main__":
    unittest.main()
