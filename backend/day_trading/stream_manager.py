from __future__ import annotations

import asyncio
import hashlib
import json
import ssl
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncContextManager

import pandas as pd
import certifi
import websockets

from .models import (
    Bar,
    Completeness,
    Quote,
    StreamDiagnostics,
    StreamState,
    TradeTick,
)
from .session import as_utc

EventHandler = Callable[[Any], None]
RawEventHandler = Callable[[dict[str, Any], datetime, str], None]
SystemEventHandler = Callable[[str, dict[str, Any], datetime], None]
WebSocketFactory = Callable[[str], AsyncContextManager[Any]]
Sleep = Callable[[float], Awaitable[None]]


def _timestamp(value: Any) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC").to_pydatetime(warn=False)


def _event_id(event: dict[str, Any]) -> str:
    stable = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode()).hexdigest()


class AlpacaStreamManager:
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        feed: str = "iex",
        symbols: list[str] | None = None,
        websocket_factory: WebSocketFactory | None = None,
        sleep: Sleep = asyncio.sleep,
        heartbeat_timeout_seconds: int = 30,
        maximum_backoff_seconds: int = 30,
        on_trade: EventHandler | None = None,
        on_quote: EventHandler | None = None,
        on_bar: EventHandler | None = None,
        on_raw_event: RawEventHandler | None = None,
        on_system_event: SystemEventHandler | None = None,
    ):
        if feed not in {"iex", "sip"}:
            raise ValueError("Alpaca feed must be iex or sip.")
        self.api_key = api_key
        self.secret_key = secret_key
        self.feed = feed
        self.symbols = sorted(
            {symbol.strip().upper() for symbol in symbols or [] if symbol.strip()}
        )
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.websocket_factory = websocket_factory or (
            lambda url: websockets.connect(url, ssl=self.ssl_context)
        )
        self.sleep = sleep
        self.heartbeat_timeout = timedelta(
            seconds=heartbeat_timeout_seconds
        )
        self.maximum_backoff = maximum_backoff_seconds
        self.on_trade = on_trade
        self.on_quote = on_quote
        self.on_bar = on_bar
        self.on_raw_event = on_raw_event
        self.on_system_event = on_system_event
        self.diagnostics = StreamDiagnostics(
            state=(
                StreamState.STOPPED
                if api_key and secret_key
                else StreamState.DISABLED
            ),
            subscriptions=self.symbols,
        )
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._seen: set[str] = set()
        self._seen_order: deque[str] = deque()
        self._maximum_seen_events = 50_000
        self._last_timestamp: dict[tuple[str, str], datetime] = {}

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    @property
    def url(self) -> str:
        return f"wss://stream.data.alpaca.markets/v2/{self.feed}"

    async def start(self) -> None:
        if not self.configured or self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self.run(), name="alpaca-market-stream")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.diagnostics.state = StreamState.STOPPED

    async def run(self, *, maximum_attempts: int | None = None) -> None:
        if not self.configured:
            self.diagnostics.state = StreamState.DISABLED
            return
        attempt = 0
        while not self._stop.is_set():
            if maximum_attempts is not None and attempt >= maximum_attempts:
                return
            attempt += 1
            self.diagnostics.state = (
                StreamState.CONNECTING
                if attempt == 1
                else StreamState.RECONNECTING
            )
            try:
                await self._connect_once()
                if self._stop.is_set():
                    return
                raise ConnectionError("Market-data stream closed unexpectedly.")
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.diagnostics.last_error = (
                    f"{type(error).__name__}: {error}"
                )
                self.diagnostics.reconnect_attempts += 1
                self.diagnostics.state = StreamState.RECONNECTING
                if self.on_system_event:
                    self.on_system_event(
                        "stream_disconnected",
                        {
                            "attempt": attempt,
                            "error_type": type(error).__name__,
                        },
                        datetime.now(timezone.utc),
                    )
                if maximum_attempts is not None and attempt >= maximum_attempts:
                    self.diagnostics.state = StreamState.ERROR
                    return
                backoff = min(2 ** (attempt - 1), self.maximum_backoff)
                if self.on_system_event:
                    self.on_system_event(
                        "stream_reconnect_scheduled",
                        {
                            "attempt": attempt + 1,
                            "backoff_seconds": backoff,
                        },
                        datetime.now(timezone.utc),
                    )
                await self.sleep(backoff)

    async def _connect_once(self) -> None:
        async with self.websocket_factory(self.url) as socket:
            await socket.send(
                json.dumps(
                    {
                        "action": "auth",
                        "key": self.api_key,
                        "secret": self.secret_key,
                    }
                )
            )
            await socket.send(
                json.dumps(
                    {
                        "action": "subscribe",
                        "trades": self.symbols,
                        "quotes": self.symbols,
                        "bars": self.symbols,
                    }
                )
            )
            now = datetime.now(timezone.utc)
            self.diagnostics.state = StreamState.CONNECTED
            self.diagnostics.connected_at = now
            self.diagnostics.last_heartbeat_at = now
            if self.on_system_event:
                self.on_system_event(
                    "stream_connected",
                    {
                        "feed": self.feed,
                        "symbols": self.symbols,
                    },
                    now,
                )
            while not self._stop.is_set():
                try:
                    message = await asyncio.wait_for(
                        socket.recv(),
                        timeout=self.heartbeat_timeout.total_seconds(),
                    )
                except TimeoutError as error:
                    self.diagnostics.state = StreamState.STALE
                    if self.on_system_event:
                        self.on_system_event(
                            "stream_stale",
                            {
                                "heartbeat_timeout_seconds": int(
                                    self.heartbeat_timeout.total_seconds()
                                )
                            },
                            datetime.now(timezone.utc),
                        )
                    raise TimeoutError("Alpaca stream heartbeat timed out.") from error
                self.process_message(message)

    def process_message(
        self,
        message: str | bytes | list[dict[str, Any]] | dict[str, Any],
        *,
        received_at: datetime | None = None,
    ) -> None:
        now = as_utc(received_at or datetime.now(timezone.utc))
        if isinstance(message, (str, bytes)):
            events = json.loads(message)
        else:
            events = message
        if isinstance(events, dict):
            events = [events]
        if not isinstance(events, list):
            self.diagnostics.invalid_events += 1
            return
        self.diagnostics.last_heartbeat_at = now
        for event in events:
            if not isinstance(event, dict):
                self.diagnostics.invalid_events += 1
                continue
            kind = str(event.get("T", ""))
            if kind in {"success", "subscription"}:
                self._observe_raw(event, now, "control")
                continue
            if kind == "error":
                self._observe_raw(event, now, "provider_error")
                self.diagnostics.last_error = str(
                    event.get("msg", "Alpaca stream error.")
                )
                self.diagnostics.invalid_events += 1
                continue
            try:
                timestamp = _timestamp(event["t"])
                ticker = str(event["S"]).upper()
            except (KeyError, TypeError, ValueError):
                self._observe_raw(event, now, "invalid")
                self.diagnostics.invalid_events += 1
                continue
            identity = _event_id(event)
            if identity in self._seen:
                self._observe_raw(event, now, "duplicate")
                self.diagnostics.duplicate_events += 1
                continue
            order_key = (kind, ticker)
            previous = self._last_timestamp.get(order_key)
            if previous and timestamp < previous:
                self._observe_raw(event, now, "out_of_order")
                self.diagnostics.out_of_order_events += 1
                continue
            if timestamp > now + timedelta(seconds=2):
                self._observe_raw(event, now, "future")
                self.diagnostics.invalid_events += 1
                continue
            self._seen.add(identity)
            self._seen_order.append(identity)
            if len(self._seen_order) > self._maximum_seen_events:
                self._seen.discard(self._seen_order.popleft())
            self._last_timestamp[order_key] = timestamp
            self.diagnostics.last_event_at = now
            self.diagnostics.messages_received += 1
            try:
                if kind == "t" and self.on_trade:
                    self.on_trade(
                        TradeTick(
                            ticker=ticker,
                            price=float(event["p"]),
                            size=float(event["s"]),
                            timestamp=timestamp,
                            event_id=identity,
                            source=f"alpaca_{self.feed}",
                        )
                    )
                elif kind == "q" and self.on_quote:
                    self.on_quote(
                        Quote(
                            ticker=ticker,
                            bid=float(event["bp"]),
                            ask=float(event["ap"]),
                            bid_size=float(event.get("bs", 0)),
                            ask_size=float(event.get("as", 0)),
                            timestamp=timestamp,
                            event_id=identity,
                            source=f"alpaca_{self.feed}",
                            coverage=(
                                "partial-market"
                                if self.feed == "iex"
                                else "full-market"
                            ),
                        )
                    )
                elif kind == "b" and self.on_bar:
                    complete = now >= timestamp + timedelta(minutes=1)
                    self.on_bar(
                        Bar(
                            ticker=ticker,
                            timeframe="1m",
                            open=float(event["o"]),
                            high=float(event["h"]),
                            low=float(event["l"]),
                            close=float(event["c"]),
                            volume=float(event["v"]),
                            vwap=(
                                float(event["vw"])
                                if event.get("vw") is not None
                                else None
                            ),
                            timestamp=timestamp,
                            source=f"alpaca_{self.feed}",
                            completeness=(
                                Completeness.CLOSED
                                if complete
                                else Completeness.INCOMPLETE
                            ),
                        )
                    )
                else:
                    self._observe_raw(event, now, "unsupported")
                    self.diagnostics.invalid_events += 1
                    continue
            except (KeyError, TypeError, ValueError):
                self._observe_raw(event, now, "invalid")
                self.diagnostics.invalid_events += 1
                continue
            self._observe_raw(event, now, "accepted")

    def _observe_raw(
        self,
        event: dict[str, Any],
        received_at: datetime,
        disposition: str,
    ) -> None:
        if self.on_raw_event:
            self.on_raw_event(event, received_at, disposition)

    def health(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = as_utc(now or datetime.now(timezone.utc))
        last = self.diagnostics.last_heartbeat_at
        stale = (
            self.diagnostics.state == StreamState.CONNECTED
            and last is not None
            and current - last > self.heartbeat_timeout
        )
        if stale:
            self.diagnostics.state = StreamState.STALE
        result = self.diagnostics.serialize()
        result.update(
            {
                "configured": self.configured,
                "feed": self.feed,
                "source": f"Alpaca {self.feed.upper()}",
                "coverage": (
                    "partial-market" if self.feed == "iex" else "full-market"
                ),
                "heartbeat_timeout_seconds": int(
                    self.heartbeat_timeout.total_seconds()
                ),
                "stale": stale,
            }
        )
        return result
