import unittest

from coach.coach_engine import analyze_completed_trade


class CoachEngineTests(unittest.TestCase):
    def setUp(self):
        self.winning_trade = {
            "ticker": "NVDA", "entry": 100, "exit": 108, "stop_loss": 96,
            "target_1": 108, "pnl": 800, "realized_rr": 2, "confidence_score": 84,
            "recommendation": "STRONG BUY", "exit_reason": "Target 1",
        }

    def test_winning_trade_returns_complete_bounded_coaching(self):
        result = analyze_completed_trade(self.winning_trade)
        self.assertEqual(set(result), {"grade", "score", "summary", "mistakes", "positives", "improvements", "confidence_alignment", "emotional_bias", "discipline_score", "explanation"})
        self.assertIn(result["grade"], {"A", "B", "C", "D", "F"})
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["discipline_score"], 100)
        self.assertTrue(result["positives"])
        self.assertEqual(result["explanation"]["verdict"], "BUY")

    def test_stopped_trade_identifies_improvement(self):
        result = analyze_completed_trade({**self.winning_trade, "exit": 96, "pnl": -400, "realized_rr": -1, "exit_reason": "Stop loss"})
        self.assertTrue(result["mistakes"])
        self.assertTrue(result["improvements"])
        self.assertIn("contained", result["emotional_bias"])

    def test_invalid_market_values_are_rejected(self):
        with self.assertRaises(ValueError):
            analyze_completed_trade({**self.winning_trade, "entry": 0})


if __name__ == "__main__":
    unittest.main()
