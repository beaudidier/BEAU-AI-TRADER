from __future__ import annotations

import unittest
from datetime import datetime, timezone

from day_trading.market_clock import MarketClock
from day_trading.models import MarketSession
from day_trading.session import classify_market_session, is_trading_day


class DayTradingSessionTests(unittest.TestCase):
    def test_regular_day_boundaries_are_timezone_safe(self):
        cases = [
            ("2026-07-27T07:59:00+00:00", MarketSession.CLOSED),
            ("2026-07-27T08:00:00+00:00", MarketSession.PREMARKET),
            ("2026-07-27T13:29:59+00:00", MarketSession.PREMARKET),
            ("2026-07-27T13:30:00+00:00", MarketSession.REGULAR),
            ("2026-07-27T20:00:00+00:00", MarketSession.AFTER_HOURS),
            ("2026-07-28T00:00:00+00:00", MarketSession.CLOSED),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    classify_market_session(datetime.fromisoformat(value)),
                    expected,
                )

    def test_us_holiday_is_closed(self):
        holiday = datetime(2026, 7, 3, 15, tzinfo=timezone.utc)
        self.assertFalse(is_trading_day(holiday.date()))
        self.assertEqual(classify_market_session(holiday), MarketSession.CLOSED)

    def test_early_close_is_reported(self):
        now = datetime.fromisoformat("2026-11-27T17:59:00+00:00")
        clock = MarketClock(lambda: now)
        snapshot = clock.snapshot()
        self.assertTrue(snapshot["is_early_close"])
        self.assertEqual(snapshot["status"], "regular")
        self.assertEqual(snapshot["regular_close"], "2026-11-27T18:00:00+00:00")
        self.assertEqual(
            classify_market_session(
                datetime.fromisoformat("2026-11-27T18:00:00+00:00")
            ),
            MarketSession.AFTER_HOURS,
        )

    def test_closed_after_hours_points_to_next_trading_day(self):
        clock = MarketClock(
            lambda: datetime.fromisoformat("2026-07-28T01:00:00+00:00")
        )
        snapshot = clock.snapshot()
        self.assertEqual(snapshot["status"], "closed")
        self.assertEqual(
            snapshot["next_transition"],
            "2026-07-28T08:00:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
