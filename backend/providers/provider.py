from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class MarketDataProvider(ABC):
    """Provider-neutral contract for market data consumed by the application."""

    @abstractmethod
    def get_quote(self, ticker: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def get_history(self, ticker: str, period: str = "6mo", interval: str = "1d", start: str | None = None, end: str | None = None) -> pd.DataFrame | None: ...

    def get_histories(
        self,
        tickers: list[str],
        period: str = "6mo",
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Optional bounded batch path with a safe single-symbol fallback."""

        result = {}
        for ticker in dict.fromkeys(tickers):
            history = self.get_history(
                ticker,
                period=period,
                interval=interval,
                start=start,
                end=end,
            )
            if history is not None:
                result[ticker] = history
        return result

    @abstractmethod
    def get_company(self, ticker: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def get_market_summary(self, tickers: list[str]) -> list[dict[str, Any]]: ...
