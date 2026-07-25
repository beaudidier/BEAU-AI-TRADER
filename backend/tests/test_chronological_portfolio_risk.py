from __future__ import annotations

import unittest

from backtesting.portfolio_risk import (
    PortfolioRiskLimits,
    build_portfolio_events,
    calculate_chronological_portfolio,
)


def _trade(
    trade_id: str,
    ticker: str,
    entry_date: str,
    exit_legs: list[dict],
    *,
    sector: str = "Technology",
) -> dict:
    return {
        "trade_id": trade_id,
        "ticker": ticker,
        "sector": sector,
        "entry_date": entry_date,
        "exit_date": exit_legs[-1]["exit_date"],
        "shares": 100,
        "r_multiple": sum(leg["r_multiple"] for leg in exit_legs),
        "exit_legs": exit_legs,
    }


class ChronologicalPortfolioRiskTests(unittest.TestCase):
    def setUp(self):
        self.partial = _trade(
            "A-1",
            "ZZZ",
            "2024-01-02",
            [
                {
                    "leg": "TP1",
                    "shares": 50,
                    "exit_date": "2024-01-04",
                    "r_multiple": 1.0,
                    "allocated_entry_cost": 0.05,
                    "exit_transaction_cost": 0.05,
                },
                {
                    "leg": "STOP",
                    "shares": 50,
                    "exit_date": "2024-01-08",
                    "r_multiple": -0.5,
                    "allocated_entry_cost": 0.05,
                    "exit_transaction_cost": 0.05,
                },
            ],
        )
        self.overlap = _trade(
            "B-1",
            "AAA",
            "2024-01-03",
            [{
                "leg": "STOP",
                "shares": 100,
                "exit_date": "2024-01-04",
                "r_multiple": -1.0,
            }],
            sector="Utilities",
        )

    def test_events_are_chronological_with_explicit_priority(self):
        events = build_portfolio_events([self.overlap, self.partial])
        ordering = [
            (event["timestamp"].date().isoformat(), event["event_type"])
            for event in events
        ]
        self.assertEqual(ordering, [
            ("2024-01-02", "entry"),
            ("2024-01-03", "entry"),
            ("2024-01-04", "partial_exit"),
            ("2024-01-04", "final_exit"),
            ("2024-01-08", "final_exit"),
        ])

    def test_overlapping_positions_and_partial_risk_are_tracked(self):
        result = calculate_chronological_portfolio(
            [self.partial, self.overlap]
        )
        self.assertEqual(result["maximum_concurrent_positions"], 2)
        self.assertEqual(result["maximum_total_open_risk_r"], 2.0)
        jan_four = next(
            row for row in result["concurrent_exposure"]
            if row["date"] == "2024-01-04"
        )
        self.assertEqual(jan_four["open_positions"], 1)
        self.assertEqual(jan_four["open_risk_r"], 0.5)
        self.assertEqual(result["cumulative_r"], -0.5)

    def test_same_day_exit_legs_are_aggregated_without_ticker_order(self):
        forward = calculate_chronological_portfolio(
            [self.partial, self.overlap]
        )
        reverse = calculate_chronological_portfolio(
            [self.overlap, self.partial]
        )
        self.assertEqual(forward, reverse)
        jan_four = next(
            row for row in forward["daily_pnl"]
            if row["date"] == "2024-01-04"
        )
        self.assertEqual(jan_four["realized_r"], 0.0)
        self.assertEqual(jan_four["gross_loss_r"], -1.0)

    def test_deterministic_equity_curve_and_drawdown(self):
        first = calculate_chronological_portfolio(
            [self.partial, self.overlap]
        )
        second = calculate_chronological_portfolio(
            [self.partial, self.overlap]
        )
        self.assertEqual(first["equity_curve"], second["equity_curve"])
        self.assertEqual(first["maximum_drawdown_r"], -0.5)
        self.assertEqual(
            first["worst_trading_day"],
            {"date": "2024-01-08", "realized_r": -0.5},
        )

    def test_same_day_entries_are_counted_before_exits(self):
        first = _trade(
            "A",
            "AAA",
            "2024-02-01",
            [{
                "leg": "STOP",
                "shares": 100,
                "exit_date": "2024-02-01",
                "r_multiple": -1.0,
            }],
        )
        second = _trade(
            "B",
            "BBB",
            "2024-02-01",
            [{
                "leg": "TP2",
                "shares": 100,
                "exit_date": "2024-02-01",
                "r_multiple": 2.0,
            }],
        )
        result = calculate_chronological_portfolio([second, first])
        self.assertEqual(result["maximum_concurrent_positions"], 2)
        self.assertEqual(result["maximum_daily_new_risk_r"], 2.0)
        self.assertEqual(result["cumulative_r"], 1.0)

    def test_constraints_are_analysis_only(self):
        result = calculate_chronological_portfolio(
            [self.partial, self.overlap],
            limits=PortfolioRiskLimits(
                maximum_total_open_risk_r=1,
                maximum_concurrent_positions=1,
                maximum_daily_new_risk_r=0.5,
            ),
        )
        constraints = result["analysis_only_constraints"]
        self.assertFalse(constraints["enforced"])
        self.assertGreater(
            constraints["violations"]["total_open_risk_days"], 0
        )
        self.assertGreater(
            constraints["violations"]["concurrent_position_days"], 0
        )
        self.assertGreater(
            constraints["violations"]["daily_new_risk_days"], 0
        )


if __name__ == "__main__":
    unittest.main()
