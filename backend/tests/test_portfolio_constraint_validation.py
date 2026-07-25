import copy
import unittest

import numpy as np

from calibration.portfolio_constraint_validation import (
    ConstraintConfiguration,
    _bootstrap_expectancy,
    apply_constraints,
    configurations,
    position_risk_percentage,
    rank_daily_signals,
)


def _trade(
    trade_id,
    ticker,
    sector,
    entry_date,
    exit_date,
    confidence,
    risk_percent,
    r_multiple=1.0,
    partial_date=None,
):
    entry = 100.0
    stop = entry * (1 - risk_percent / 100)
    legs = []
    if partial_date:
        legs.append(
            {
                "leg": "TP1",
                "shares": 50,
                "exit_date": partial_date,
                "r_multiple": 1.0,
            }
        )
    legs.append(
        {
            "leg": "FINAL",
            "shares": 50 if partial_date else 100,
            "exit_date": exit_date,
            "r_multiple": r_multiple - (1.0 if partial_date else 0.0),
        }
    )
    return {
        "trade_id": trade_id,
        "ticker": ticker,
        "sector": sector,
        "signal_date": entry_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": entry,
        "stop_loss": stop,
        "target_1": entry + 2 * (entry - stop),
        "target_2": entry + 4 * (entry - stop),
        "confidence": confidence,
        "shares": 100,
        "r_multiple": r_multiple,
        "exit_legs": legs,
    }


class PortfolioConstraintValidationTests(unittest.TestCase):
    def test_all_256_configurations_are_unique(self):
        rows = list(configurations())
        self.assertEqual(len(rows), 256)
        self.assertEqual(len({row.id for row in rows}), 256)

    def test_bootstrap_is_deterministic(self):
        values = np.asarray([-1.0, 0.5, 2.0, 1.0], dtype=float)
        self.assertEqual(
            _bootstrap_expectancy(values, 12),
            _bootstrap_expectancy(values, 12),
        )

    def test_highest_confidence_is_deterministic(self):
        rows = [
            _trade("b", "BBB", "Tech", "2024-01-02", "2024-01-05", 80, 4),
            _trade("a", "AAA", "Health", "2024-01-02", "2024-01-05", 90, 4),
        ]
        ranked = rank_daily_signals(rows, "highest_confidence")
        self.assertEqual([row["ticker"] for row in ranked], ["AAA", "BBB"])

    def test_lowest_risk_percentage_ranks_first(self):
        rows = [
            _trade("a", "AAA", "Tech", "2024-01-02", "2024-01-05", 90, 4),
            _trade("b", "BBB", "Health", "2024-01-02", "2024-01-05", 80, 2),
        ]
        ranked = rank_daily_signals(rows, "lowest_risk_percentage")
        self.assertEqual([row["ticker"] for row in ranked], ["BBB", "AAA"])
        self.assertAlmostEqual(position_risk_percentage(ranked[0]), 2.0)

    def test_sector_ranking_considers_each_sector_before_second_pick(self):
        rows = [
            _trade("a", "AAA", "Tech", "2024-01-02", "2024-01-05", 95, 4),
            _trade("b", "BBB", "Tech", "2024-01-02", "2024-01-05", 94, 4),
            _trade("c", "CCC", "Health", "2024-01-02", "2024-01-05", 80, 4),
        ]
        ranked = rank_daily_signals(
            rows, "one_highest_ranked_per_sector"
        )
        self.assertEqual([row["ticker"] for row in ranked], ["AAA", "CCC", "BBB"])

    def test_daily_new_risk_limit_selects_ranked_signal(self):
        rows = [
            _trade("a", "AAA", "Tech", "2024-01-02", "2024-01-05", 80, 4),
            _trade("b", "BBB", "Health", "2024-01-02", "2024-01-05", 90, 4),
        ]
        config = ConstraintConfiguration(10, 10, 1, "highest_confidence")
        accepted, rejected = apply_constraints(rows, config)
        self.assertEqual([row["ticker"] for row in accepted], ["BBB"])
        self.assertEqual(len(rejected), 1)
        self.assertIn(
            "maximum_daily_new_risk",
            rejected[0]["portfolio_rejection_reasons"],
        )

    def test_partial_exit_releases_open_risk_for_later_entry(self):
        rows = [
            _trade(
                "a",
                "AAA",
                "Tech",
                "2024-01-02",
                "2024-01-10",
                90,
                4,
                partial_date="2024-01-03",
            ),
            _trade("b", "BBB", "Health", "2024-01-04", "2024-01-08", 80, 4),
        ]
        config = ConstraintConfiguration(2, 1.5, 2, "highest_confidence")
        accepted, rejected = apply_constraints(rows, config)
        self.assertEqual(len(accepted), 2)
        self.assertEqual(rejected, [])

    def test_same_day_entry_precedes_exit(self):
        rows = [
            _trade("a", "AAA", "Tech", "2024-01-02", "2024-01-04", 90, 4),
            _trade("b", "BBB", "Health", "2024-01-04", "2024-01-08", 80, 4),
        ]
        config = ConstraintConfiguration(1, 1, 2, "highest_confidence")
        accepted, rejected = apply_constraints(rows, config)
        self.assertEqual([row["ticker"] for row in accepted], ["AAA"])
        self.assertEqual([row["ticker"] for row in rejected], ["BBB"])

    def test_input_order_does_not_change_admission(self):
        rows = [
            _trade("a", "AAA", "Tech", "2024-01-02", "2024-01-05", 80, 4),
            _trade("b", "BBB", "Health", "2024-01-02", "2024-01-05", 90, 4),
            _trade("c", "CCC", "Energy", "2024-01-03", "2024-01-06", 85, 4),
        ]
        config = ConstraintConfiguration(2, 2, 1, "highest_confidence")
        first = apply_constraints(copy.deepcopy(rows), config)
        second = apply_constraints(list(reversed(copy.deepcopy(rows))), config)
        self.assertEqual(
            [row["trade_id"] for row in first[0]],
            [row["trade_id"] for row in second[0]],
        )
        self.assertEqual(
            [row["trade_id"] for row in first[1]],
            [row["trade_id"] for row in second[1]],
        )

    def test_duplicate_trade_ids_are_rejected(self):
        rows = [
            _trade("same", "AAA", "Tech", "2024-01-02", "2024-01-05", 80, 4),
            _trade("same", "BBB", "Health", "2024-01-02", "2024-01-05", 90, 4),
        ]
        config = ConstraintConfiguration(10, 10, 1, "highest_confidence")
        with self.assertRaisesRegex(ValueError, "duplicate trade IDs"):
            apply_constraints(rows, config)


if __name__ == "__main__":
    unittest.main()
