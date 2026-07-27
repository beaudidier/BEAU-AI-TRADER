from threading import Lock
from datetime import timezone
from typing import Any

import pandas as pd
import yfinance as yf

from .provider import MarketDataProvider

_DOWNLOAD_LOCK = Lock()


class YahooFinanceProvider(MarketDataProvider):
    """Yahoo Finance implementation of the provider-neutral market-data contract."""

    provider_name = "Yahoo Finance"
    quote_data_label = "delayed"

    @staticmethod
    def _normalize_history(data: pd.DataFrame) -> pd.DataFrame | None:
        if data.empty:
            return None
        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        if data.columns.has_duplicates:
            return None
        for column in required_columns:
            if column in data.columns:
                data[column] = data[column].squeeze()
        if any(column not in data.columns for column in required_columns):
            return None
        data = data.dropna(subset=required_columns)
        return None if data.empty else data

    def get_history(self, ticker: str, period: str = "6mo", interval: str = "1d", start: str | None = None, end: str | None = None) -> pd.DataFrame | None:
        try:
            options = {"tickers": ticker, "interval": interval, "progress": False, "auto_adjust": True, "group_by": "column"}
            if start is not None:
                options.update({"start": start, "end": end})
            else:
                options["period"] = period
            # yfinance mutates shared download state, so parallel dashboard
            # requests can otherwise mix columns from unrelated tickers.
            with _DOWNLOAD_LOCK:
                data = yf.download(**options)
            if data.empty:
                return None
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return self._normalize_history(data)
        except Exception as error:
            print(f"Fout bij ophalen van {ticker}: {error}")
            return None

    def get_histories(
        self,
        tickers: list[str],
        period: str = "6mo",
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, pd.DataFrame]:
        requested = list(dict.fromkeys(ticker.upper() for ticker in tickers if ticker))
        if not requested:
            return {}
        try:
            options = {
                "tickers": requested,
                "interval": interval,
                "progress": False,
                "auto_adjust": True,
                "group_by": "column",
                "threads": False,
            }
            if start is not None:
                options.update({"start": start, "end": end})
            else:
                options["period"] = period
            with _DOWNLOAD_LOCK:
                data = yf.download(**options)
            if data.empty:
                return {}
            if len(requested) == 1:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                normalized = self._normalize_history(data)
                return {requested[0]: normalized} if normalized is not None else {}
            if not isinstance(data.columns, pd.MultiIndex):
                return {}
            ticker_level = 1 if set(requested) & set(data.columns.get_level_values(1)) else 0
            result: dict[str, pd.DataFrame] = {}
            for ticker in requested:
                if ticker not in set(data.columns.get_level_values(ticker_level)):
                    continue
                history = data.xs(ticker, axis=1, level=ticker_level).copy()
                normalized = self._normalize_history(history)
                if normalized is not None:
                    result[ticker] = normalized
            return result
        except Exception as error:
            print(f"Fout bij batch ophalen: {type(error).__name__}")
            return {}

    def get_quote(self, ticker: str) -> dict[str, Any] | None:
        try:
            info = yf.Ticker(ticker).fast_info
            return {
                "ticker": ticker.upper(),
                "price": info.get("last_price"),
                "previous_close": info.get("previous_close"),
                "currency": info.get("currency"),
            }
        except Exception as error:
            print(f"Fout bij quote ophalen van {ticker}: {error}")
            return None

    def get_quote_transparency(self, ticker: str) -> dict[str, Any] | None:
        quote = self.get_quote(ticker)
        if quote is None:
            return None
        timestamp = None
        try:
            instrument = yf.Ticker(ticker)
            try:
                with _DOWNLOAD_LOCK:
                    intraday = instrument.history(
                        period="1d",
                        interval="1m",
                        prepost=True,
                        auto_adjust=True,
                        raise_errors=False,
                    )
                if intraday is not None and not intraday.empty:
                    latest = intraday.dropna(subset=["Close"]).iloc[-1]
                    latest_index = pd.Timestamp(intraday.dropna(subset=["Close"]).index[-1])
                    if latest_index.tzinfo is None:
                        latest_index = latest_index.tz_localize("UTC")
                    quote["price"] = float(latest["Close"])
                    timestamp = latest_index.tz_convert(timezone.utc).isoformat()
            except Exception:
                # A quote without an exchange timestamp remains usable but is
                # explicitly labelled unknown/stale by the transparency layer.
                timestamp = None
            return {**quote, "timestamp": timestamp}
        except Exception as error:
            print(f"Fout bij quote-tijd ophalen van {ticker}: {error}")
            return {**quote, "timestamp": None}

    def get_company(self, ticker: str) -> dict[str, Any] | None:
        try:
            info = yf.Ticker(ticker).info
            return {"ticker": ticker.upper(), "name": info.get("longName"), "sector": info.get("sector"), "industry": info.get("industry"), "website": info.get("website")}
        except Exception as error:
            print(f"Fout bij bedrijfsinformatie ophalen van {ticker}: {error}")
            return None

    def get_market_summary(self, tickers: list[str]) -> list[dict[str, Any]]:
        return [quote for ticker in tickers if (quote := self.get_quote(ticker)) is not None]
