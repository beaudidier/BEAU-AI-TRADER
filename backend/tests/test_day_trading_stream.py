from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone

from day_trading.models import Completeness, StreamState
from day_trading.stream_manager import AlpacaStreamManager


NOW = datetime(2026, 7, 27, 14, 30, 10, tzinfo=timezone.utc)


class FailingSocket:
    async def __aenter__(self):
        raise ConnectionError("offline")

    async def __aexit__(self, *_args):
        return False


class DayTradingStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconnect_uses_exponential_backoff(self):
        delays: list[float] = []

        async def fake_sleep(delay):
            delays.append(delay)

        manager = AlpacaStreamManager(
            api_key="test",
            secret_key="test",
            websocket_factory=lambda _url: FailingSocket(),
            sleep=fake_sleep,
        )
        await manager.run(maximum_attempts=3)
        self.assertEqual(delays, [1, 2])
        self.assertEqual(manager.diagnostics.reconnect_attempts, 3)
        self.assertEqual(manager.diagnostics.state, StreamState.ERROR)

    async def test_duplicate_out_of_order_and_incomplete_bar_handling(self):
        trades = []
        bars = []
        manager = AlpacaStreamManager(
            api_key="test",
            secret_key="test",
            on_trade=trades.append,
            on_bar=bars.append,
        )
        trade = {
            "T": "t",
            "S": "AAPL",
            "p": 100,
            "s": 2,
            "t": "2026-07-27T14:30:00Z",
        }
        manager.process_message([trade, trade], received_at=NOW)
        manager.process_message(
            [{**trade, "p": 99, "t": "2026-07-27T14:29:59Z"}],
            received_at=NOW,
        )
        manager.process_message(
            [
                {
                    "T": "b",
                    "S": "AAPL",
                    "o": 100,
                    "h": 101,
                    "l": 99,
                    "c": 100.5,
                    "v": 1000,
                    "vw": 100.25,
                    "t": "2026-07-27T14:30:00Z",
                }
            ],
            received_at=NOW,
        )
        self.assertEqual(len(trades), 1)
        self.assertEqual(manager.diagnostics.duplicate_events, 1)
        self.assertEqual(manager.diagnostics.out_of_order_events, 1)
        self.assertEqual(bars[0].completeness, Completeness.INCOMPLETE)

    async def test_stale_stream_health(self):
        manager = AlpacaStreamManager(
            api_key="test",
            secret_key="test",
            heartbeat_timeout_seconds=10,
        )
        manager.diagnostics.state = StreamState.CONNECTED
        manager.diagnostics.last_heartbeat_at = NOW
        health = manager.health(now=NOW + timedelta(seconds=11))
        self.assertTrue(health["stale"])
        self.assertEqual(health["state"], "stale")
        self.assertEqual(health["coverage"], "partial-market")

    async def test_sip_metadata_is_swappable_without_consumers_changing(self):
        quotes = []
        manager = AlpacaStreamManager(
            api_key="test",
            secret_key="test",
            feed="sip",
            on_quote=quotes.append,
        )
        manager.process_message(
            json.dumps(
                [
                    {
                        "T": "q",
                        "S": "MSFT",
                        "bp": 400,
                        "ap": 400.05,
                        "bs": 5,
                        "as": 6,
                        "t": "2026-07-27T14:30:00Z",
                    }
                ]
            ),
            received_at=NOW,
        )
        self.assertEqual(quotes[0].coverage, "full-market")
        self.assertEqual(manager.health(now=NOW)["feed"], "sip")


if __name__ == "__main__":
    unittest.main()
