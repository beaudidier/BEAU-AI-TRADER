import unittest
from pathlib import Path

from paper_trading.portfolio_risk import (
    admit_ranked_signals,
    build_portfolio_risk_dashboard,
    evaluate_admission,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607250013_paper_admission_idempotency.sql"
)


class PortfolioRiskEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.account = {
            "initial_balance": 10_000,
            "cash_balance": 10_000,
        }
        self.dashboard = build_portfolio_risk_dashboard(
            self.account,
            [],
            portfolio_balance=10_000,
        )

    def test_simultaneous_ranked_admissions_never_exceed_daily_budget(self):
        signals = [
            {"ticker": f"T{index}", "confidence": 80 + index}
            for index in range(20)
        ]
        accepted, rejected = admit_ranked_signals(
            signals,
            self.dashboard,
            timestamp="2026-07-25T20:00:00+00:00",
        )
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 19)
        self.assertEqual(accepted[0]["ticker"], "T19")
        self.assertTrue(
            all(
                "1R new-risk budget"
                in item["portfolio_rejection"]["rejection_reason"]
                for item in rejected
            )
        )

    def test_rejected_admission_does_not_mutate_capacity(self):
        before = dict(self.dashboard)
        result = evaluate_admission(
            self.dashboard,
            1.01,
            ticker="OVER",
            signal_rank=1,
            timestamp="2026-07-25T20:00:00+00:00",
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(self.dashboard, before)

    def test_database_boundary_serializes_tabs_and_retries(self):
        sql = MIGRATION.read_text()
        self.assertIn("pg_advisory_xact_lock", sql)
        self.assertIn("ticker = upper(p_ticker)", sql)
        self.assertIn("and status = 'OPEN'", sql)
        self.assertIn("return to_jsonb(existing_trade)", sql)
        self.assertIn("portfolio_risk_rejections", sql)

    def test_account_row_lock_remains_the_global_atomic_boundary(self):
        sql = (
            ROOT
            / "supabase"
            / "migrations"
            / "202607250011_paper_portfolio_constraints.sql"
        ).read_text()
        self.assertIn("for update", sql.lower())
        self.assertIn("open_positions + 1 > 10", sql)
        self.assertIn("open_risk_r + proposed_risk_r > 10.000000001", sql)
        self.assertIn("daily_new_risk_r + proposed_risk_r > 1.000000001", sql)


if __name__ == "__main__":
    unittest.main()
