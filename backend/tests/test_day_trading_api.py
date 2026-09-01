from __future__ import annotations

import unittest
import tempfile
import time

from fastapi.testclient import TestClient

from api import app
from day_trading.health import day_trading_runtime
from day_trading.recorder import IntradayRecorder
from day_trading.replay import DeterministicReplayEngine


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
            ("/day-trading/record/start", "POST"),
            ("/day-trading/record/stop", "POST"),
            ("/day-trading/record/status", "GET"),
            ("/day-trading/record/sessions", "GET"),
            ("/day-trading/replay/start", "POST"),
            ("/day-trading/replay/pause", "POST"),
            ("/day-trading/replay/resume", "POST"),
            ("/day-trading/replay/seek", "POST"),
            ("/day-trading/replay/reset", "POST"),
            ("/day-trading/replay/status", "GET"),
            ("/day-trading/replay/bars/{ticker}", "GET"),
            ("/day-trading/replay/verify/{session_id}", "GET"),
            ("/day-trading/replay/orders", "POST"),
            ("/day-trading/replay/orders/{order_id}", "DELETE"),
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

    def test_research_endpoints_are_disabled_without_explicit_local_flag(self):
        with TestClient(app) as client:
            response = client.get("/day-trading/record/status")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "The day-trading research lab is disabled.",
        )


class DayTradingResearchApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.original_recorder = day_trading_runtime.recorder
        self.original_replay = day_trading_runtime.replay
        self.original_research = day_trading_runtime.research_enabled
        self.original_symbols = day_trading_runtime.stream.symbols
        day_trading_runtime.recorder = IntradayRecorder(
            self.temporary.name
        )
        day_trading_runtime.replay = DeterministicReplayEngine(
            day_trading_runtime.recorder
        )
        day_trading_runtime.research_enabled = True
        day_trading_runtime.stream.symbols = ["AAPL"]

    def tearDown(self):
        day_trading_runtime.recorder.stop()
        day_trading_runtime.replay.reset()
        day_trading_runtime.recorder = self.original_recorder
        day_trading_runtime.replay = self.original_replay
        day_trading_runtime.research_enabled = self.original_research
        day_trading_runtime.stream.symbols = self.original_symbols
        self.temporary.cleanup()

    def test_record_replay_and_verification_api_flow(self):
        with TestClient(app) as client:
            started = client.post(
                "/day-trading/record/start",
                json={"symbols": ["AAPL"]},
            )
            self.assertEqual(started.status_code, 200)
            self.assertTrue(started.json()["active"])

            stopped = client.post("/day-trading/record/stop")
            self.assertEqual(stopped.status_code, 200)
            session_id = stopped.json()["session_id"]
            self.assertTrue(stopped.json()["checksum_sha256"])

            sessions = client.get("/day-trading/record/sessions")
            self.assertEqual(sessions.status_code, 200)
            self.assertEqual(
                sessions.json()["sessions"][0]["session_id"],
                session_id,
            )

            replay = client.post(
                "/day-trading/replay/start",
                json={"session_id": session_id, "speed": "maximum"},
            )
            self.assertEqual(replay.status_code, 200)
            for _ in range(20):
                status = client.get("/day-trading/replay/status").json()
                if status["status"] == "completed":
                    break
                time.sleep(0.005)
            self.assertEqual(status["status"], "completed")
            self.assertFalse(status["live_order_routing"])
            replay_bars = client.get(
                "/day-trading/replay/bars/AAPL?timeframe=5m"
            )
            self.assertEqual(replay_bars.status_code, 200)
            self.assertEqual(replay_bars.json()["timeframe"], "5m")

            verified = client.get(
                f"/day-trading/replay/verify/{session_id}"
            )
            self.assertEqual(verified.status_code, 200)
            self.assertTrue(
                verified.json()["recording"]["checksum_valid"]
            )
            self.assertTrue(
                verified.json()["determinism"]["deterministic"]
            )

            reset = client.post("/day-trading/replay/reset")
            self.assertEqual(reset.status_code, 200)
            self.assertEqual(reset.json()["status"], "idle")


if __name__ == "__main__":
    unittest.main()
