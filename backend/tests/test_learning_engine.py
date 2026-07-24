import unittest

from learning.learning_engine import build_learning_context, build_learning_dashboard, build_learning_trade_update


class LearningEngineTests(unittest.TestCase):
    def test_context_classifies_setup_deterministically(self):
        context = build_learning_context("NVDA", 85, "STRONG BUY", {"engines": {"trend": {"score": 80}, "momentum": {"score": 75}, "market_regime": {"score": 90}}}, {"sector": "Technology"})
        self.assertEqual(context["setup_quality"], "High quality")
        self.assertEqual(context["market_regime"], "Risk-on")

    def test_completed_trade_stores_rr_and_coach_mistakes(self):
        update = build_learning_trade_update({"entry_price": 100, "stop_loss": 96, "quantity": 10, "realized_pnl": -40}, {"mistakes": ["Late exit"]})
        self.assertEqual(update["realized_rr"], -1)
        self.assertEqual(update["mistakes"], ["Late exit"])

    def test_dashboard_groups_results_and_recommendations(self):
        dashboard = build_learning_dashboard([
            {"status": "CLOSED", "confidence_score": 85, "market_regime": "Risk-on", "setup_quality": "High quality", "holding_minutes": 30, "realized_pnl": 100, "realized_rr": 2, "mistakes": [], "closed_at": "2026-07-01T10:00:00Z"},
            {"status": "CLOSED", "confidence_score": 60, "market_regime": "Defensive", "setup_quality": "Watchlist", "holding_minutes": 1600, "realized_pnl": -50, "realized_rr": -1, "mistakes": ["Late exit"], "closed_at": "2026-07-02T10:00:00Z"},
        ])
        self.assertEqual(dashboard["personal_statistics"]["win_rate"], 50)
        self.assertEqual(dashboard["most_common_mistakes"][0]["mistake"], "Late exit")
        self.assertTrue(dashboard["ai_recommendations"])


if __name__ == "__main__":
    unittest.main()
