import unittest
from datetime import datetime, timezone

from paper_trading.portfolio_risk import (
    admit_ranked_signals,
    build_portfolio_risk_dashboard,
    evaluate_admission,
)


NOW = datetime(2026, 7, 28, 15, 0, tzinfo=timezone.utc)
ACCOUNT = {"initial_balance": 10_000, "cash_balance": 8_000}


def trade(
    index: int,
    *,
    risk_r: float = 1.0,
    remaining: float = 1.0,
    status: str = "OPEN",
    admitted_at: str = "2026-07-27T15:00:00+00:00",
):
    return {
        "id": f"trade-{index}",
        "ticker": f"T{index}",
        "status": status,
        "initial_risk_r": risk_r,
        "remaining_risk_r": risk_r * remaining,
        "risk_admitted_at": admitted_at,
        "opened_at": admitted_at,
        "realized_pnl": 0,
    }


class PaperPortfolioRiskTests(unittest.TestCase):
    def dashboard(self, trades):
        return build_portfolio_risk_dashboard(
            ACCOUNT, trades, now=NOW, portfolio_balance=10_000
        )

    def test_tenth_position_is_accepted(self):
        snapshot = self.dashboard([trade(index) for index in range(9)])
        decision = evaluate_admission(
            snapshot,
            1,
            ticker="TEN",
            signal_rank=1,
            timestamp=NOW.isoformat(),
        )
        self.assertTrue(decision["allowed"])

    def test_eleventh_position_is_blocked(self):
        snapshot = self.dashboard([trade(index) for index in range(10)])
        decision = evaluate_admission(
            snapshot,
            0.5,
            ticker="ELEVEN",
            signal_rank=1,
            timestamp=NOW.isoformat(),
        )
        self.assertFalse(decision["allowed"])
        self.assertIn("10-position", decision["rejection_reason"])

    def test_exactly_ten_r_is_accepted(self):
        snapshot = self.dashboard(
            [trade(index, risk_r=1) for index in range(9)]
        )
        self.assertTrue(
            evaluate_admission(
                snapshot,
                1,
                ticker="TENR",
                signal_rank=1,
                timestamp=NOW.isoformat(),
            )["allowed"]
        )

    def test_above_ten_r_is_blocked(self):
        snapshot = self.dashboard(
            [trade(index, risk_r=1.05) for index in range(9)]
        )
        result = evaluate_admission(
            snapshot,
            0.6,
            ticker="OVER",
            signal_rank=1,
            timestamp=NOW.isoformat(),
        )
        self.assertFalse(result["allowed"])
        self.assertIn("10R open-risk", result["rejection_reason"])

    def test_exactly_one_r_daily_new_risk_is_accepted(self):
        snapshot = self.dashboard([])
        self.assertTrue(
            evaluate_admission(
                snapshot,
                1,
                ticker="ONE",
                signal_rank=1,
                timestamp=NOW.isoformat(),
            )["allowed"]
        )

    def test_above_one_r_daily_new_risk_is_blocked(self):
        snapshot = self.dashboard(
            [
                trade(
                    1,
                    risk_r=0.5,
                    admitted_at="2026-07-28T14:00:00+00:00",
                )
            ]
        )
        result = evaluate_admission(
            snapshot,
            0.6,
            ticker="OVER",
            signal_rank=1,
            timestamp=NOW.isoformat(),
        )
        self.assertFalse(result["allowed"])
        self.assertIn("1R new-risk", result["rejection_reason"])

    def test_chronological_same_day_ranking_admits_only_first_risk_unit(self):
        signals = [
            {"ticker": "LOW", "confidence": 80},
            {"ticker": "HIGH", "confidence": 95},
        ]
        accepted, rejected = admit_ranked_signals(
            signals, self.dashboard([]), timestamp=NOW.isoformat()
        )
        self.assertEqual([item["ticker"] for item in accepted], ["HIGH"])
        self.assertEqual([item["ticker"] for item in rejected], ["LOW"])

    def test_confidence_ranking_is_deterministic(self):
        signals = [
            {"ticker": "BBB", "confidence": 90},
            {"ticker": "AAA", "confidence": 90},
        ]
        first = admit_ranked_signals(
            signals, self.dashboard([]), timestamp=NOW.isoformat()
        )
        second = admit_ranked_signals(
            list(reversed(signals)),
            self.dashboard([]),
            timestamp=NOW.isoformat(),
        )
        self.assertEqual(first, second)
        self.assertEqual(first[0][0]["ticker"], "AAA")

    def test_partial_exit_releases_open_risk(self):
        snapshot = self.dashboard(
            [trade(index, remaining=0.5) for index in range(10)]
        )
        self.assertEqual(snapshot["open_risk_r"], 5)

    def test_closed_position_releases_capacity(self):
        rows = [trade(index) for index in range(9)]
        rows.append(trade(10, status="CLOSED"))
        snapshot = self.dashboard(rows)
        self.assertEqual(snapshot["open_positions"], 9)
        self.assertTrue(
            evaluate_admission(
                snapshot,
                1,
                ticker="NEW",
                signal_rank=1,
                timestamp=NOW.isoformat(),
            )["allowed"]
        )


if __name__ == "__main__":
    unittest.main()
