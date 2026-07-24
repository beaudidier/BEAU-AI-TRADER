from .provider import MarketDataProvider
from .yahoo_provider import YahooFinanceProvider

_provider: MarketDataProvider = YahooFinanceProvider()


def get_market_data_provider() -> MarketDataProvider:
    """Return the configured market-data provider."""

    return _provider


def set_market_data_provider(provider: MarketDataProvider) -> None:
    """Replace the provider for tests or future runtime configuration."""

    global _provider
    _provider = provider
