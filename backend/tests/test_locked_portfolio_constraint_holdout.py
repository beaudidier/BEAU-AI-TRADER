import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from calibration.locked_portfolio_constraint_holdout import (
    FROZEN_CONFIGURATION,
    _approval,
    _matched_random_entries,
    load_cached_candidates,
)


class LockedPortfolioConstraintHoldoutTests(unittest.TestCase):
    def test_frozen_configuration_is_exact(self):
        self.assertEqual(
            FROZEN_CONFIGURATION.maximum_concurrent_positions, 10
        )
        self.assertEqual(
            FROZEN_CONFIGURATION.maximum_total_open_risk_r, 10
        )
        self.assertEqual(
            FROZEN_CONFIGURATION.maximum_daily_new_risk_r, 1
        )
        self.assertEqual(
            FROZEN_CONFIGURATION.ranking_method, "highest_confidence"
        )

    def test_candidate_loader_deduplicates_partial_exit_rows(self):
        history = pd.DataFrame(
            {"Close": [10, 11]},
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )
        row = {
            "filter_id": "existing_market_regime",
            "cost_multiplier": "1",
            "ticker": "AAA",
            "signal_date": "2024-01-02",
            "sector": "Technology",
            "ema20": "10",
            "swing_low_20": "9",
            "atr": "0.5",
            "walk_forward_period": "Holdout",
            "spy_close_ema200": "True",
            "spy_ema50_ema200": "True",
            "spy_dual_ema": "True",
            "nasdaq_close_ema200": "True",
            "universe_breadth_60": "True",
            "existing_market_regime": "True",
            "out_of_sample": "True",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
                writer.writerow(row)
            result = load_cached_candidates({"AAA": history}, path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["index"], 0)

    def test_approval_passes_all_declared_checks(self):
        frozen = {
            "expectancy_r": 0.2,
            "profit_factor": 1.3,
            "maximum_drawdown_r": -10.0,
            "maximum_open_risk_r": 10.0,
            "maximum_concurrent_positions": 10,
            "bootstrap_expectancy_95_ci": [-0.01, 0.4],
        }
        unconstrained = {"maximum_drawdown_r": -20.0}
        doubled = {"expectancy_r": 0.1, "profit_factor": 1.1}
        self.assertTrue(
            _approval(frozen, unconstrained, doubled)["passed"]
        )

    def test_materially_negative_interval_fails(self):
        frozen = {
            "expectancy_r": 0.2,
            "profit_factor": 1.3,
            "maximum_drawdown_r": -10.0,
            "maximum_open_risk_r": 10.0,
            "maximum_concurrent_positions": 10,
            "bootstrap_expectancy_95_ci": [-0.051, 0.4],
        }
        result = _approval(
            frozen,
            {"maximum_drawdown_r": -20.0},
            {"expectancy_r": 0.1, "profit_factor": 1.1},
        )
        self.assertFalse(result["passed"])
        self.assertFalse(
            result["checks"][
                "expectancy_interval_not_materially_negative"
            ]
        )

    def test_random_baseline_is_deterministic(self):
        history = pd.DataFrame(
            {
                "Open": [100 + index for index in range(50)],
                "Close": [100.5 + index for index in range(50)],
            },
            index=pd.bdate_range("2024-01-02", periods=50),
        )
        trades = [{"ticker": "AAA", "holding_days": 5}] * 4
        first = _matched_random_entries(trades, {"AAA": history}, seed=7)
        second = _matched_random_entries(trades, {"AAA": history}, seed=7)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
