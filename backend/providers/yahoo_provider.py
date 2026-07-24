from typing import Any

import pandas as pd
import yfinance as yf

from .provider import MarketDataProvider


class YahooFinanceProvider(MarketDataProvider):
    """Yahoo Finance implementation of the provider-neutral market-data contract."""

    def get_history(self, ticker: str, period: str = "6mo", interval: str = "1d", start: str | None = None, end: str | None = None) -> pd.DataFrame | None:
        try:
            options = {"tickers": ticker, "interval": interval, "progress": False, "auto_adjust": True, "group_by": "column"}
            if start is not None:
                options.update({"start": start, "end": end})
            else:
                options["period"] = period
            data = yf.download(**options)
            if data.empty:
                return None
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            for column in ["Open", "High", "Low", "Close", "Volume"]:
                if column in data.columns:
                    data[column] = data[column].squeeze()
            return data
        except Exception as error:
            print(f"Fout bij ophalen van {ticker}: {error}")
            return None

    def get_quote(self, ticker: str) -> dict[str, Any] | None:
        try:
            info = yf.Ticker(ticker).fast_info
            return {"ticker": ticker.upper(), "price": info.get("last_price"), "previous_close": info.get("previous_close"), "currency": info.get("currency")}
        except Exception as error:
            print(f"Fout bij quote ophalen van {ticker}: {error}")
            return None

    def get_company(self, ticker: str) -> dict[str, Any] | None:
        try:
            info = yf.Ticker(ticker).info
            return {"ticker": ticker.upper(), "name": info.get("longName"), "sector": info.get("sector"), "industry": info.get("industry"), "website": info.get("website")}
        except Exception as error:
            print(f"Fout bij bedrijfsinformatie ophalen van {ticker}: {error}")
            return None

    def get_market_summary(self, tickers: list[str]) -> list[dict[str, Any]]:
        return [quote for ticker in tickers if (quote := self.get_quote(ticker)) is not None]
