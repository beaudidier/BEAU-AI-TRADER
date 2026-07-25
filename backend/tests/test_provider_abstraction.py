import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep
from unittest.mock import patch

import pandas as pd

from data import get_stock_data
from providers import get_market_data_provider, set_market_data_provider
from providers.provider import MarketDataProvider
from providers.yahoo_provider import YahooFinanceProvider


class FakeProvider(MarketDataProvider):
    def get_quote(self, ticker): return {"ticker": ticker}
    def get_history(self, ticker, period="6mo", interval="1d", start=None, end=None): return pd.DataFrame({"Close": [1.0]})
    def get_company(self, ticker): return {"ticker": ticker}
    def get_market_summary(self, tickers): return [{"ticker": ticker} for ticker in tickers]


class ProviderAbstractionTests(unittest.TestCase):
    def test_legacy_data_helper_uses_configured_provider(self):
        original = get_market_data_provider()
        try:
            set_market_data_provider(FakeProvider())
            result = get_stock_data("TEST", period="1y", interval="1d")
            self.assertEqual(float(result["Close"].iloc[-1]), 1.0)
        finally:
            set_market_data_provider(original)

    @patch("providers.yahoo_provider.yf.download")
    def test_yahoo_provider_drops_incomplete_market_rows(self, download):
        download.return_value = pd.DataFrame(
            {
                "Open": [100.0, float("nan")],
                "High": [102.0, float("nan")],
                "Low": [99.0, float("nan")],
                "Close": [101.0, float("nan")],
                "Volume": [1_000, 2_000],
            },
            index=pd.to_datetime(["2026-07-23", "2026-07-24"]),
        )

        result = YahooFinanceProvider().get_history("TEST")

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.index[-1], pd.Timestamp("2026-07-23"))
        self.assertEqual(float(result["Close"].iloc[-1]), 101.0)

    @patch("providers.yahoo_provider.yf.download")
    def test_yahoo_provider_rejects_missing_ohlcv_columns(self, download):
        download.return_value = pd.DataFrame({"Close": [101.0]})

        self.assertIsNone(YahooFinanceProvider().get_history("TEST"))

    @patch("providers.yahoo_provider.yf.download")
    def test_yahoo_downloads_are_serialized(self, download):
        state_lock = Lock()
        active = 0
        maximum_active = 0

        def fake_download(**_options):
            nonlocal active, maximum_active
            with state_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            sleep(0.01)
            with state_lock:
                active -= 1
            return pd.DataFrame(
                {
                    "Open": [100.0],
                    "High": [102.0],
                    "Low": [99.0],
                    "Close": [101.0],
                    "Volume": [1_000],
                }
            )

        download.side_effect = fake_download
        provider = YahooFinanceProvider()
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(provider.get_history, ["A", "B", "C", "D"]))

        self.assertTrue(all(result is not None for result in results))
        self.assertEqual(maximum_active, 1)

    @patch("providers.yahoo_provider.yf.download")
    def test_yahoo_provider_splits_bounded_batch_response(self, download):
        columns = pd.MultiIndex.from_product(
            [["Open", "High", "Low", "Close", "Volume"], ["AAPL", "MSFT"]],
            names=["Price", "Ticker"],
        )
        download.return_value = pd.DataFrame(
            [[100, 200, 101, 201, 99, 199, 100.5, 200.5, 1_000, 2_000]],
            columns=columns,
            index=pd.to_datetime(["2026-07-24"]),
        )

        result = YahooFinanceProvider().get_histories(["AAPL", "MSFT"])

        self.assertEqual(sorted(result), ["AAPL", "MSFT"])
        self.assertEqual(float(result["AAPL"]["Close"].iloc[-1]), 100.5)
        self.assertEqual(float(result["MSFT"]["Close"].iloc[-1]), 200.5)
        self.assertFalse(download.call_args.kwargs["threads"])


if __name__ == "__main__":
    unittest.main()
