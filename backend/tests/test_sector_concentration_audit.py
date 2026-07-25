import json
import unittest
from copy import deepcopy

import numpy as np

from calibration.sector_concentration_audit import (
    LOCKED_RESULTS_PATH,
    _cap_allows,
    _maximum_drawdown,
    _paired_block_comparison,
    _simple_metrics,
    apply_variant,
    load_validated_ledger,
)


def _trade(
    trade_id: str,
    *,
    ticker: str,
    sector: str,
    signal_date: str = "2020-01-02",
    entry_date: str = "2020-01-03",
    exit_date: str = "2020-01-10",
    confidence: float = 80,
    r_multiple: float = 1,
) -> dict:
    return {
        "trade_id": trade_id,
        "ticker": ticker,
        "sector": sector,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "confidence": confidence,
        "r_multiple": r_multiple,
        "market_regime": "Bull",
    }


class SectorConcentrationAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = load_validated_ledger()
        cls.locked = json.loads(
            LOCKED_RESULTS_PATH.read_text(encoding="utf-8")
        )["selected_regime_gated_pullback"]

    def test_no_limit_reproduces_locked_point_metrics(self):
        metrics = _simple_metrics(self.ledger)
        self.assertEqual(len(self.ledger), self.locked["accepted_trades"])
        self.assertEqual(metrics["expectancy"], self.locked["expectancy"])
        self.assertEqual(
            metrics["profit_factor"], self.locked["profit_factor"]
        )
        self.assertEqual(metrics["win_rate"], self.locked["win_rate"])
        self.assertEqual(metrics["average_r"], self.locked["average_r"])
        self.assertEqual(len({row["trade_id"] for row in self.ledger}), 835)

    def test_drawdown_uses_chronological_realised_order(self):
        metrics = _simple_metrics(self.ledger)
        self.assertEqual(metrics["maximum_drawdown"], -29.4789)
        self.assertNotEqual(
            metrics["maximum_drawdown"], self.locked["maximum_drawdown"]
        )
        self.assertEqual(_maximum_drawdown(np.array([1.0, -2.0, 0.5])), -2.0)

    def test_cap_bootstraps_only_through_diversification(self):
        technology = _trade("t1", ticker="AAA", sector="Technology")
        technology_two = _trade("t2", ticker="BBB", sector="Technology")
        utility = _trade("t3", ticker="CCC", sector="Utilities")
        self.assertTrue(_cap_allows([], technology, limit=0.30))
        self.assertFalse(
            _cap_allows([technology], technology_two, limit=0.30)
        )
        self.assertTrue(_cap_allows([technology], utility, limit=0.30))

    def test_highest_confidence_selection_is_deterministic(self):
        lower = _trade(
            "low",
            ticker="BBB",
            sector="Technology",
            confidence=80,
        )
        higher = _trade(
            "high",
            ticker="AAA",
            sector="Technology",
            confidence=90,
        )
        equal_but_later_ticker = _trade(
            "tie",
            ticker="ZZZ",
            sector="Technology",
            confidence=90,
        )
        selected, rejected = apply_variant(
            [lower, equal_but_later_ticker, higher],
            "E_highest_confidence_per_sector_day",
        )
        self.assertEqual([row["trade_id"] for row in selected], ["high"])
        self.assertEqual(
            {row["trade_id"] for row in rejected}, {"low", "tie"}
        )

    def test_related_sector_cap_treats_utilities_and_real_estate_together(self):
        trades = [
            _trade("u1", ticker="AAA", sector="Utilities"),
            _trade("t1", ticker="BBB", sector="Technology"),
            _trade("r1", ticker="CCC", sector="Real Estate"),
        ]
        selected, rejected = apply_variant(
            deepcopy(trades), "D_max_50_rate_sensitive"
        )
        self.assertEqual([row["trade_id"] for row in selected], ["u1", "t1"])
        self.assertEqual([row["trade_id"] for row in rejected], ["r1"])

    def test_paired_bootstrap_is_deterministic(self):
        baseline = [
            _trade(
                f"t{index}",
                ticker=f"T{index}",
                sector="Technology" if index % 2 else "Utilities",
                exit_date=f"2020-01-{index + 2:02d}",
                r_multiple=float(value),
            )
            for index, value in enumerate([1, -1, 2, -0.5, 0.5, -1, 1, 2])
        ]
        accepted = baseline[::2]
        first = _paired_block_comparison(baseline, accepted, 99)
        second = _paired_block_comparison(baseline, accepted, 99)
        self.assertEqual(first, second)
        self.assertEqual(len(first["expectancy_difference_95_ci"]), 2)
        self.assertEqual(
            len(first["maximum_drawdown_improvement_95_ci"]), 2
        )


if __name__ == "__main__":
    unittest.main()
