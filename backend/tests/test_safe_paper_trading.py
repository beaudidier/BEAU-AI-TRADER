import unittest

from paper_trading.engine import build_close_preview
from paper_trading.validation import validate_long_paper_trade


class SafePaperTradingTests(unittest.TestCase):
    def setUp(self):
        self.valid = {"side": "BUY", "recommendation": "BUY", "current_price": 100, "entry_price": 100, "stop_loss": 96, "target_1": 106, "target_2": 112, "quantity": 10, "confidence_score": 80, "risk_reward_target_1": 1.5}

    def test_valid_paper_buy_is_allowed(self):
        validate_long_paper_trade(self.valid)

    def test_skip_trade_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "SKIP"):
            validate_long_paper_trade({**self.valid, "confidence_score": 59, "recommendation": "SKIP"})

    def test_mismatched_recommendation_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_long_paper_trade({**self.valid, "recommendation": "WATCH"})

    def test_low_rr_trade_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "risk/reward"):
            validate_long_paper_trade({**self.valid, "risk_reward_target_1": 1.49})

    def test_zero_quantity_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "quantity"):
            validate_long_paper_trade({**self.valid, "quantity": 0})

    def test_short_trade_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "Only long"):
            validate_long_paper_trade({**self.valid, "side": "SELL"})

    def test_close_preview_has_quote_and_realized_pnl_estimate(self):
        preview = build_close_preview({"id": "trade-1", "ticker": "NVDA", "side": "BUY", "entry_price": 100, "quantity": 10}, 108, "2026-07-24T10:00:00+00:00")
        self.assertEqual(preview["latest_quote"], 108)
        self.assertEqual(preview["estimated_exit_value"], 1080)
        self.assertEqual(preview["realized_pnl_estimate"], 80)


if __name__ == "__main__":
    unittest.main()
