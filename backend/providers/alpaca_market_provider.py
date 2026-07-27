from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pandas as pd

from day_trading.models import Bar, Completeness, Quote


class AlpacaMarketDataError(RuntimeError):
    pass


class AlpacaMarketProvider:
    """Alpaca stock data with feed metadata kept outside strategy code."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        secret_key: str | None = None,
        feed: str | None = None,
        base_url: str = "https://data.alpaca.markets",
        client: httpx.Client | None = None,
    ):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY_ID", "")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY", "")
        self.feed = (feed or os.getenv("ALPACA_DATA_FEED", "iex")).lower()
        if self.feed not in {"iex", "sip"}:
            raise ValueError("ALPACA_DATA_FEED must be iex or sip.")
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=10)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    @property
    def source(self) -> str:
        return f"Alpaca {self.feed.upper()}"

    @property
    def coverage(self) -> str:
        return "partial-market" if self.feed == "iex" else "full-market"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
        }

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise AlpacaMarketDataError("Alpaca market data is not configured.")
        response = self.client.get(
            f"{self.base_url}{path}",
            params=params,
            headers=self.headers,
        )
        if response.status_code >= 400:
            raise AlpacaMarketDataError(
                f"Alpaca market data request failed ({response.status_code})."
            )
        return response.json()

    def latest_quote(self, ticker: str) -> Quote:
        symbol = ticker.upper()
        payload = self._get(
            "/v2/stocks/quotes/latest",
            {"symbols": symbol, "feed": self.feed},
        )
        value = payload.get("quotes", {}).get(symbol)
        if not value:
            raise AlpacaMarketDataError("No Alpaca quote is available.")
        timestamp = pd.Timestamp(value["t"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        return Quote(
            ticker=symbol,
            bid=float(value["bp"]),
            ask=float(value["ap"]),
            bid_size=float(value.get("bs", 0)),
            ask_size=float(value.get("as", 0)),
            timestamp=timestamp.tz_convert("UTC").to_pydatetime(warn=False),
            event_id=f"rest-q-{symbol}-{value['t']}",
            source=f"alpaca_{self.feed}",
            coverage=self.coverage,
        )

    def minute_bars(self, ticker: str, *, limit: int = 300) -> list[Bar]:
        symbol = ticker.upper()
        payload = self._get(
            f"/v2/stocks/{symbol}/bars",
            {
                "timeframe": "1Min",
                "feed": self.feed,
                "limit": max(1, min(limit, 10_000)),
                "sort": "asc",
            },
        )
        now = datetime.now(timezone.utc)
        result = []
        for value in payload.get("bars", []):
            timestamp = pd.Timestamp(value["t"])
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize("UTC")
            value_time = timestamp.tz_convert("UTC").to_pydatetime(warn=False)
            result.append(
                Bar(
                    ticker=symbol,
                    timeframe="1m",
                    open=float(value["o"]),
                    high=float(value["h"]),
                    low=float(value["l"]),
                    close=float(value["c"]),
                    volume=float(value["v"]),
                    vwap=(
                        float(value["vw"])
                        if value.get("vw") is not None
                        else None
                    ),
                    timestamp=value_time,
                    source=f"alpaca_{self.feed}",
                    completeness=(
                        Completeness.CLOSED
                        if now >= value_time.replace(second=0, microsecond=0)
                        + timedelta(minutes=1)
                        else Completeness.INCOMPLETE
                    ),
                )
            )
        return result

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Alpaca Market Data",
            "configured": self.configured,
            "feed": self.feed,
            "source": self.source,
            "coverage": self.coverage,
            "coverage_warning": (
                "IEX is a single-exchange feed with partial US-market coverage."
                if self.feed == "iex"
                else None
            ),
            "paper_only": True,
        }
