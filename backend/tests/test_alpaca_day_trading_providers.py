from __future__ import annotations

import unittest

from providers.alpaca_market_provider import AlpacaMarketProvider
from providers.alpaca_paper_broker import (
    AlpacaPaperBrokerClient,
    AlpacaPaperBrokerError,
)


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, payload=None):
        self.payload = payload or {}
        self.calls = []

    def get(self, url, **options):
        self.calls.append(("GET", url, options))
        return FakeResponse(self.payload)

    def request(self, method, url, **options):
        self.calls.append((method, url, options))
        return FakeResponse({"id": "paper-order"})


class AlpacaDayTradingProviderTests(unittest.TestCase):
    def test_iex_is_explicitly_partial_market_coverage(self):
        provider = AlpacaMarketProvider(
            api_key="test",
            secret_key="test",
            feed="iex",
            client=FakeClient(),
        )
        status = provider.status()
        self.assertEqual(status["coverage"], "partial-market")
        self.assertIn("single-exchange", status["coverage_warning"])

    def test_latest_quote_uses_configured_feed_and_preserves_metadata(self):
        client = FakeClient(
            {
                "quotes": {
                    "AAPL": {
                        "bp": 100,
                        "ap": 100.05,
                        "bs": 10,
                        "as": 12,
                        "t": "2026-07-27T14:30:00Z",
                    }
                }
            }
        )
        provider = AlpacaMarketProvider(
            api_key="test",
            secret_key="test",
            feed="iex",
            client=client,
        )
        quote = provider.latest_quote("aapl")
        self.assertEqual(client.calls[0][2]["params"]["feed"], "iex")
        self.assertEqual(quote.coverage, "partial-market")
        self.assertEqual(quote.ticker, "AAPL")

    def test_sip_can_be_selected_without_changing_consumer_contract(self):
        provider = AlpacaMarketProvider(
            api_key="test",
            secret_key="test",
            feed="sip",
            client=FakeClient(),
        )
        self.assertEqual(provider.coverage, "full-market")
        self.assertEqual(provider.status()["feed"], "sip")

    def test_paper_adapter_rejects_live_broker_domain(self):
        with self.assertRaisesRegex(ValueError, "paper trading domain"):
            AlpacaPaperBrokerClient(
                api_key="test",
                secret_key="test",
                base_url="https://api.alpaca.markets",
            )

    def test_paper_adapter_is_disabled_by_default(self):
        client = AlpacaPaperBrokerClient(
            api_key="test",
            secret_key="test",
            enabled=False,
        )
        with self.assertRaises(AlpacaPaperBrokerError):
            client.submit_order(
                {"symbol": "AAPL", "qty": "1", "side": "buy", "type": "market"}
            )

    def test_paper_adapter_never_changes_the_paper_domain(self):
        fake = FakeClient()
        client = AlpacaPaperBrokerClient(
            api_key="test",
            secret_key="test",
            enabled=True,
            client=fake,
        )
        client.submit_order(
            {"symbol": "AAPL", "qty": "1", "side": "buy", "type": "market"}
        )
        self.assertTrue(fake.calls[0][1].startswith(client.PAPER_BASE_URL))
        self.assertEqual(
            fake.calls[0][2]["json"]["time_in_force"],
            "day",
        )


if __name__ == "__main__":
    unittest.main()
