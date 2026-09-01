from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from providers.alpaca_market_provider import (
    AlpacaMarketDataError,
    AlpacaMarketProvider,
)
from providers.alpaca_paper_broker import AlpacaPaperBrokerClient

from .bar_aggregator import BarAggregator
from .market_clock import MarketClock
from .models import Bar, Quote, TradeTick
from .paper_broker import PaperBroker
from .quote_cache import QuoteCache, QuoteValidationError
from .recorder import IntradayRecorder
from .replay import DeterministicReplayEngine
from .stream_manager import AlpacaStreamManager


class DayTradingRuntime:
    def __init__(self):
        self.clock = MarketClock()
        self.quotes = QuoteCache(
            stale_after_seconds=int(
                os.getenv("DAY_TRADING_QUOTE_STALE_SECONDS", "15")
            )
        )
        self.bars = BarAggregator()
        self.market_provider = AlpacaMarketProvider()
        self.alpaca_paper = AlpacaPaperBrokerClient()
        self.paper_broker = PaperBroker(
            self.quotes,
            self.clock,
            starting_balance=float(
                os.getenv("DAY_TRADING_PAPER_BALANCE", "100000")
            ),
            max_spread_percent=float(
                os.getenv("DAY_TRADING_MAX_SPREAD_PERCENT", "0.25")
            ),
            orders_enabled=(
                os.getenv(
                    "DAY_TRADING_PAPER_ORDERS_ENABLED",
                    "false",
                ).lower()
                == "true"
            ),
        )
        symbols = [
            value.strip()
            for value in os.getenv(
                "DAY_TRADING_SYMBOLS",
                "AAPL,MSFT,NVDA",
            ).split(",")
            if value.strip()
        ]
        self.stream = AlpacaStreamManager(
            api_key=self.market_provider.api_key,
            secret_key=self.market_provider.secret_key,
            feed=self.market_provider.feed,
            symbols=symbols,
            heartbeat_timeout_seconds=int(
                os.getenv("DAY_TRADING_HEARTBEAT_TIMEOUT_SECONDS", "30")
            ),
            on_trade=self._on_trade,
            on_quote=self._on_quote,
            on_bar=self._on_bar,
            on_raw_event=self._on_raw_event,
            on_system_event=self._on_stream_system,
        )
        self.stream_enabled = (
            os.getenv("DAY_TRADING_STREAM_ENABLED", "false").lower() == "true"
        )
        self.last_trade: dict[str, TradeTick] = {}
        recording_path = Path(
            os.getenv(
                "DAY_TRADING_RECORDING_PATH",
                "data/day_trading_recordings",
            )
        )
        if not recording_path.is_absolute():
            recording_path = Path(__file__).resolve().parents[1] / recording_path
        self.recorder = IntradayRecorder(recording_path)
        self.replay = DeterministicReplayEngine(self.recorder)
        self.research_enabled = (
            os.getenv(
                "DAY_TRADING_RESEARCH_ENABLED",
                "false",
            ).lower()
            == "true"
        )
        self._bar_history_loaded: set[str] = set()
        self._bar_history_lock = RLock()
        self._session_guard_task: asyncio.Task | None = None

    def _on_trade(self, trade: TradeTick) -> None:
        current = self.last_trade.get(trade.ticker)
        if current is None or trade.timestamp >= current.timestamp:
            self.last_trade[trade.ticker] = trade

    def _on_quote(self, quote: Quote) -> None:
        if self.quotes.put(quote):
            self.paper_broker.process_quote(quote.ticker)

    def _on_bar(self, bar: Bar) -> None:
        self.bars.add_minute_bar(bar)

    def _on_raw_event(
        self,
        event: dict[str, Any],
        received_at: datetime,
        disposition: str,
    ) -> None:
        self.recorder.record_raw(
            event,
            received_at=received_at,
            disposition=disposition,
        )

    def _on_stream_system(
        self,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        self.recorder.record_system(
            event_type,
            payload,
            occurred_at=occurred_at,
        )

    async def start(self) -> None:
        if self.stream_enabled:
            await self.stream.start()
        if self._session_guard_task is None:
            self._session_guard_task = asyncio.create_task(
                self._session_guard(),
                name="day-trading-session-guard",
            )

    async def stop(self) -> None:
        await self.stream.stop()
        if self._session_guard_task is not None:
            self._session_guard_task.cancel()
            try:
                await self._session_guard_task
            except asyncio.CancelledError:
                pass
            self._session_guard_task = None

    async def _session_guard(self) -> None:
        while True:
            self.paper_broker.enforce_no_overnight()
            if self.recorder.active:
                self.recorder.record_system(
                    "heartbeat",
                    self.stream.health(),
                )
                self.recorder.record_system(
                    "market_clock",
                    self.clock.snapshot(),
                )
            await asyncio.sleep(5)

    def ensure_quote(self, ticker: str) -> dict | None:
        snapshot = self.quotes.snapshot(ticker)
        if snapshot is not None:
            return snapshot
        if not self.market_provider.configured:
            return None
        try:
            quote = self.market_provider.latest_quote(ticker)
            self.quotes.put(quote, received_at=datetime.now(timezone.utc))
        except (AlpacaMarketDataError, QuoteValidationError):
            return None
        return self.quotes.snapshot(ticker)

    def ensure_bars(self, ticker: str, timeframe: str) -> dict[str, Any]:
        symbol = ticker.upper()
        if self.market_provider.configured and symbol not in self._bar_history_loaded:
            with self._bar_history_lock:
                if symbol not in self._bar_history_loaded:
                    try:
                        for bar in self.market_provider.minute_bars(symbol):
                            self.bars.add_minute_bar(
                                bar,
                                received_at=datetime.now(timezone.utc),
                                historical_backfill=True,
                            )
                    except (AlpacaMarketDataError, ValueError):
                        pass
                    else:
                        self._bar_history_loaded.add(symbol)
        return self.bars.serialized(symbol, timeframe)

    def status(self) -> dict[str, Any]:
        stream = self.stream.health()
        configured = self.market_provider.configured
        return {
            "status": (
                "connected"
                if stream["state"] == "connected"
                else "configured"
                if configured
                else "credentials_required"
            ),
            "paper_only": True,
            "live_money_enabled": False,
            "recommendations_enabled": False,
            "research_enabled": self.research_enabled,
            "provider": self.market_provider.status(),
            "alpaca_paper": self.alpaca_paper.status(),
            "stream": stream,
            "market_clock": self.clock.snapshot(),
            "risk_controls": {
                "maximum_account_risk_per_trade_percent": 0.25,
                "maximum_open_day_trades": 2,
                "maximum_daily_loss_percent": 0.5,
                "no_averaging_down": True,
                "no_overnight_positions": True,
                "stale_quote_orders_blocked": True,
                "maximum_spread_percent": self.paper_broker.max_spread_percent,
            },
        }


day_trading_runtime = DayTradingRuntime()
