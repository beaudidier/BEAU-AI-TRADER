from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from day_trading.bar_aggregator import BarAggregator
from day_trading.models import Bar, Completeness, Quote
from day_trading.quote_cache import QuoteCache, QuoteValidationError


NOW = datetime(2026, 7, 27, 14, 30, tzinfo=timezone.utc)


def minute_bar(
    minute: int,
    *,
    completeness: Completeness = Completeness.CLOSED,
) -> Bar:
    price = 100 + minute
    return Bar(
        ticker="AAPL",
        timeframe="1m",
        open=price,
        high=price + 1,
        low=price - 1,
        close=price + 0.5,
        volume=100 + minute,
        vwap=price + 0.25,
        timestamp=NOW.replace(minute=minute),
        source="alpaca_iex",
        completeness=completeness,
    )


def quote(
    event_id: str,
    timestamp: datetime,
    *,
    bid: float = 100,
    ask: float = 100.10,
) -> Quote:
    return Quote(
        ticker="AAPL",
        bid=bid,
        ask=ask,
        bid_size=10,
        ask_size=12,
        timestamp=timestamp,
        event_id=event_id,
    )


class DayTradingDataIntegrityTests(unittest.TestCase):
    def test_deterministic_five_minute_aggregation(self):
        aggregator = BarAggregator()
        received = NOW.replace(minute=20)
        for minute in range(0, 5):
            self.assertTrue(
                aggregator.add_minute_bar(
                    minute_bar(minute),
                    received_at=received,
                )
            )
        first = aggregator.bars("AAPL", "5m")[0]
        second = aggregator.bars("AAPL", "5m")[0]
        self.assertEqual(first, second)
        self.assertEqual(first.completeness, Completeness.CLOSED)
        self.assertEqual(first.open, 100)
        self.assertEqual(first.close, 104.5)
        self.assertEqual(first.volume, sum(100 + value for value in range(5)))

    def test_incomplete_bar_never_becomes_closed(self):
        aggregator = BarAggregator()
        aggregator.add_minute_bar(
            minute_bar(0),
            received_at=NOW.replace(minute=20),
        )
        result = aggregator.bars("AAPL", "5m")[0]
        self.assertEqual(result.completeness, Completeness.INCOMPLETE)

    def test_gap_duplicate_and_out_of_order_are_reported(self):
        aggregator = BarAggregator()
        received = NOW.replace(minute=20)
        self.assertTrue(
            aggregator.add_minute_bar(minute_bar(0), received_at=received)
        )
        self.assertFalse(
            aggregator.add_minute_bar(minute_bar(0), received_at=received)
        )
        self.assertTrue(
            aggregator.add_minute_bar(minute_bar(2), received_at=received)
        )
        self.assertFalse(
            aggregator.add_minute_bar(minute_bar(1), received_at=received)
        )
        self.assertEqual(aggregator.duplicates, 1)
        self.assertEqual(aggregator.out_of_order, 1)
        self.assertEqual(len(aggregator.gaps["AAPL"]), 1)
        self.assertEqual(
            aggregator.bars("AAPL", "5m")[0].completeness,
            Completeness.GAP,
        )

    def test_historical_backfill_preserves_live_bar_without_out_of_order_noise(self):
        aggregator = BarAggregator()
        base = NOW.replace(minute=0)
        received = base + timedelta(minutes=10)
        aggregator.add_minute_bar(
            minute_bar(10),
            received_at=received,
        )
        for minute in range(10):
            aggregator.add_minute_bar(
                minute_bar(minute),
                received_at=received,
                historical_backfill=True,
            )

        values = aggregator.bars("AAPL", "1m")
        self.assertEqual(len(values), 11)
        self.assertEqual(values[0].timestamp, base)
        self.assertEqual(values[-1].timestamp, base + timedelta(minutes=10))
        self.assertEqual(aggregator.out_of_order, 0)

    def test_future_bar_is_rejected(self):
        aggregator = BarAggregator(future_tolerance_seconds=0)
        with self.assertRaises(ValueError):
            aggregator.add_minute_bar(
                minute_bar(20),
                received_at=NOW.replace(minute=19),
            )

    def test_quote_cache_rejects_invalid_and_out_of_order_quotes(self):
        cache = QuoteCache(stale_after_seconds=15)
        self.assertTrue(cache.put(quote("one", NOW), received_at=NOW))
        self.assertFalse(cache.put(quote("one", NOW), received_at=NOW))
        self.assertFalse(
            cache.put(
                quote("old", NOW - timedelta(seconds=1)),
                received_at=NOW,
            )
        )
        with self.assertRaises(QuoteValidationError):
            cache.put(
                quote("crossed", NOW, bid=101, ask=100),
                received_at=NOW,
            )
        self.assertEqual(cache.duplicates, 1)
        self.assertEqual(cache.out_of_order, 1)

    def test_quote_snapshot_stores_timestamp_spread_and_staleness(self):
        cache = QuoteCache(stale_after_seconds=15)
        cache.put(quote("one", NOW), received_at=NOW)
        snapshot = cache.snapshot(
            "AAPL",
            now=NOW + timedelta(seconds=16),
        )
        self.assertEqual(snapshot["timestamp"], NOW.isoformat())
        self.assertAlmostEqual(snapshot["spread"], 0.1)
        self.assertTrue(snapshot["stale"])
        self.assertEqual(snapshot["coverage"], "partial-market")


if __name__ == "__main__":
    unittest.main()
