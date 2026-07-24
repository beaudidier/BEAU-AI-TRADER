import unittest

import pandas as pd

from data import get_stock_data
from providers import get_market_data_provider, set_market_data_provider
from providers.provider import MarketDataProvider


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


if __name__ == "__main__":
    unittest.main()
