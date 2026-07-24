import unittest

from paper_trading.engine import build_portfolio_summary, build_trade_coach_payload


class PaperTradingEngineTests(unittest.TestCase):
    def test_portfolio_includes_open_and_realized_profit(self):
        result = build_portfolio_summary(
            {"initial_balance": 10000, "cash_balance": 9000},
            [{"ticker": "NVDA", "side": "BUY", "entry_price": 100, "quantity": 10, "opened_at": "2026-07-24T10:00:00Z"}],
            [{"ticker": "AAPL", "realized_pnl": 50, "closed_at": "2026-07-23T10:00:00Z"}],
            {"NVDA": {"price": 110, "previous_close": 108}},
        )
        self.assertEqual(result["unrealized_pnl"], 100)
        self.assertEqual(result["portfolio_balance"], 10100)
        self.assertEqual(result["realized_pnl"], 50)
        self.assertEqual(result["win_rate"], 100)

    def test_coach_payload_has_safe_risk_reward(self):
        payload = build_trade_coach_payload({"ticker": "NVDA", "entry_price": 100, "exit_price": 96, "stop_loss": 96, "target_1": 108, "quantity": 10, "realized_pnl": -40, "confidence_score": 80})
        self.assertEqual(payload["realized_rr"], -1)
        self.assertEqual(payload["ticker"], "NVDA")


if __name__ == "__main__":
    unittest.main()
