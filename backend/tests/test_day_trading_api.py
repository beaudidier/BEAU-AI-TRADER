from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api import app


class DayTradingApiTests(unittest.TestCase):
    def test_required_routes_are_registered(self):
        paths = app.openapi()["paths"]
        routes = {
            (path, method.upper())
            for path, operations in paths.items()
            for method in operations
        }
        expected = {
            ("/day-trading/status", "GET"),
            ("/day-trading/market-clock", "GET"),
            ("/day-trading/stream-health", "GET"),
            ("/day-trading/bars/{ticker}", "GET"),
            ("/day-trading/quotes/{ticker}", "GET"),
            ("/day-trading/paper-account", "GET"),
            ("/day-trading/paper-positions", "GET"),
            ("/day-trading/paper-orders", "POST"),
            ("/day-trading/paper-orders/{order_id}", "DELETE"),
        }
        self.assertTrue(expected.issubset(routes))

    def test_status_is_paper_only_and_has_no_recommendations(self):
        with TestClient(app) as client:
            response = client.get("/day-trading/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_money_enabled"])
        self.assertFalse(payload["recommendations_enabled"])
        self.assertEqual(payload["provider"]["feed"], "iex")
        self.assertEqual(payload["provider"]["coverage"], "partial-market")

    def test_invalid_timeframe_is_rejected(self):
        with TestClient(app) as client:
            response = client.get("/day-trading/bars/AAPL?timeframe=1h")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            "Timeframe must be 1m, 5m, or 15m.",
        )


if __name__ == "__main__":
    unittest.main()
