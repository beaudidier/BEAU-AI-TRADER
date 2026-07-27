import unittest
from datetime import datetime, timezone

import pandas as pd

from providers.market_transparency import (
    build_market_data_transparency,
    latest_completed_candle_timestamp,
    latest_completed_session_date,
    market_session,
)
from providers.provider import MarketDataProvider
from unittest.mock import patch

from api import get_market_data_transparency


class FakeProvider(MarketDataProvider):
    provider_name = "Test Market Data"
    quote_data_label = "delayed"

    def get_quote(self, ticker):  # pragma: no cover - interface fixture
        return None

    def get_history(
        self,
        ticker,
        period="6mo",
        interval="1d",
        start=None,
        end=None,
    ):  # pragma: no cover - interface fixture
        return None

    def get_company(self, ticker):  # pragma: no cover - interface fixture
        return None

    def get_market_summary(self, tickers):  # pragma: no cover
        return []


def history(*dates: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0] * len(dates),
            "High": [102.0] * len(dates),
            "Low": [99.0] * len(dates),
            "Close": [101.0] * len(dates),
            "Volume": [1_000] * len(dates),
        },
        index=pd.to_datetime(list(dates)),
    )


class MarketDataTransparencyTests(unittest.TestCase):
    def test_market_session_boundaries(self):
        cases = {
            datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc): "premarket",
            datetime(2026, 7, 27, 14, 0, tzinfo=timezone.utc): "open",
            datetime(2026, 7, 27, 21, 0, tzinfo=timezone.utc): "after-hours",
            datetime(2026, 7, 28, 1, 0, tzinfo=timezone.utc): "closed",
            datetime(2026, 7, 26, 15, 0, tzinfo=timezone.utc): "closed",
        }
        for timestamp, expected in cases.items():
            with self.subTest(timestamp=timestamp):
                self.assertEqual(market_session(timestamp), expected)

    def test_full_market_holiday_is_closed(self):
        july_fourth_observed = datetime(
            2026,
            7,
            3,
            15,
            0,
            tzinfo=timezone.utc,
        )
        self.assertEqual(market_session(july_fourth_observed), "closed")

    def test_latest_completed_candle_excludes_open_session(self):
        now = datetime(2026, 7, 27, 15, 0, tzinfo=timezone.utc)
        candles = history("2026-07-24", "2026-07-27")
        self.assertEqual(
            latest_completed_candle_timestamp(candles, now),
            "2026-07-24T00:00:00",
        )
        self.assertEqual(
            latest_completed_session_date(now).isoformat(),
            "2026-07-24",
        )

    def test_today_candle_is_completed_after_validation_buffer(self):
        now = datetime(2026, 7, 27, 20, 20, tzinfo=timezone.utc)
        candles = history("2026-07-24", "2026-07-27")
        self.assertEqual(
            latest_completed_candle_timestamp(candles, now),
            "2026-07-27T00:00:00",
        )

    def test_transparency_distinguishes_quote_from_daily_signal(self):
        now = datetime(2026, 7, 27, 15, 0, tzinfo=timezone.utc)
        result = build_market_data_transparency(
            ticker="aapl",
            provider=FakeProvider(),
            quote={
                "price": 214.25,
                "timestamp": "2026-07-27T14:55:00+00:00",
            },
            daily_history=history("2026-07-24", "2026-07-27"),
            now=now,
        )
        self.assertEqual(result["provider"], "Test Market Data")
        self.assertEqual(result["market_status"], "open")
        self.assertEqual(
            result["current_quote"]["label"],
            "indicative current quote",
        )
        self.assertEqual(result["current_quote"]["data_label"], "delayed")
        self.assertFalse(result["current_quote"]["stale"])
        self.assertEqual(
            result["validated_daily_signal"][
                "latest_completed_candle_timestamp"
            ],
            "2026-07-24T00:00:00",
        )
        self.assertFalse(result["validated_daily_signal"]["stale"])
        self.assertIsNone(result["stale_data_warning"])

    def test_missing_quote_timestamp_and_old_daily_candle_warn(self):
        now = datetime(2026, 7, 27, 15, 0, tzinfo=timezone.utc)
        result = build_market_data_transparency(
            ticker="AAPL",
            provider=FakeProvider(),
            quote={"price": 214.25},
            daily_history=history("2026-07-23"),
            now=now,
        )
        self.assertTrue(result["current_quote"]["stale"])
        self.assertTrue(result["validated_daily_signal"]["stale"])
        self.assertIn(
            "did not supply a timestamp",
            result["stale_data_warning"],
        )
        self.assertIn(
            "older than the expected",
            result["stale_data_warning"],
        )

    def test_unknown_provider_label_is_normalized(self):
        provider = FakeProvider()
        provider.quote_data_label = "realtime-ish"
        result = build_market_data_transparency(
            ticker="AAPL",
            provider=provider,
            quote={
                "price": 214.25,
                "timestamp": "2026-07-27T14:55:00+00:00",
            },
            daily_history=history("2026-07-24"),
            now=datetime(2026, 7, 27, 15, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(result["current_quote"]["data_label"], "unknown")

    def test_endpoint_uses_provider_quote_and_daily_history(self):
        provider = FakeProvider()
        provider.get_quote = lambda _ticker: {
            "price": 214.25,
            "timestamp": "2026-07-27T14:55:00+00:00",
        }
        provider.get_history = lambda *_args, **_kwargs: history("2026-07-24")
        with patch("api.get_market_data_provider", return_value=provider):
            result = get_market_data_transparency("aapl")
        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["provider"], "Test Market Data")
        self.assertEqual(result["current_quote"]["price"], 214.25)

    def test_invalid_quote_price_is_not_serialized_as_market_data(self):
        result = build_market_data_transparency(
            ticker="AAPL",
            provider=FakeProvider(),
            quote={
                "price": float("nan"),
                "timestamp": "2026-07-27T14:55:00+00:00",
            },
            daily_history=history("2026-07-24"),
            now=datetime(2026, 7, 27, 15, 0, tzinfo=timezone.utc),
        )
        self.assertIsNone(result["current_quote"]["price"])


if __name__ == "__main__":
    unittest.main()
