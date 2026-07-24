from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class MarketDataProvider(ABC):
    """Provider-neutral contract for market data consumed by the application."""

    @abstractmethod
    def get_quote(self, ticker: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def get_history(self, ticker: str, period: str = "6mo", interval: str = "1d", start: str | None = None, end: str | None = None) -> pd.DataFrame | None: ...

    @abstractmethod
    def get_company(self, ticker: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def get_market_summary(self, tickers: list[str]) -> list[dict[str, Any]]: ...
